"""Unit test template email (notification-service)."""
from _loader import load_module

templates = load_module("notification-service/app/templates.py")

OTP_DATA = {
    "otp_code": "482913",
    "payment_id": "4b2e8f11-aaaa-bbbb-cccc-ddddeeeeffff",
    "recipient_name": "Nguyễn Văn Minh",
    "student_code": "522H0001",
    "student_name": "Nguyễn Văn Minh",
    "amount": 9500000,
    "ttl_minutes": 5,
}


def test_email_otp_chua_ma_va_ma_giao_dich():
    subject, html, text = templates.otp_email(OTP_DATA)
    assert "OTP" in subject
    assert "482913" in html and "482913" in text
    # Bản text phải nêu rõ payment_id: OTP gắn với đúng một giao dịch.
    assert OTP_DATA["payment_id"] in text and OTP_DATA["payment_id"] in html


def test_email_otp_nhac_han_su_dung():
    _, html, text = templates.otp_email(OTP_DATA)
    assert "5 phút" in html
    assert "5 phut" in text


def test_email_bien_lai_ghi_ro_thanh_cong():
    subject, html, text = templates.receipt_email(
        {
            "payment_id": "4b2e8f11",
            "payer_name": "Trần Thu Hà",
            "student_code": "522H0003",
            "student_name": "Phạm Minh Tuấn",
            "semester": "HK1/2026-2027",
            "amount": 10200000,
            "balance_after": 12900000,
            "completed_at": "14/09/2026 15:06:36 UTC",
        }
    )
    assert "thanh cong" in subject.lower()
    assert "STATUS: SUCCESS" in text
    assert "522H0003" in html and "522H0003" in text


def test_dinh_dang_tien_kieu_viet_nam():
    assert templates._money(9500000) == "9.500.000 VND"
    assert templates._money("10200000.00") == "10.200.000 VND"
    assert templates._money(0) == "0 VND"


def test_chi_co_hai_template_duoc_phep():
    assert set(templates.RENDERERS) == {"OTP", "RECEIPT"}
