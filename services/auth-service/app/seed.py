"""Dữ liệu mẫu. user_id cố định để account-service seed đúng chủ tài khoản."""
import bcrypt
from sqlalchemy import select

from common.db import SessionLocal

from .models import User

DEMO_PASSWORD = "123456"

USERS = [
    # (id, username, full_name, phone, email)
    ("11111111-1111-1111-1111-111111111111", "minhnguyen", "Nguyễn Văn Minh", "0901234567", "minhnguyen@tdtu.edu.vn"),
    ("22222222-2222-2222-2222-222222222222", "thuha", "Trần Thu Hà", "0912345678", "thuha@tdtu.edu.vn"),
    ("33333333-3333-3333-3333-333333333333", "quocbao", "Võ Quốc Bảo", "0923456789", "quocbao@tdtu.edu.vn"),
    ("44444444-4444-4444-4444-444444444444", "itdu", "Lê Ít Dư", "0934567890", "itdu@tdtu.edu.vn"),
]


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()


def seed() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)):
            return
        pwd = hash_password(DEMO_PASSWORD)
        db.add_all(
            User(id=uid, username=u, password_hash=pwd, full_name=name, phone=phone, email=email)
            for uid, u, name, phone, email in USERS
        )
        db.commit()
