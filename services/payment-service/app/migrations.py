"""Nâng cấp schema cho database đã tồn tại.

`Base.metadata.create_all()` chỉ tạo bảng còn thiếu, KHÔNG thêm cột vào bảng đã
có. Nâng cấp lên bản có `processing_at` trên một volume PostgreSQL cũ vì vậy sẽ
lỗi `UndefinedColumn` ở mọi truy vấn payment. Các câu lệnh dưới đây idempotent
nên chạy được trên cả database mới lẫn database cũ, mỗi lần khởi động.
"""
from sqlalchemy import text

STATEMENTS = (
    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS processing_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_payments_processing_at ON payments (processing_at)",
    # Giao dịch PROCESSING từ bản cũ không có mốc thời gian nào khác ngoài
    # created_at; thiếu backfill thì chúng treo vĩnh viễn ngoài tầm đối soát.
    "UPDATE payments SET processing_at = created_at "
    "WHERE status = 'PROCESSING' AND processing_at IS NULL",
)


def migrate(engine) -> None:
    with engine.begin() as conn:
        for sql in STATEMENTS:
            conn.execute(text(sql))
