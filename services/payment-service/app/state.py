"""Thao tác chuyển trạng thái giao dịch, dùng chung cho luồng chính và job đối soát."""
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from common.observability import get_request_id

from .models import FAILED, SUCCESS, Payment, PaymentEvent

log = logging.getLogger(__name__)


def record_event(db: Session, payment_id: str, step: str, status: str, detail: str | None = None) -> None:
    db.add(
        PaymentEvent(
            id=str(uuid.uuid4()),
            payment_id=payment_id,
            step=step,
            status=status,
            detail=detail,
            request_id=get_request_id(),
            created_at=datetime.now(UTC),
        )
    )
    db.flush()


def mark_failed(db: Session, payment: Payment, code: str, reason: str) -> None:
    payment.status = FAILED
    payment.failure_code = code
    payment.failure_reason = reason[:255]
    payment.completed_at = datetime.now(UTC)
    db.flush()
    log.warning("giao dịch thất bại payment=%s code=%s", payment.id, code)


def mark_success(db: Session, payment: Payment, balance_after: Decimal | None) -> None:
    payment.status = SUCCESS
    payment.balance_after = balance_after
    payment.completed_at = datetime.now(UTC)
    db.flush()
