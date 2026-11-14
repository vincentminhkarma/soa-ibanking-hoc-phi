"""Kiểm thử job đối soát giao dịch treo ở PROCESSING.

Không thể "giết" tiến trình giữa saga một cách tin cậy trong test, nên ta dựng
lại đúng trạng thái hỏng đó bằng cách: gọi thẳng các bước nội bộ rồi ép trạng
thái `PROCESSING` trong database — y như khi payment-service chết giữa chừng.
"""
from concurrent.futures import ThreadPoolExecutor
import os
import time
from decimal import Decimal

import httpx
import psycopg
import pytest
from conftest import ACCOUNT_URL, INTERNAL_HEADERS, TUITION_URL, Client, fee_state, new_fee, top_up

PAYMENT_URL = os.getenv("PAYMENT_URL", "http://localhost:8004")
PAYMENT_DSN = os.getenv("PAYMENT_DSN", "postgresql://ibanking:ibanking@localhost:5433/paymentdb")


def force_stuck(payment_id: str, seconds_ago: int = 300) -> None:
    """Ép giao dịch về trạng thái treo — mô phỏng tiến trình chết giữa saga."""
    with psycopg.connect(PAYMENT_DSN, autocommit=True) as conn:
        conn.execute(
            "UPDATE payments SET status = 'PROCESSING', "
            "processing_at = now() - make_interval(secs => %s) WHERE id = %s",
            (seconds_ago, payment_id),
        )


def debit_directly(user_id: str, amount: str, reference: str) -> None:
    resp = httpx.post(
        f"{ACCOUNT_URL}/internal/accounts/{user_id}/debit",
        json={"amount": amount, "reference": reference, "description": "Mô phỏng đã trừ tiền"},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()


def mark_fee_paid(fee_id: str, payment_ref: str) -> None:
    resp = httpx.post(
        f"{TUITION_URL}/internal/tuitions/fees/{fee_id}/pay",
        json={"payment_ref": payment_ref},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()


def run_reconcile() -> dict:
    resp = httpx.post(
        f"{PAYMENT_URL}/internal/payments/reconcile",
        params={"stuck_after_seconds": 0},
        headers=INTERNAL_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def action_for(report: dict, payment_id: str) -> str | None:
    return next((r["action"] for r in report["resolved"] if r["payment_id"] == payment_id), None)


@pytest.fixture
def pending(alice: Client):
    """Một giao dịch PENDING_OTP kèm khoản học phí riêng và số dư đủ."""
    fee = new_fee("700000.00", prefix="RC")
    top_up(alice.user["id"], "1000000.00", f"topup-rec-{fee['id']}")
    payment = alice.create_payment(fee["student_code"]).json()["payment"]
    return fee, payment


def test_treo_sau_khi_tru_tien_thi_duoc_hoan_tien(alice: Client, pending):
    """Chết sau bước trừ tiền, trước bước gạch nợ => phải hoàn tiền, học phí giữ nguyên."""
    fee, payment = pending
    so_du_truoc = alice.balance()
    debit_directly(alice.user["id"], "700000.00", payment["id"])
    assert alice.balance() == so_du_truoc - Decimal("700000.00")
    force_stuck(payment["id"], seconds_ago=1)

    assert action_for(run_reconcile(), payment["id"]) == "REFUND_AND_FAIL"

    ket_qua = alice.http.get(f"/payments/{payment['id']}").json()
    assert ket_qua["status"] == "FAILED"
    assert ket_qua["failure_code"] == "RECONCILED_REFUND"
    assert alice.balance() == so_du_truoc                      # tiền đã về
    assert fee_state(fee["id"])["status"] == "UNPAID"          # học phí không bị đụng
    ledger = alice.http.get("/accounts/me/transactions").json()["items"]
    assert any(i["reference"] == f"{payment['id']}:refund" and i["direction"] == "CREDIT" for i in ledger)


def test_treo_sau_khi_gach_no_thi_duoc_hoan_tat(alice: Client, pending):
    """Chết sau khi đã trừ tiền VÀ gạch nợ => đối soát hoàn tất giao dịch, không hoàn tiền."""
    fee, payment = pending
    so_du_truoc = alice.balance()
    debit_directly(alice.user["id"], "700000.00", payment["id"])
    mark_fee_paid(fee["id"], payment["id"])
    force_stuck(payment["id"], seconds_ago=1)

    assert action_for(run_reconcile(), payment["id"]) == "COMPLETE"

    ket_qua = alice.http.get(f"/payments/{payment['id']}").json()
    assert ket_qua["status"] == "SUCCESS"
    assert Decimal(str(ket_qua["balance_after"])) == so_du_truoc - Decimal("700000.00")
    assert alice.balance() == so_du_truoc - Decimal("700000.00")
    fee_sau = fee_state(fee["id"])
    assert fee_sau["status"] == "PAID" and fee_sau["payment_ref"] == payment["id"]


def test_treo_truoc_khi_tru_tien_thi_chi_dong_giao_dich(alice: Client, pending):
    """Chết trước khi trừ tiền => không tạo tiền từ hư không, chỉ đóng giao dịch."""
    fee, payment = pending
    so_du_truoc = alice.balance()
    force_stuck(payment["id"], seconds_ago=1)

    assert action_for(run_reconcile(), payment["id"]) == "FAIL"

    ket_qua = alice.http.get(f"/payments/{payment['id']}").json()
    assert ket_qua["status"] == "FAILED"
    assert ket_qua["failure_code"] == "RECONCILED_FAIL"
    assert alice.balance() == so_du_truoc
    assert fee_state(fee["id"])["status"] == "UNPAID"


def test_doi_soat_idempotent(alice: Client, pending):
    """Chạy đối soát nhiều lần không được trừ/hoàn thêm lần nào."""
    fee, payment = pending
    so_du_truoc = alice.balance()
    debit_directly(alice.user["id"], "700000.00", payment["id"])
    force_stuck(payment["id"], seconds_ago=1)

    run_reconcile()
    so_du_sau_lan_1 = alice.balance()
    run_reconcile()   # giao dịch đã FAILED nên không còn nằm trong danh sách treo
    run_reconcile()

    assert alice.balance() == so_du_sau_lan_1 == so_du_truoc
    ledger = alice.http.get("/accounts/me/transactions").json()["items"]
    assert sum(1 for i in ledger if i["reference"] == f"{payment['id']}:refund") == 1


def test_giao_dich_binh_thuong_khong_bi_doi_soat_dung_vao(alice: Client):
    """Giao dịch vừa tạo (PENDING_OTP) không bao giờ bị job đối soát chạm tới."""
    fee = new_fee("650000.00", prefix="RK")
    top_up(alice.user["id"], "1000000.00", f"topup-safe-{fee['id']}")
    payment = alice.create_payment(fee["student_code"]).json()["payment"]

    assert action_for(run_reconcile(), payment["id"]) is None
    assert alice.http.get(f"/payments/{payment['id']}").json()["status"] == "PENDING_OTP"


def test_no_debit_but_paid_reverts_fee(alice: Client, pending):
    """Đã gạch nợ nhưng không có bút toán trừ tiền => huỷ gạch nợ (revert) và fail."""
    fee, payment = pending
    mark_fee_paid(fee["id"], payment["id"])
    force_stuck(payment["id"], seconds_ago=1)

    assert action_for(run_reconcile(), payment["id"]) == "REVERT_AND_FAIL"
    ket_qua = alice.http.get(f"/payments/{payment['id']}").json()
    assert ket_qua["status"] == "FAILED"
    assert ket_qua["failure_code"] == "RECONCILED_REVERT"
    assert fee_state(fee["id"])["status"] == "UNPAID"


def test_other_payer_fee_refunds_without_revert(alice: Client, bob: Client, pending):
    """Học phí đã bị tài khoản khác gạch nợ, tiền mình bị trừ => hoàn tiền, không revert học phí."""
    fee, payment = pending
    so_du_truoc = alice.balance()
    debit_directly(alice.user["id"], "700000.00", payment["id"])
    other_ref = f"other-{fee['id']}"
    mark_fee_paid(fee["id"], other_ref)
    force_stuck(payment["id"], seconds_ago=1)

    assert action_for(run_reconcile(), payment["id"]) == "REFUND_AND_FAIL"
    ket_qua = alice.http.get(f"/payments/{payment['id']}").json()
    assert ket_qua["status"] == "FAILED"
    assert ket_qua["failure_code"] == "RECONCILED_REFUND"
    assert alice.balance() == so_du_truoc
    current_fee = fee_state(fee["id"])
    assert current_fee["status"] == "PAID"
    assert current_fee["payment_ref"] == other_ref


def test_crash_after_refund_with_owned_fee(alice: Client, pending):
    """Đã trừ tiền, đã gạch nợ, đã hoàn tiền trước khi crash (có refund entry) => revert và fail."""
    fee, payment = pending
    debit_directly(alice.user["id"], "700000.00", payment["id"])
    mark_fee_paid(fee["id"], payment["id"])
    # Refund entry đã tồn tại trong account-service
    resp = httpx.post(
        f"{ACCOUNT_URL}/internal/accounts/{alice.user['id']}/credit",
        json={"amount": "700000.00", "reference": f"{payment['id']}:refund", "description": "Crash mock refund"},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    force_stuck(payment["id"], seconds_ago=1)

    assert action_for(run_reconcile(), payment["id"]) == "REVERT_AND_FAIL"
    ket_qua = alice.http.get(f"/payments/{payment['id']}").json()
    assert ket_qua["status"] == "FAILED"
    assert ket_qua["failure_code"] == "RECONCILED_REVERT"
    assert fee_state(fee["id"])["status"] == "UNPAID"


def test_crash_after_refund_without_owned_fee(alice: Client, pending):
    """Đã trừ tiền, học phí chưa gạch nợ, đã hoàn tiền trước khi crash => chỉ đóng fail."""
    fee, payment = pending
    debit_directly(alice.user["id"], "700000.00", payment["id"])
    resp = httpx.post(
        f"{ACCOUNT_URL}/internal/accounts/{alice.user['id']}/credit",
        json={"amount": "700000.00", "reference": f"{payment['id']}:refund", "description": "Crash mock refund"},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    force_stuck(payment["id"], seconds_ago=1)

    assert action_for(run_reconcile(), payment["id"]) == "FAIL"
    ket_qua = alice.http.get(f"/payments/{payment['id']}").json()
    assert ket_qua["status"] == "FAILED"
    assert ket_qua["failure_code"] == "RECONCILED_REFUND"


def test_recent_processing_ignored_default(alice: Client, pending):
    """Giao dịch PROCESSING mới vào (dưới 60s) bị bỏ qua khi quét đối soát mặc định."""
    fee, payment = pending
    force_stuck(payment["id"], seconds_ago=5)

    resp = httpx.post(f"{PAYMENT_URL}/internal/payments/reconcile", headers=INTERNAL_HEADERS, timeout=30)
    resp.raise_for_status()
    report = resp.json()
    assert action_for(report, payment["id"]) is None
    assert alice.http.get(f"/payments/{payment['id']}").json()["status"] == "PROCESSING"


def test_locked_payment_skipped_by_reconciler(alice: Client, pending):
    """Giao dịch đang bị tiến trình khác giữ khoá (SELECT FOR UPDATE) phải được bỏ qua."""
    fee, payment = pending
    force_stuck(payment["id"], seconds_ago=1)

    with psycopg.connect(PAYMENT_DSN) as conn:
        conn.execute("BEGIN;")
        conn.execute("SELECT id FROM payments WHERE id = %s FOR UPDATE;", (payment["id"],))
        report = run_reconcile()
        assert action_for(report, payment["id"]) is None
        conn.execute("ROLLBACK;")

    assert action_for(run_reconcile(), payment["id"]) == "FAIL"


def test_concurrent_sweepers_each_payment_once(alice: Client):
    """Nhiều sweeper chạy song song chỉ xử lý mỗi giao dịch đúng một lần."""
    fees_and_payments = []
    for _ in range(3):
        fee = new_fee("500000.00", prefix="SW")
        top_up(alice.user["id"], "1000000.00", f"topup-sw-{fee['id']}")
        p = alice.create_payment(fee["student_code"]).json()["payment"]
        force_stuck(p["id"], seconds_ago=1)
        fees_and_payments.append((fee, p))

    with ThreadPoolExecutor(max_workers=3) as pool:
        reports = list(pool.map(lambda _: run_reconcile(), range(3)))

    resolved_counts = {}
    for r in reports:
        for item in r["resolved"]:
            pid = item["payment_id"]
            resolved_counts[pid] = resolved_counts.get(pid, 0) + 1

    for _, p in fees_and_payments:
        assert resolved_counts.get(p["id"], 0) == 1
        assert alice.http.get(f"/payments/{p['id']}").json()["status"] == "FAILED"


def test_background_tick_resolves_automatically(alice: Client):
    """Background ticker tự động phát hiện và xử lý giao dịch treo > 300s mà không cần gọi API."""
    fee = new_fee("550000.00", prefix="BG")
    top_up(alice.user["id"], "1000000.00", f"topup-bg-{fee['id']}")
    payment = alice.create_payment(fee["student_code"]).json()["payment"]
    force_stuck(payment["id"], seconds_ago=300)

    deadline = time.time() + 40
    resolved = False
    while time.time() < deadline:
        st = alice.http.get(f"/payments/{payment['id']}").json()["status"]
        if st in {"FAILED", "SUCCESS"}:
            resolved = True
            break
        time.sleep(2)
    assert resolved, "Job đối soát nền không xử lý giao dịch trong thời gian quy định."


def test_reconcile_invalid_threshold_422():
    """Gọi reconcile với ngưỡng âm stuck_after_seconds = -1 trả về 422 Unprocessable Entity."""
    resp = httpx.post(
        f"{PAYMENT_URL}/internal/payments/reconcile",
        params={"stuck_after_seconds": -1},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )
    assert resp.status_code == 422


def test_read_entry_wrong_user_404(alice: Client, pending):
    """Tra cứu bút toán của user này dưới user_id khác trả về 404 ENTRY_NOT_FOUND."""
    fee, payment = pending
    debit_directly(alice.user["id"], "700000.00", payment["id"])

    resp = httpx.get(
        f"{ACCOUNT_URL}/internal/accounts/00000000-0000-0000-0000-000000000000/entries/{payment['id']}",
        headers=INTERNAL_HEADERS,
        timeout=15,
    )
    assert resp.status_code == 404
    assert resp.json().get("error", {}).get("code") == "ENTRY_NOT_FOUND"
