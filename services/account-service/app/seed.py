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
]


def seed() -> None:
    with SessionLocal() as db:
        if db.scalar(select(Account).limit(1)):
            return
        db.add_all(
            Account(id=aid, user_id=uid, balance=Decimal(bal), currency="VND")
            for aid, uid, bal in ACCOUNTS
        )
        db.commit()
