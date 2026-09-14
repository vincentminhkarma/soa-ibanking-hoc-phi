"""Xác thực: JWT cho người dùng, shared token cho lời gọi service-to-service."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header

from .config import INTERNAL_TOKEN, JWT_ALG, JWT_EXPIRES_MIN, JWT_SECRET
from .errors import APIError


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    username: str
    full_name: str
    email: str
    phone: str


def create_access_token(user_id: str, username: str, full_name: str, email: str, phone: str) -> tuple[str, int]:
    """Trả về (token, expires_in_seconds).

    Claim chứa sẵn thông tin người nộp tiền để payment-service không phải gọi
    ngược lại auth-service ở mọi request (giảm coupling và round-trip).
    """
    expires_in = JWT_EXPIRES_MIN * 60
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "username": username,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG), expires_in


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise APIError(401, "TOKEN_EXPIRED", "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")
    except jwt.PyJWTError:
        raise APIError(401, "INVALID_TOKEN", "Token không hợp lệ.")


def current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """Dependency cho API công khai.

    Mỗi service tự verify JWT (zero-trust) thay vì tin header do gateway gắn vào.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise APIError(401, "UNAUTHORIZED", "Thiếu access token.")
    claims = decode_token(authorization.split(" ", 1)[1].strip())
    return CurrentUser(
        user_id=claims["sub"],
        username=claims.get("username", ""),
        full_name=claims.get("full_name", ""),
        email=claims.get("email", ""),
        phone=claims.get("phone", ""),
    )


def require_internal(x_internal_token: str | None = Header(default=None)) -> None:
    """Dependency cho endpoint /internal/*: chỉ service khác trong cluster được gọi."""
    if x_internal_token != INTERNAL_TOKEN:
        raise APIError(403, "FORBIDDEN", "Endpoint nội bộ, không được phép truy cập từ bên ngoài.")


InternalOnly = Depends(require_internal)
