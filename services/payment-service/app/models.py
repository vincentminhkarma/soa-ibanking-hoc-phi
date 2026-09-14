from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base

PENDING_OTP = "PENDING_OTP"
PROCESSING = "PROCESSING"
SUCCESS = "SUCCESS"
FAILED = "FAILED"
STATUSES = (PENDING_OTP, PROCESSING, SUCCESS, FAILED)


class Payment(Base):
    """Giao dịch thanh toán học phí (saga orchestrator state).

    `uq_payment_success_fee` là partial unique index: tối đa MỘT giao dịch
    SUCCESS cho mỗi khoản học phí — lớp bảo vệ thứ hai bên cạnh khoá dòng ở
    tuition-service.
    """

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("payer_user_id", "idempotency_key", name="uq_payment_idempotency"),
        CheckConstraint(f"status IN {STATUSES}", name="ck_payment_status"),
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        Index("uq_payment_success_fee", "fee_id", unique=True, postgresql_where=text("status = 'SUCCESS'")),
        Index("ix_payment_user_created", "payer_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payer_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    payer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    payer_email: Mapped[str] = mapped_column(String(160), nullable=False)
    payer_phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")

    student_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    student_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    fee_id: Mapped[str] = mapped_column(String(36), nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    status: Mapped[str] = mapped_column(String(15), nullable=False, default=PENDING_OTP, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Thời điểm vào PROCESSING — job đối soát dựa vào đây để biết giao dịch treo
    # bao lâu, thay vì created_at (người dùng có thể ngồi nhập OTP rất lâu).
    processing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "payer": {"name": self.payer_name, "email": self.payer_email, "phone": self.payer_phone},
            "student_code": self.student_code,
            "student_name": self.student_name,
            "fee_id": self.fee_id,
            "semester": self.semester,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "failure_code": self.failure_code,
            "failure_reason": self.failure_reason,
            "otp_expires_at": self.otp_expires_at.isoformat() if self.otp_expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class PaymentEvent(Base):
    """Nhật ký từng bước của saga — phục vụ trace và giải thích khi demo."""

    __tablename__ = "payment_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payment_id: Mapped[str] = mapped_column(String(36), ForeignKey("payments.id"), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # OK | FAILED | COMPENSATED
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str] = mapped_column(String(40), nullable=False, default="-")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
