"""Kết nối database. Mỗi service sở hữu một database riêng (database-per-service)."""
import logging
import time
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=20,
    # Mỗi transaction đọc/ghi tiền bạc đều dùng SELECT ... FOR UPDATE nên
    # READ COMMITTED là đủ; xem docs/04-transaction-concurrency.md.
    isolation_level="READ COMMITTED",
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: một session cho mỗi request."""
    with SessionLocal() as session:
        yield session


def wait_for_db(timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover - chỉ chạy lúc khởi động
            if time.time() > deadline:
                raise
            log.warning("database chưa sẵn sàng (%s), thử lại...", exc)
            time.sleep(2)
