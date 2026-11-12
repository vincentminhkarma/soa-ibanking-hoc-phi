"""Tài khoản mẫu, user_id khớp với dữ liệu của auth-service."""
from decimal import Decimal

from sqlalchemy import select

from common.db import SessionLocal

from .models import Account

ACCOUNTS = [
    # (account_id, user_id, balance)
    ("a0000001-0000-0000-0000-000000000001", "11111111-1111-1111-1111-111111111111", "50000000.00"),
    ("a0000002-0000-0000-0000-000000000002", "22222222-2222-2222-2222-222222222222", "20000000.00"),
    ("a0000003-0000-0000-0000-000000000003", "33333333-3333-3333-3333-333333333333", "15000000.00"),
    # Tài khoản số dư thấp, dùng để demo tình huống không đủ số dư.
    ("a0000004-0000-0000-0000-000000000004", "44444444-4444-4444-4444-444444444444", "1000000.00"),
    # Tài khoản bổ sung, khớp với người dùng bổ sung của auth-service.
    ("a0000005-0000-0000-0000-000000000005", "55555555-5555-5555-5555-555555555555", "30000000.00"),
    ("a0000006-0000-0000-0000-000000000006", "66666666-6666-6666-6666-666666666666", "25000000.00"),
    ("a0000007-0000-0000-0000-000000000007", "77777777-7777-7777-7777-777777777777", "18000000.00"),
    ("a0000008-0000-0000-0000-000000000008", "88888888-8888-8888-8888-888888888888", "40000000.00"),
    ("a0000009-0000-0000-0000-000000000009", "99999999-9999-9999-9999-999999999999", "22000000.00"),
    ("a0000010-0000-0000-0000-000000000010", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "12000000.00"),
]


def seed() -> None:
    # Chèn từng tài khoản còn thiếu, nên database đã có dữ liệu vẫn nhận thêm dòng mới.
    with SessionLocal() as db:
        existing = set(db.scalars(select(Account.id)))
        missing = [a for a in ACCOUNTS if a[0] not in existing]
        if not missing:
            return
        db.add_all(
            Account(id=aid, user_id=uid, balance=Decimal(bal), currency="VND")
            for aid, uid, bal in missing
        )
        db.commit()
