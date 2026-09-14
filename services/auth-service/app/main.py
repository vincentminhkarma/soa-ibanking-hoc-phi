"""auth-service — sở hữu dữ liệu người dùng và phát hành JWT."""
import bcrypt
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.app import create_app
from common.db import get_session
from common.errors import APIError
from common.security import CurrentUser, InternalOnly, create_access_token, current_user

from .models import User
from .schemas import LoginRequest, LoginResponse, UserProfile
from .seed import seed

app = create_app(
    "Auth Service",
    "Đăng nhập bằng username/password, phát hành JWT và cung cấp hồ sơ người dùng.",
    on_start=seed,
)

# Hash giả dùng cho nhánh "username không tồn tại" (chống timing attack).
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode()


@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["public"], summary="Đăng nhập")
def login(payload: LoginRequest, db: Session = Depends(get_session)) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    # So sánh hash kể cả khi user không tồn tại để tránh lộ username qua thời gian phản hồi.
    hashed = user.password_hash if user else _DUMMY_HASH
    ok = bcrypt.checkpw(payload.password.encode(), hashed.encode())
    if not user or not ok:
        raise APIError(401, "INVALID_CREDENTIALS", "Tên đăng nhập hoặc mật khẩu không đúng.")

    token, expires_in = create_access_token(
        user.id, user.username, user.full_name, user.email, user.phone
    )
    return LoginResponse(access_token=token, expires_in=expires_in, user=UserProfile(**user.as_dict()))


@app.get("/api/v1/auth/me", response_model=UserProfile, tags=["public"], summary="Thông tin tài khoản đang đăng nhập")
def me(user: CurrentUser = Depends(current_user), db: Session = Depends(get_session)) -> UserProfile:
    row = db.get(User, user.user_id)
    if not row:
        raise APIError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")
    return UserProfile(**row.as_dict())


@app.get(
    "/internal/users/{user_id}",
    response_model=UserProfile,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Hồ sơ người dùng (service-to-service)",
)
def get_user(user_id: str, db: Session = Depends(get_session)) -> UserProfile:
    row = db.get(User, user_id)
    if not row:
        raise APIError(404, "USER_NOT_FOUND", "Không tìm thấy người dùng.")
    return UserProfile(**row.as_dict())
