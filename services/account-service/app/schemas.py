from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    account_id: str
    user_id: str
    balance: Decimal
    currency: str


class TransactionItem(BaseModel):
    id: str
    direction: str
    amount: Decimal
    balance_after: Decimal
    reference: str
    description: str
    created_at: datetime | None


class TransactionHistory(BaseModel):
    items: list[TransactionItem]
    total: int


class MoveMoneyRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2, examples=["9500000.00"])
    reference: str = Field(min_length=6, max_length=80, description="Khoá idempotency, thường là payment_id")
    description: str = Field(default="", max_length=255)


class MoveMoneyResponse(BaseModel):
    ledger_id: str
    balance_after: Decimal
    idempotent_replay: bool = False
