"""Kiểm thử các ràng buộc OTP theo đúng mục 3 của đề bài."""
import os
import time
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from conftest import (
    INTERNAL_HEADERS,
    Client,
    error_code,
    new_fee,
    read_otp,
    top_up,
)

OTP_URL = os.getenv("OTP_URL", "http://localhost:8005")
OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "300"))


def _issue(payment_id: str, email: str = "otp-test@tdtu.edu.vn") -> dict:
    resp = httpx.post(
        f"{OTP_URL}/internal/otp/issue",
        json={"payment_id": payment_id, "email": email, "recipient_name": "Kiểm thử OTP"},
        headers=INTERNAL_HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _verify(payment_id: str, code: str) -> httpx.Response:
    return httpx.post(
        f"{OTP_URL}/internal/otp/verify",
        json={"payment_id": payment_id, "code": code},
        headers=INTERNAL_HEADERS,
        timeout=20,
    )


def _pending_payment(client: Client, amount: str = "500000.00") -> dict:
    fee = new_fee(amount)
    top_up(client.user["id"], "1000000.00", f"topup-otp-{fee['id']}")
    return client.create_payment(fee["student_code"]).json()["payment"]


def test_otp_co_han_dung_5_phut(alice: Client):
    payment = _pending_payment(alice)
    con_lai = (datetime.fromisoformat(payment["otp_expires_at"]) - datetime.now(UTC)).total_seconds()
    assert OTP_TTL_SECONDS == 300, "Đề bài yêu cầu OTP hiệu lực tối đa 5 phút"
    assert 280 <= con_lai <= 300


def test_otp_sai_bi_tu_choi_va_dem_so_lan_thu(alice: Client):
    payment = _pending_payment(alice)
    read_otp(payment["id"])  # đảm bảo email đã tới trước khi thử sai

    resp = alice.confirm(payment["id"], "000000")
    assert resp.status_code == 400
    assert error_code(resp) in ("OTP_INVALID", "OTP_LOCKED")
    assert resp.json()["error"]["details"].get("remaining_attempts") == 4


def test_otp_chi_dung_duoc_mot_lan(alice: Client):
    """Xác thực trực tiếp ở otp-service: lần verify thứ hai không còn mã hiệu lực."""
    payment_id = str(uuid.uuid4())
    _issue(payment_id)
    code = read_otp(payment_id)

    assert _verify(payment_id, code).status_code == 200
    lan_hai = _verify(payment_id, code)
    assert lan_hai.status_code == 400
    assert error_code(lan_hai) == "OTP_NOT_FOUND"


def test_otp_gan_voi_dung_mot_giao_dich(alice: Client):
    """Mã của giao dịch A không dùng được cho giao dịch B."""
    payment_a = _pending_payment(alice)
    payment_b = _pending_payment(alice)
    code_a = read_otp(payment_a["id"])

    resp = alice.confirm(payment_b["id"], code_a)
    assert resp.status_code == 400
    assert error_code(resp) == "OTP_INVALID"

    # Mã của A vẫn dùng được cho chính A.
    assert alice.confirm(payment_a["id"], code_a).status_code == 200


def test_gui_lai_ma_thi_ma_cu_het_hieu_luc(alice: Client):
    payment = _pending_payment(alice)
    code_cu = read_otp(payment["id"])

    alice.resend(payment["id"])
    time.sleep(1)
    resp = alice.confirm(payment["id"], code_cu)
    assert resp.status_code == 400
    assert error_code(resp) == "OTP_INVALID"


def test_nhap_sai_qua_so_lan_thi_khoa_ma(alice: Client):
    payment = _pending_payment(alice)
    read_otp(payment["id"])

    codes = ["111111", "222222", "333333", "444444", "555555"]
    ket_qua = [error_code(alice.confirm(payment["id"], c)) for c in codes]
    assert ket_qua[-1] == "OTP_LOCKED"
    assert ket_qua[:-1] == ["OTP_INVALID"] * 4


@pytest.mark.skipif(OTP_TTL_SECONDS > 15, reason="Chỉ chạy khi đặt OTP_TTL_SECONDS ngắn để test hết hạn")
def test_otp_het_han_bi_tu_choi(alice: Client):
    payment_id = str(uuid.uuid4())
    _issue(payment_id)
    code = read_otp(payment_id)
    time.sleep(OTP_TTL_SECONDS + 2)
    resp = _verify(payment_id, code)
    assert resp.status_code == 400
    assert error_code(resp) == "OTP_EXPIRED"
