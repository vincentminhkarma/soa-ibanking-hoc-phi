from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base

STATUS_UNPAID = "UNPAID"
STATUS_PAID = "PAID"


class Student(Base):
    __tablename__ = "students"

    student_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    program: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    faculty: Mapped[str] = mapped_column(String(120), nullable=False, default="")


class TuitionFee(Base):
    """Khoản học phí theo học kỳ.

    Ràng buộc chống thanh toán trùng:
      - (student_code, semester) UNIQUE: mỗi học kỳ chỉ một khoản học phí.
      - payment_ref UNIQUE: một giao dịch chỉ gạch nợ được một lần.
      - status chỉ nhận UNPAID/PAID; chuyển trạng thái luôn thực hiện trong
        transaction có SELECT ... FOR UPDATE (xem main.py).
    """

    __tablename__ = "tuition_fees"
    __table_args__ = (
        UniqueConstraint("student_code", "semester", name="uq_fee_student_semester"),
        CheckConstraint("amount > 0", name="ck_fee_amount_positive"),
        CheckConstraint("status IN ('UNPAID','PAID')", name="ck_fee_status"),
        Index("ix_fee_student_status", "student_code", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("students.student_code"), nullable=False, index=True
    )
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=STATUS_UNPAID)
    payment_ref: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "student_code": self.student_code,
            "semester": self.semester,
            "amount": self.amount,
            "status": self.status,
            "payment_ref": self.payment_ref,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }
