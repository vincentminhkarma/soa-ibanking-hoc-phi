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
    # Người dùng bổ sung: scripts/seed_demo.py dùng các tài khoản này để tạo lịch sử giao dịch mẫu.
    ("55555555-5555-5555-5555-555555555555", "ngoclan", "Phạm Ngọc Lan", "0945678901", "ngoclan@tdtu.edu.vn"),
    ("66666666-6666-6666-6666-666666666666", "ducthinh", "Hoàng Đức Thịnh", "0956789012", "ducthinh@tdtu.edu.vn"),
    ("77777777-7777-7777-7777-777777777777", "hoangyen", "Đỗ Hoàng Yến", "0967890123", "hoangyen@tdtu.edu.vn"),
    ("88888888-8888-8888-8888-888888888888", "giahan", "Lý Gia Hân", "0978901234", "giahan@tdtu.edu.vn"),
    ("99999999-9999-9999-9999-999999999999", "tuananh", "Bùi Tuấn Anh", "0989012345", "tuananh@tdtu.edu.vn"),
    ("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "camtu", "Trịnh Cẩm Tú", "0990123456", "camtu@tdtu.edu.vn"),
]


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()


def seed() -> None:
    # Chèn từng người dùng còn thiếu, nên database đã có dữ liệu vẫn nhận thêm dòng mới.
    with SessionLocal() as db:
        existing = set(db.scalars(select(User.id)))
        missing = [u for u in USERS if u[0] not in existing]
        if not missing:
            return
        pwd = hash_password(DEMO_PASSWORD)
        db.add_all(
            User(id=uid, username=u, password_hash=pwd, full_name=name, phone=phone, email=email)
            for uid, u, name, phone, email in missing
        )
        db.commit()
