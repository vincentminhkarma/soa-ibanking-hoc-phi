from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base


class EmailLog(Base):
    """Nhật ký email đã gửi (audit).

    Không lưu nội dung email vì thân thư chứa mã OTP.
    """

    __tablename__ = "email_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    to_email: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # SENT | FAILED
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
