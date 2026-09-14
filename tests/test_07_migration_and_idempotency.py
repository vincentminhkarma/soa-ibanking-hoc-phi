"""Hai lớp bảo vệ không nhìn thấy được từ luồng nghiệp vụ thông thường.

1. Nâng cấp một database đã tồn tại lên bản có `processing_at`. Database demo
   hiện tại đã có sẵn cột nên không chứng minh được gì; test dựng lại schema cũ
   trong một schema PostgreSQL riêng rồi chạy đúng các câu lệnh migration thật.
2. Reference của sổ cái là UNIQUE toàn hệ thống. Dùng lại reference cho tài
   khoản / số tiền / chiều khác phải bị từ chối, không được báo replay thành
   công — nếu không job đối soát sẽ chốt "đã hoàn tiền" cho giao dịch chưa hoàn.
"""
import os
from decimal import Decimal

import httpx
import psycopg
from _loader import load_module
from conftest import ACCOUNT_URL, INTERNAL_HEADERS, Client, error_code

PAYMENT_DSN = os.getenv("PAYMENT_DSN", "postgresql://ibanking:ibanking@localhost:5433/paymentdb")

migrations = load_module("payment-service/app/migrations.py")

SCHEMA_CU = """
CREATE TABLE payments (
    id          TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
)
"""


def test_nang_cap_tu_database_chua_co_processing_at():
    """Bảng payments của bản cũ phải được thêm cột, đánh index và backfill."""
    with psycopg.connect(PAYMENT_DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS mig_check CASCADE")
        conn.execute("CREATE SCHEMA mig_check")
        conn.execute("SET search_path TO mig_check")   # migration chạy trên bảng dựng lại, không đụng dữ liệu thật
        try:
            conn.execute(SCHEMA_CU)
            conn.execute(
                "INSERT INTO payments VALUES "
                "('treo', 'PROCESSING', now() - interval '10 minutes'),"
                "('xong', 'SUCCESS', now())"
            )
            for sql in migrations.STATEMENTS:
                conn.execute(sql)

            moc = dict(conn.execute("SELECT id, processing_at FROM payments").fetchall())
            assert moc["treo"] is not None, "giao dịch PROCESSING cũ phải được backfill để job đối soát quét tới"
            assert moc["xong"] is None, "giao dịch đã kết thúc không được đụng tới"
            assert conn.execute(
                "SELECT 1 FROM pg_indexes WHERE schemaname = 'mig_check' "
                "AND indexname = 'ix_payments_processing_at'"
            ).fetchone(), "thiếu index cho cột processing_at"

            for sql in migrations.STATEMENTS:   # khởi động lại service: chạy lần hai vẫn phải sạch
                conn.execute(sql)
            assert dict(conn.execute("SELECT id, processing_at FROM payments").fetchall()) == moc
        finally:
            conn.execute("DROP SCHEMA mig_check CASCADE")


def _credit(user_id: str, amount: str, reference: str) -> httpx.Response:
    return httpx.post(
        f"{ACCOUNT_URL}/internal/accounts/{user_id}/credit",
        json={"amount": amount, "reference": reference, "description": "Kiểm thử idempotency"},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )


def _debit(user_id: str, amount: str, reference: str) -> httpx.Response:
    return httpx.post(
        f"{ACCOUNT_URL}/internal/accounts/{user_id}/debit",
        json={"amount": amount, "reference": reference, "description": "Kiểm thử idempotency"},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )


def test_replay_dung_noi_dung_thi_khong_ghi_so_lan_hai(alice: Client):
    """Gọi lại y hệt: trả kết quả cũ, số dư không nhúc nhích."""
    ref = f"idem-ok-{os.urandom(4).hex()}"
    dau = alice.balance()
    lan_1 = _credit(alice.user["id"], "100000.00", ref)
    lan_1.raise_for_status()
    lan_2 = _credit(alice.user["id"], "100000.00", ref)
    lan_2.raise_for_status()

    assert lan_2.json()["idempotent_replay"] is True
    assert lan_2.json()["ledger_id"] == lan_1.json()["ledger_id"]
    assert alice.balance() == dau + Decimal("100000.00")


def test_reference_cua_tai_khoan_khac_bi_tu_choi(alice: Client, bob: Client):
    """Reference đã thuộc về alice không được coi là đã hoàn tiền cho bob."""
    ref = f"idem-user-{os.urandom(4).hex()}"
    _credit(alice.user["id"], "100000.00", ref).raise_for_status()
    so_du_bob = bob.balance()

    resp = _credit(bob.user["id"], "100000.00", ref)

    assert resp.status_code == 409
    assert error_code(resp) == "REFERENCE_CONFLICT"
    assert bob.balance() == so_du_bob


def test_reference_trung_nhung_khac_so_tien_bi_tu_choi(alice: Client):
    ref = f"idem-amt-{os.urandom(4).hex()}"
    _credit(alice.user["id"], "100000.00", ref).raise_for_status()

    resp = _credit(alice.user["id"], "250000.00", ref)

    assert resp.status_code == 409
    assert error_code(resp) == "REFERENCE_CONFLICT"


def test_reference_trung_nhung_khac_chieu_bi_tu_choi(alice: Client):
    ref = f"idem-dir-{os.urandom(4).hex()}"
    _credit(alice.user["id"], "100000.00", ref).raise_for_status()
    dau = alice.balance()

    resp = _debit(alice.user["id"], "100000.00", ref)

    assert resp.status_code == 409
    assert error_code(resp) == "REFERENCE_CONFLICT"
    assert alice.balance() == dau
