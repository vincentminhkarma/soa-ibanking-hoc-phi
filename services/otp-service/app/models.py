from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base

ACTIVE, USED, EXPIRED, REVOKED = "ACTIVE", "USED", "EXPIRED", "REVOKED"


class OtpCode(Base):
    """Mã OTP gắn với đúng một giao dịch.

    Hai partial unique index dưới đây hiện thực trực tiếp yêu cầu của đề bài:
      - uq_otp_active_payment: mỗi giao dịch chỉ có tối đa 1 OTP còn hiệu lực.
      - uq_otp_active_code: mã đang hiệu lực không trùng với giao dịch khác.
    Mã được lưu dạng SHA-256, không lưu plaintext.
    """

    __tablename__ = "otp_codes"
    __table_args__ = (
        Index(
            "uq_otp_active_payment",
            "payment_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "uq_otp_active_code",
            "code_hash",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=ACTIVE)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
