"""Unit test cho logic sinh/băm/che mã OTP (otp-service)."""
import re

import pytest
from _loader import load_module

codes = load_module("otp-service/app/codes.py")


def test_ma_otp_luon_dung_6_chu_so():
    for _ in range(200):
        assert re.fullmatch(r"\d{6}", codes.generate_code())


def test_ma_otp_du_ngau_nhien():
    """200 lần sinh phải ra nhiều giá trị khác nhau — chống sinh mã tĩnh."""
    assert len({codes.generate_code() for _ in range(200)}) > 150


def test_bam_ma_la_xac_dinh_va_khong_lo_plaintext():
    h1 = codes.hash_code("123456")
    h2 = codes.hash_code("123456")
    assert h1 == h2                       # cùng mã => cùng hash, để so sánh khi verify
    assert len(h1) == 64                  # SHA-256 hex
    assert "123456" not in h1             # không lộ mã gốc


def test_ma_khac_nhau_cho_hash_khac_nhau():
    assert codes.hash_code("123456") != codes.hash_code("123457")


def test_hash_khong_phu_thuoc_giao_dich():
    """Hash chỉ theo mã: nhờ vậy unique index trên code_hash mới chặn được
    hai giao dịch cùng có một mã đang hiệu lực."""
    assert codes.hash_code("999999") == codes.hash_code("999999")


@pytest.mark.parametrize(
    "email,expected",
    [
        ("minhnguyen@tdtu.edu.vn", "mi********@tdtu.edu.vn"),
        ("ha@tdtu.edu.vn", "h***@tdtu.edu.vn"),
        ("a@tdtu.edu.vn", "a***@tdtu.edu.vn"),
    ],
)
def test_che_email_giu_dau_va_ten_mien(email, expected):
    assert codes.mask_email(email) == expected


def test_che_email_khong_lo_phan_giua():
    masked = codes.mask_email("nguyenvanminh@tdtu.edu.vn")
    assert masked.startswith("ng")
    assert "nguyenvanminh" not in masked
    assert masked.endswith("@tdtu.edu.vn")
