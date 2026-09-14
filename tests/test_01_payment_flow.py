"""Integration test luồng nghiệp vụ chính (chạy qua API Gateway như client thật)."""
from decimal import Decimal

import httpx
from conftest import (
    GATEWAY,
    Client,
    error_code,
    fee_state,
    new_fee,
    read_otp,
    receipt_exists,
    top_up,
)


def test_login_thanh_cong(alice: Client):
    assert alice.user["username"] == "minhnguyen"
    assert alice.token


def test_login_sai_mat_khau():
    resp = httpx.post(
        f"{GATEWAY}/api/v1/auth/login", json={"username": "minhnguyen", "password": "sai-mat-khau"}, timeout=15
    )
    assert resp.status_code == 401
    assert error_code(resp) == "INVALID_CREDENTIALS"


def test_goi_api_khong_co_token():
    resp = httpx.get(f"{GATEWAY}/api/v1/accounts/me", timeout=15)
    assert resp.status_code == 401


def test_gateway_chan_endpoint_noi_bo():
    """Endpoint /internal/* tuyệt đối không lộ ra ngoài qua gateway."""
    resp = httpx.get(f"{GATEWAY}/api/v1/tuitions/internal/tuitions/fees/abc", timeout=15)
    assert resp.status_code in (401, 403)


def test_tra_cuu_mssv_khong_ton_tai(alice: Client):
    resp = alice.lookup("999X9999")
    assert resp.status_code == 404
    assert error_code(resp) == "STUDENT_NOT_FOUND"


def test_tra_cuu_hien_dung_cong_no(alice: Client):
    fee = new_fee("1500000.00")
    resp = alice.lookup(fee["student_code"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["student"]["student_code"] == fee["student_code"]
    assert Decimal(str(body["outstanding_fee"]["amount"])) == Decimal("1500000.00")
    assert body["outstanding_fee"]["status"] == "UNPAID"


def test_luong_thanh_toan_thanh_cong_dau_den_cuoi(alice: Client):
    fee = new_fee("1200000.00")
    top_up(alice.user["id"], "2000000.00", f"topup-happy-{fee['id']}")
    balance_truoc = alice.balance()

    created = alice.create_payment(fee["student_code"])
    assert created.status_code == 201
    payment = created.json()["payment"]
    assert payment["status"] == "PENDING_OTP"
    assert created.json()["otp_sent_to"].endswith("@tdtu.edu.vn")

    otp = read_otp(payment["id"])  # OTP lấy từ email thật trong MailHog
    confirmed = alice.confirm(payment["id"], otp)
    assert confirmed.status_code == 200
    result = confirmed.json()

    # 1. Giao dịch thành công
    assert result["status"] == "SUCCESS"
    # 2. Trừ đúng số tiền khỏi tài khoản người nộp
    assert alice.balance() == balance_truoc - Decimal("1200000.00")
    assert Decimal(str(result["balance_after"])) == balance_truoc - Decimal("1200000.00")
    # 3. Học phí chuyển sang đã thanh toán, gắn đúng giao dịch
    fee_sau = fee_state(fee["id"])
    assert fee_sau["status"] == "PAID"
    assert fee_sau["payment_ref"] == payment["id"]
    # 4. Lưu vào lịch sử giao dịch
    ledger = alice.http.get("/accounts/me/transactions").json()["items"]
    assert any(item["reference"] == payment["id"] and item["direction"] == "DEBIT" for item in ledger)
    assert any(p["id"] == payment["id"] for p in alice.http.get("/payments").json()["items"])
    # 5. Gửi email xác nhận
    assert receipt_exists(payment["id"])
    # 6. Saga trace ghi đủ các bước
    steps = [e["step"] for e in alice.http.get(f"/payments/{payment['id']}/events").json()]
    assert steps == [
        "PAYMENT_CREATED", "OTP_ISSUED", "OTP_VERIFIED", "DEBIT",
        "MARK_TUITION_PAID", "PAYMENT_COMPLETED", "RECEIPT_EMAIL",
    ]


def test_khong_du_so_du_bi_tu_choi_ngay_tu_dau(alice: Client):
    qua_kha_nang = alice.balance() + Decimal("1000000")
    fee = new_fee(qua_kha_nang)
    resp = alice.create_payment(fee["student_code"])
    assert resp.status_code == 409
    assert error_code(resp) == "INSUFFICIENT_FUNDS"
    assert fee_state(fee["id"])["status"] == "UNPAID"


def test_hoc_phi_da_dong_thi_khong_tao_duoc_giao_dich_moi(bob: Client):
    fee = new_fee("900000.00")
    top_up(bob.user["id"], "2000000.00", f"topup-paid-{fee['id']}")

    created = bob.create_payment(fee["student_code"])
    payment_id = created.json()["payment"]["id"]
    assert bob.confirm(payment_id, read_otp(payment_id)).status_code == 200

    lai = bob.create_payment(fee["student_code"])
    assert lai.status_code == 409
    assert error_code(lai) == "NO_OUTSTANDING_TUITION"


def test_idempotency_key_khong_tao_giao_dich_trung(alice: Client):
    fee = new_fee("800000.00")
    top_up(alice.user["id"], "1000000.00", f"topup-idem-{fee['id']}")
    key = f"idem-{fee['id']}"

    lan_1 = alice.create_payment(fee["student_code"], idem=key)
    lan_2 = alice.create_payment(fee["student_code"], idem=key)
    assert lan_1.json()["payment"]["id"] == lan_2.json()["payment"]["id"]


def test_khong_xem_duoc_giao_dich_cua_nguoi_khac(alice: Client, bob: Client):
    fee = new_fee("700000.00")
    top_up(alice.user["id"], "1000000.00", f"topup-acl-{fee['id']}")
    payment_id = alice.create_payment(fee["student_code"]).json()["payment"]["id"]

    resp = bob.http.get(f"/payments/{payment_id}")
    assert resp.status_code == 403
    assert error_code(resp) == "FORBIDDEN"
