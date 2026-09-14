"""account-service — sở hữu số dư và lịch sử giao dịch.

Điểm cốt lõi: mọi thay đổi số dư đều đi qua `_lock_account()` dùng
SELECT ... FOR UPDATE nên hai giao dịch đồng thời trên cùng một tài khoản bị
tuần tự hoá ở tầng database, không thể chi tiêu vượt số dư.
"""
import logging
import os
import time
import uuid
from decimal import Decimal

from fastapi import Depends
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from common.app import create_app
from common.db import get_session
from common.errors import APIError
from common.security import CurrentUser, InternalOnly, current_user

from .models import Account, LedgerEntry
from .schemas import (
    AccountResponse,
    MoveMoneyRequest,
    MoveMoneyResponse,
    TransactionHistory,
    TransactionItem,
)
from .seed import seed

log = logging.getLogger(__name__)

# Nới rộng cửa sổ tranh chấp để demo/test concurrency thấy rõ hiệu lực của khoá.
# Mặc định 0 (production). docker-compose đặt 150ms cho môi trường demo.
LOCK_HOLD_MS = int(os.getenv("LOCK_HOLD_MS", "0"))

app = create_app(
    "Account Service",
    "Quản lý số dư khả dụng và lịch sử giao dịch. Trừ/hoàn tiền an toàn với khoá dòng.",
    on_start=seed,
)


def _lock_account(db: Session, user_id: str) -> Account:
    """Lấy tài khoản kèm khoá độc quyền dòng; khoá giữ tới khi commit/rollback."""
    account = db.execute(
        select(Account).where(Account.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if not account:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Không tìm thấy tài khoản thanh toán.")
    if LOCK_HOLD_MS:
        time.sleep(LOCK_HOLD_MS / 1000)
    return account


def _replay_of(db: Session, account: Account, req: MoveMoneyRequest, direction: str) -> LedgerEntry | None:
    """Bút toán cũ được coi là replay chỉ khi trùng cả tài khoản, chiều lẫn số tiền.

    `reference` UNIQUE trên toàn hệ thống, nên tra theo mỗi reference có thể bắt
    trúng bút toán của tài khoản khác rồi báo thành công giả: job đối soát sẽ
    chốt "đã hoàn tiền" cho một giao dịch thực tế chưa hề được hoàn.
    """
    entry = db.scalar(select(LedgerEntry).where(LedgerEntry.reference == req.reference))
    if entry is None:
        return None
    if entry.account_id != account.id or entry.direction != direction or entry.amount != req.amount:
        raise APIError(
            409,
            "REFERENCE_CONFLICT",
            "Reference này đã thuộc về một bút toán khác, không thể dùng lại.",
            {"reference": req.reference},
        )
    return entry


def _apply(db: Session, user_id: str, req: MoveMoneyRequest, direction: str) -> MoveMoneyResponse:
    account = _lock_account(db, user_id)

    # Idempotency: cùng reference => trả lại kết quả cũ, không ghi sổ lần hai.
    existing = _replay_of(db, account, req, direction)
    if existing:
        return MoveMoneyResponse(
            ledger_id=existing.id, balance_after=existing.balance_after, idempotent_replay=True
        )

    amount = Decimal(req.amount)
    if direction == "DEBIT":
        if account.balance < amount:
            raise APIError(
                409,
                "INSUFFICIENT_FUNDS",
                "Số dư khả dụng không đủ để thực hiện giao dịch.",
                {"balance": str(account.balance), "required": str(amount)},
            )
        account.balance -= amount
    else:
        account.balance += amount

    entry = LedgerEntry(
        id=str(uuid.uuid4()),
        account_id=account.id,
        direction=direction,
        amount=amount,
        balance_after=account.balance,
        reference=req.reference,
        description=req.description,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        # Hai request cùng reference chạy song song: bản ghi kia đã thắng.
        db.rollback()
        existing = _replay_of(db, account, req, direction)
        if existing:
            return MoveMoneyResponse(
                ledger_id=existing.id, balance_after=existing.balance_after, idempotent_replay=True
            )
        raise
    log.info(
        "%s %s cho user=%s ref=%s, số dư còn %s",
        direction, amount, user_id, req.reference, account.balance,
    )
    return MoveMoneyResponse(ledger_id=entry.id, balance_after=entry.balance_after)


@app.get("/api/v1/accounts/me", response_model=AccountResponse, tags=["public"], summary="Số dư khả dụng")
def my_account(user: CurrentUser = Depends(current_user), db: Session = Depends(get_session)) -> AccountResponse:
    account = db.scalar(select(Account).where(Account.user_id == user.user_id))
    if not account:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Không tìm thấy tài khoản thanh toán.")
    return AccountResponse(
        account_id=account.id, user_id=account.user_id, balance=account.balance, currency=account.currency
    )


@app.get(
    "/api/v1/accounts/me/transactions",
    response_model=TransactionHistory,
    tags=["public"],
    summary="Lịch sử giao dịch",
)
def my_transactions(
    limit: int = 50,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_session),
) -> TransactionHistory:
    account = db.scalar(select(Account).where(Account.user_id == user.user_id))
    if not account:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Không tìm thấy tài khoản thanh toán.")
    rows = db.scalars(
        select(LedgerEntry)
        .where(LedgerEntry.account_id == account.id)
        .order_by(desc(LedgerEntry.created_at))
        .limit(min(limit, 200))
    ).all()
    total = db.scalar(select(func.count(LedgerEntry.id)).where(LedgerEntry.account_id == account.id)) or 0
    return TransactionHistory(items=[TransactionItem(**r.as_dict()) for r in rows], total=total)


@app.get(
    "/internal/accounts/{user_id}",
    response_model=AccountResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Đọc số dư (service-to-service)",
)
def read_account(user_id: str, db: Session = Depends(get_session)) -> AccountResponse:
    account = db.scalar(select(Account).where(Account.user_id == user_id))
    if not account:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Không tìm thấy tài khoản thanh toán.")
    return AccountResponse(
        account_id=account.id, user_id=account.user_id, balance=account.balance, currency=account.currency
    )


@app.get(
    "/internal/accounts/{user_id}/entries/{reference}",
    response_model=TransactionItem,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Tra bút toán theo reference — dùng cho đối soát giao dịch treo",
    responses={404: {"description": "Chưa có bút toán nào với reference này"}},
)
def read_entry(user_id: str, reference: str, db: Session = Depends(get_session)) -> TransactionItem:
    entry = db.scalar(
        select(LedgerEntry)
        .join(Account, LedgerEntry.account_id == Account.id)
        .where(Account.user_id == user_id, LedgerEntry.reference == reference)
    )
    if not entry:
        raise APIError(404, "ENTRY_NOT_FOUND", "Không tìm thấy bút toán với reference này.")
    return TransactionItem(**entry.as_dict())


@app.post(
    "/internal/accounts/{user_id}/debit",
    response_model=MoveMoneyResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Trừ tiền (idempotent theo reference)",
)
def debit(user_id: str, req: MoveMoneyRequest, db: Session = Depends(get_session)) -> MoveMoneyResponse:
    return _apply(db, user_id, req, "DEBIT")


@app.post(
    "/internal/accounts/{user_id}/credit",
    response_model=MoveMoneyResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Hoàn tiền — bước bù trừ (compensation) của saga",
)
def credit(user_id: str, req: MoveMoneyRequest, db: Session = Depends(get_session)) -> MoveMoneyResponse:
    return _apply(db, user_id, req, "CREDIT")
