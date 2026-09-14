"""Kiểm thử hai tình huống đồng thời ở mục 5 của đề bài.

Hai test này là bằng chứng chạy được cho phần Transaction & Concurrency:
mỗi test bắn nhiều request confirm đúng lúc bằng ThreadPoolExecutor và kiểm tra
trạng thái cuối cùng của số dư, học phí và lịch sử giao dịch.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from conftest import Client, error_code, fee_state, new_fee, read_otp, top_up


def _chuan_bi_giao_dich(client: Client, student_code: str) -> str:
    created = client.create_payment(student_code)
    created.raise_for_status()
    payment_id = created.json()["payment"]["id"]
    read_otp(payment_id)  # chờ email tới trước khi vào pha đồng thời
    return payment_id


def _confirm_dong_thoi(jobs: list[tuple[Client, str]]) -> list:
    """Bắn tất cả confirm cùng lúc; mỗi job là (client, payment_id)."""
    otps = {pid: read_otp(pid) for _, pid in jobs}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(c.confirm, pid, otps[pid]) for c, pid in jobs]
        return [f.result() for f in futures]


def test_51_nhieu_giao_dich_tren_cung_mot_tai_khoan(carol: Client):
    """Số dư chỉ đủ cho MỘT giao dịch; hai giao dịch chạy song song.

    Kỳ vọng: đúng một giao dịch SUCCESS, giao dịch còn lại FAILED với
    INSUFFICIENT_FUNDS, số dư cuối cùng bằng 0 và không bao giờ âm.
    """
    top_up(carol.user["id"], "12000000.00", f"topup-conc-{carol.user['id']}-{id(carol)}")
    so_du = carol.balance()
    assert so_du > 0

    # Hai khoản học phí, mỗi khoản đúng bằng toàn bộ số dư => chỉ trả nổi một.
    fee_a = new_fee(so_du, prefix="CA")
    fee_b = new_fee(so_du, prefix="CB")
    payment_a = _chuan_bi_giao_dich(carol, fee_a["student_code"])
    payment_b = _chuan_bi_giao_dich(carol, fee_b["student_code"])

    ket_qua = _confirm_dong_thoi([(carol, payment_a), (carol, payment_b)])
    thanh_cong = [r for r in ket_qua if r.status_code == 200]
    that_bai = [r for r in ket_qua if r.status_code != 200]

    assert len(thanh_cong) == 1, "Không được để hai giao dịch cùng tiêu một số dư"
    assert len(that_bai) == 1
    assert error_code(that_bai[0]) == "INSUFFICIENT_FUNDS"

    assert carol.balance() == Decimal("0.00")  # không âm, không tiêu vượt
    trang_thai = [fee_state(fee_a["id"])["status"], fee_state(fee_b["id"])["status"]]
    assert sorted(trang_thai) == ["PAID", "UNPAID"]


def test_52_nhieu_tai_khoan_thanh_toan_cung_mot_hoc_phi(alice: Client, bob: Client):
    """Hai người dùng cùng đóng học phí cho một MSSV, xác nhận cùng lúc.

    Kỳ vọng: khoản học phí chỉ được thanh toán thành công MỘT lần; người thua
    bị từ chối và được hoàn lại tiền (số dư trở về như trước giao dịch).
    """
    fee = new_fee("1000000.00", prefix="CS")
    amount = Decimal("1000000.00")
    top_up(alice.user["id"], "2000000.00", f"topup-same-a-{fee['id']}")
    top_up(bob.user["id"], "2000000.00", f"topup-same-b-{fee['id']}")

    payment_alice = _chuan_bi_giao_dich(alice, fee["student_code"])
    payment_bob = _chuan_bi_giao_dich(bob, fee["student_code"])
    so_du_truoc = {"alice": alice.balance(), "bob": bob.balance()}

    ket_qua = _confirm_dong_thoi([(alice, payment_alice), (bob, payment_bob)])
    thanh_cong = [r for r in ket_qua if r.status_code == 200]
    that_bai = [r for r in ket_qua if r.status_code != 200]

    assert len(thanh_cong) == 1, "Một khoản học phí chỉ được thanh toán thành công một lần"
    assert error_code(that_bai[0]) == "TUITION_ALREADY_PAID"

    fee_sau = fee_state(fee["id"])
    assert fee_sau["status"] == "PAID"
    assert fee_sau["payment_ref"] == thanh_cong[0].json()["id"]

    # Người thắng bị trừ tiền, người thua được hoàn tiền về đúng số dư ban đầu.
    nguoi_thang = thanh_cong[0].json()["payer"]["email"]
    for ten, client in (("alice", alice), ("bob", bob)):
        giam = so_du_truoc[ten] - client.balance()
        assert giam == (amount if client.user["email"] == nguoi_thang else Decimal("0.00"))

    # Bù trừ phải để lại dấu vết: một bút toán CREDIT hoàn tiền trong sổ cái.
    nguoi_thua = bob if bob.user["email"] != nguoi_thang else alice
    payment_thua = payment_bob if nguoi_thua is bob else payment_alice
    ledger = nguoi_thua.http.get("/accounts/me/transactions").json()["items"]
    assert any(
        item["reference"] == f"{payment_thua}:refund" and item["direction"] == "CREDIT" for item in ledger
    )


def test_xac_nhan_trung_lap_khong_tru_tien_hai_lan(alice: Client):
    """Bấm xác nhận nhiều lần cho cùng một giao dịch chỉ trừ tiền một lần."""
    fee = new_fee("600000.00", prefix="ID")
    top_up(alice.user["id"], "1000000.00", f"topup-dup-{fee['id']}")
    payment_id = _chuan_bi_giao_dich(alice, fee["student_code"])
    otp = read_otp(payment_id)
    so_du_truoc = alice.balance()

    with ThreadPoolExecutor(max_workers=3) as pool:
        ket_qua = [f.result() for f in [pool.submit(alice.confirm, payment_id, otp) for _ in range(3)]]

    assert sum(1 for r in ket_qua if r.status_code == 200) >= 1
    assert alice.balance() == so_du_truoc - Decimal("600000.00")
    ledger = alice.http.get("/accounts/me/transactions").json()["items"]
    assert sum(1 for item in ledger if item["reference"] == payment_id) == 1
