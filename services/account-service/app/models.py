from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base


class Account(Base):
    """Tài khoản thanh toán. CHECK balance >= 0 là chốt chặn cuối ở tầng database."""

    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("balance >= 0", name="ck_accounts_balance_non_negative"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="VND")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LedgerEntry(Base):
    """Lịch sử giao dịch (sổ cái).

    `reference` UNIQUE là cơ chế idempotency: payment-service retry cùng một
    reference sẽ không bị trừ tiền hai lần.
    """

    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # DEBIT | CREDIT
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reference: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "direction": self.direction,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "reference": self.reference,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
