"""Logic thuần của OTP: sinh mã, băm, che email.

Tách khỏi `main.py` để unit-test được mà không cần database hay HTTP.
"""
import hashlib
import os
import secrets

# Pepper: băm theo chính mã (không trộn payment_id) để partial unique index trên
# code_hash thực sự chặn được trùng mã giữa các giao dịch đang hiệu lực.
OTP_PEPPER = os.getenv("OTP_PEPPER", "tdtu-ibanking-pepper")

CODE_LENGTH = 6


def generate_code() -> str:
    """Mã 6 chữ số sinh bằng nguồn ngẫu nhiên an toàn mật mã."""
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


def hash_code(code: str) -> str:
    """Băm SHA-256 kèm pepper — không bao giờ lưu mã dạng plaintext."""
    return hashlib.sha256((OTP_PEPPER + code).encode()).hexdigest()


def mask_email(email: str) -> str:
    """mi*******@tdtu.edu.vn — đủ để người dùng nhận ra hộp thư của mình."""
    name, _, domain = email.partition("@")
    keep = name[:2] if len(name) > 2 else name[:1]
    return f"{keep}{'*' * max(len(name) - len(keep), 3)}@{domain}"
