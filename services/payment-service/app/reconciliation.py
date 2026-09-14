"""Đối soát PROCESSING từ công nợ và sổ cái của các service sở hữu dữ liệu."""
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from opentelemetry import trace
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from common.config import ACCOUNT_SERVICE_URL, TUITION_SERVICE_URL
from common.db import SessionLocal
from common.errors import APIError
from common.http import call_service

from .decisions import COMPLETE, REFUND_AND_FAIL, REVERT_AND_FAIL, decide
from .models import PROCESSING, Payment
from .state import mark_failed, mark_success, record_event

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
STUCK_AFTER_SECONDS = int(os.getenv("RECONCILE_STUCK_AFTER_SECONDS", "60"))
INTERVAL_SECONDS = int(os.getenv("RECONCILE_INTERVAL_SECONDS", "30"))

# processing_at NULL (dòng do bản cũ ghi trong lúc nâng cấp cuốn chiếu) sẽ bị mọi
# so sánh `<` loại bỏ và treo vĩnh viễn — lùi về created_at để vẫn quét được.
_STUCK_SINCE = func.coalesce(Payment.processing_at, Payment.created_at)


@dataclass
class ReconcileReport:
    scanned: int = 0
    resolved: list[dict] = field(default_factory=list)


def _read_entry(payment: Payment, reference: str, direction: str) -> dict | None:
    try:
        entry = call_service(
            "GET",
            f"{ACCOUNT_SERVICE_URL}/internal/accounts/{payment.payer_user_id}/entries/{reference}",
        )
    except APIError as exc:
        if exc.code == "ENTRY_NOT_FOUND":
            return None
        raise
    if (entry["reference"] != reference or entry["direction"] != direction
            or Decimal(str(entry["amount"])) != payment.amount):
        raise APIError(409, "LEDGER_MISMATCH", "Bút toán không khớp giao dịch, cần kiểm tra thủ công.")
    return entry


def resolve(db: Session, payment: Payment) -> str:
    fee = call_service("GET", f"{TUITION_SERVICE_URL}/internal/tuitions/fees/{payment.fee_id}")
    if fee["id"] != payment.fee_id or Decimal(str(fee["amount"])) != payment.amount:
        raise APIError(409, "FEE_MISMATCH", "Khoản học phí không khớp giao dịch.")
    debit = _read_entry(payment, payment.id, "DEBIT")
    refund = _read_entry(payment, f"{payment.id}:refund", "CREDIT")
    if refund and not debit:
        raise APIError(409, "LEDGER_MISMATCH", "Có hoàn tiền nhưng thiếu bút toán trừ tiền.")
    action = decide(payment.id, fee["status"], fee.get("payment_ref"), debit is not None, refund is not None)
    trace.get_current_span().set_attribute("reconciliation.action", action)
    record_event(db, payment.id, "RECONCILE", "OK", f"hành động: {action}")

    if action == COMPLETE:
        mark_success(db, payment, Decimal(str(debit["balance_after"])))
        record_event(db, payment.id, "PAYMENT_COMPLETED", "OK", "hoàn tất bởi job đối soát")
    elif action == REFUND_AND_FAIL:
        call_service(
            "POST",
            f"{ACCOUNT_SERVICE_URL}/internal/accounts/{payment.payer_user_id}/credit",
            json={
                "amount": str(payment.amount),
                "reference": f"{payment.id}:refund",
                "description": f"Hoàn tiền giao dịch treo {payment.id} (đối soát tự động)",
            },
        )
        record_event(db, payment.id, "REFUND", "COMPENSATED", "hoàn tiền bởi job đối soát")
        mark_failed(db, payment, "RECONCILED_REFUND", "Giao dịch gián đoạn giữa chừng, đã hoàn tiền.")
    elif action == REVERT_AND_FAIL:
        call_service(
            "POST",
            f"{TUITION_SERVICE_URL}/internal/tuitions/fees/{payment.fee_id}/revert",
            json={"payment_ref": payment.id},
        )
        record_event(db, payment.id, "REVERT_TUITION", "COMPENSATED", "huỷ gạch nợ bởi job đối soát")
        mark_failed(db, payment, "RECONCILED_REVERT", "Đã huỷ gạch nợ vì chưa trừ tiền hoặc đã hoàn tiền.")
    elif refund:
        mark_failed(db, payment, "RECONCILED_REFUND", "Đã hoàn tiền trước khi đối soát.")
    else:
        mark_failed(db, payment, "RECONCILED_FAIL", "Giao dịch gián đoạn trước khi trừ tiền.")
    return action


def reconcile_once(db: Session, stuck_after_seconds: int | None = None) -> ReconcileReport:
    threshold = datetime.now(UTC) - timedelta(
        seconds=STUCK_AFTER_SECONDS if stuck_after_seconds is None else stuck_after_seconds
    )
    candidates = list(db.scalars(
        select(Payment.id).where(Payment.status == PROCESSING, _STUCK_SINCE < threshold)
    ))
    db.rollback()
    report = ReconcileReport()
    for payment_id in candidates:
        try:
            payment = db.scalar(
                select(Payment)
                .where(Payment.id == payment_id, Payment.status == PROCESSING, _STUCK_SINCE < threshold)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            if payment is None:
                db.rollback()
                continue
            report.scanned += 1
            with tracer.start_as_current_span("payment.reconcile", attributes={"payment.id": payment_id}):
                action = resolve(db, payment)
                db.commit()
            report.resolved.append({"payment_id": payment_id, "action": action})
            log.warning("đối soát payment=%s -> %s", payment_id, action)
        except (APIError, SQLAlchemyError) as exc:
            db.rollback()
            log.error("đối soát thất bại payment=%s err=%s", payment_id, exc)
    return report


def start_background_reconciler() -> None:
    def loop() -> None:
        while True:
            time.sleep(INTERVAL_SECONDS)
            try:
                with SessionLocal() as db:
                    report = reconcile_once(db)
                    if report.resolved:
                        log.warning("job đối soát xử lý %d giao dịch treo", len(report.resolved))
            except Exception:
                log.exception("vòng đối soát lỗi")

    threading.Thread(target=loop, name="reconciler", daemon=True).start()
    log.info("job đối soát chạy mỗi %ds, ngưỡng treo %ds", INTERVAL_SECONDS, STUCK_AFTER_SECONDS)
