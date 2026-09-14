"""payment-service — điều phối (orchestrator) toàn bộ luồng thanh toán học phí.

Giao dịch trải trên 3 service nên không thể dùng một transaction ACID duy nhất.
Ở đây dùng **saga có bù trừ**: mỗi bước là một transaction cục bộ, nếu bước sau
hỏng thì chạy bước bù trừ cho bước trước.

    trừ tiền (account-service)  ->  gạch nợ (tuition-service)  ->  SUCCESS
            |                              |
            |                              +-- lỗi ==> hoàn tiền (compensation)
            +-- lỗi ==> giao dịch FAILED, không đụng tới học phí

Trừ tiền trước vì tiền là tài nguyên khan hiếm và có thể hoàn lại an toàn;
mọi lời gọi đều idempotent theo `reference = payment_id` nên retry không gây
trừ tiền hai lần.
"""
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import Depends, Header
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from common.app import create_app
from common.config import (
    ACCOUNT_SERVICE_URL,
    NOTIFICATION_SERVICE_URL,
    OTP_SERVICE_URL,
    TUITION_SERVICE_URL,
)
from common.db import get_session
from common.errors import APIError
from common.http import call_service
from common.observability import get_request_id
from common.security import CurrentUser, current_user

from .models import FAILED, PENDING_OTP, PROCESSING, SUCCESS, Payment, PaymentEvent
from .schemas import (
    ConfirmPaymentRequest,
    CreatePaymentRequest,
    CreatePaymentResponse,
    PaymentEventItem,
    PaymentListResponse,
    PaymentResponse,
)

log = logging.getLogger(__name__)

app = create_app(
    "Payment Service",
    "Điều phối luồng thanh toán học phí: kiểm tra công nợ, OTP, trừ tiền, gạch nợ, biên lai.",
)


# --------------------------------------------------------------------------- helpers
def _event(db: Session, payment_id: str, step: str, status: str, detail: str | None = None) -> None:
    db.add(
        PaymentEvent(
            id=str(uuid.uuid4()),
            payment_id=payment_id,
            step=step,
            status=status,
            detail=detail,
            request_id=get_request_id(),
        )
    )
    db.commit()


def _fail(db: Session, payment: Payment, code: str, reason: str) -> None:
    payment.status = FAILED
    payment.failure_code = code
    payment.failure_reason = reason[:255]
    payment.completed_at = datetime.now(UTC)
    db.commit()
    log.warning("giao dịch thất bại payment=%s code=%s", payment.id, code)


def _response(payment: Payment) -> PaymentResponse:
    return PaymentResponse(**payment.as_dict())


def _owned(db: Session, payment_id: str, user: CurrentUser, lock: bool = False) -> Payment:
    stmt = select(Payment).where(Payment.id == payment_id)
    if lock:
        # populate_existing bắt buộc: nếu payment đã nằm trong identity map từ lần
        # đọc trước, SQLAlchemy sẽ trả lại object cũ và ta kiểm tra trạng thái cũ
        # dù vừa khoá được dòng. Ép nạp lại giá trị mới nhất từ database.
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    payment = db.execute(stmt).scalar_one_or_none()
    if not payment:
        raise APIError(404, "PAYMENT_NOT_FOUND", "Không tìm thấy giao dịch.")
    if payment.payer_user_id != user.user_id:
        raise APIError(403, "FORBIDDEN", "Bạn không có quyền truy cập giao dịch này.")
    return payment


def _issue_otp(db: Session, payment: Payment) -> dict:
    otp = call_service(
        "POST",
        f"{OTP_SERVICE_URL}/internal/otp/issue",
        json={
            "payment_id": payment.id,
            "email": payment.payer_email,
            "recipient_name": payment.payer_name,
            "student_code": payment.student_code,
            "student_name": payment.student_name,
            "amount": float(payment.amount),
        },
    )
    payment.otp_expires_at = datetime.fromisoformat(otp["expires_at"])
    db.commit()
    _event(db, payment.id, "OTP_ISSUED", "OK", f"hết hạn {otp['expires_at']}")
    return otp


# --------------------------------------------------------------------------- API
@app.post(
    "/api/v1/payments",
    response_model=CreatePaymentResponse,
    status_code=201,
    tags=["public"],
    summary="Khởi tạo giao dịch thanh toán học phí và gửi OTP",
    responses={
        409: {"description": "Học phí đã thanh toán / không có công nợ / số dư không đủ"},
        404: {"description": "MSSV không tồn tại"},
    },
)
def create_payment(
    req: CreatePaymentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_session),
) -> CreatePaymentResponse:
    if not req.accept_terms:
        raise APIError(400, "TERMS_NOT_ACCEPTED", "Bạn phải đồng ý với điều khoản giao dịch.")

    if idempotency_key:
        existing = db.scalar(
            select(Payment).where(
                Payment.payer_user_id == user.user_id, Payment.idempotency_key == idempotency_key
            )
        )
        if existing:
            # Client gửi lại cùng Idempotency-Key: trả về giao dịch cũ, không tạo mới.
            return CreatePaymentResponse(
                payment=_response(existing), otp_sent_to="", otp_ttl_seconds=0
            )

    lookup = call_service("GET", f"{TUITION_SERVICE_URL}/internal/tuitions/students/{req.student_code}")
    fee = lookup.get("outstanding_fee")
    if not fee:
        raise APIError(
            409,
            "NO_OUTSTANDING_TUITION",
            f"Sinh viên {lookup['student']['student_code']} không còn khoản học phí cần thanh toán.",
        )

    amount = Decimal(str(fee["amount"]))
    account = call_service("GET", f"{ACCOUNT_SERVICE_URL}/internal/accounts/{user.user_id}")
    if Decimal(str(account["balance"])) < amount:
        raise APIError(
            409,
            "INSUFFICIENT_FUNDS",
            "Số dư khả dụng không đủ để thanh toán khoản học phí này.",
            {"balance": account["balance"], "required": str(amount)},
        )

    payment = Payment(
        id=str(uuid.uuid4()),
        payer_user_id=user.user_id,
        payer_name=user.full_name,
        payer_email=user.email,
        payer_phone=user.phone,
        student_code=lookup["student"]["student_code"],
        student_name=lookup["student"]["full_name"],
        fee_id=fee["id"],
        semester=fee["semester"],
        amount=amount,
        status=PENDING_OTP,
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    db.commit()
    _event(db, payment.id, "PAYMENT_CREATED", "OK", f"fee={fee['id']} amount={amount}")

    otp = _issue_otp(db, payment)
    return CreatePaymentResponse(
        payment=_response(payment),
        otp_sent_to=otp["email_masked"],
        otp_ttl_seconds=otp["ttl_seconds"],
    )


@app.post(
    "/api/v1/payments/{payment_id}/otp/resend",
    response_model=CreatePaymentResponse,
    tags=["public"],
    summary="Gửi lại mã OTP cho giao dịch",
)
def resend_otp(
    payment_id: str,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_session),
) -> CreatePaymentResponse:
    payment = _owned(db, payment_id, user)
    if payment.status != PENDING_OTP:
        raise APIError(409, "PAYMENT_NOT_PENDING", "Giao dịch không ở trạng thái chờ xác thực OTP.")
    otp = _issue_otp(db, payment)
    return CreatePaymentResponse(
        payment=_response(payment), otp_sent_to=otp["email_masked"], otp_ttl_seconds=otp["ttl_seconds"]
    )


@app.post(
    "/api/v1/payments/{payment_id}/confirm",
    response_model=PaymentResponse,
    tags=["public"],
    summary="Xác thực OTP và thực hiện giao dịch",
    responses={
        400: {"description": "OTP sai/hết hạn/đã dùng"},
        409: {"description": "Số dư không đủ, học phí đã được người khác thanh toán"},
    },
)
def confirm_payment(
    payment_id: str,
    req: ConfirmPaymentRequest,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_session),
) -> PaymentResponse:
    payment = _owned(db, payment_id, user)
    if payment.status == SUCCESS:
        return _response(payment)  # xác nhận lại giao dịch đã thành công: idempotent
    if payment.status == FAILED:
        raise APIError(409, "PAYMENT_FAILED", payment.failure_reason or "Giao dịch đã thất bại.")
    if payment.status == PROCESSING:
        raise APIError(409, "PAYMENT_IN_PROGRESS", "Giao dịch đang được xử lý.")

    # Bước 1 — OTP. otp-service đảm bảo mã chỉ dùng được một lần, nên hai request
    # xác nhận song song cho cùng giao dịch thì chỉ một request đi tiếp được.
    call_service(
        "POST", f"{OTP_SERVICE_URL}/internal/otp/verify", json={"payment_id": payment.id, "code": req.otp_code}
    )
    _event(db, payment.id, "OTP_VERIFIED", "OK")

    # Bước 2 — chốt trạng thái PROCESSING dưới khoá dòng để chặn xác nhận trùng.
    payment = _owned(db, payment_id, user, lock=True)
    if payment.status != PENDING_OTP:
        raise APIError(409, "PAYMENT_IN_PROGRESS", "Giao dịch đang được xử lý hoặc đã kết thúc.")
    payment.status = PROCESSING
    db.commit()

    # Bước 3 — trừ tiền (idempotent theo reference = payment_id).
    try:
        debit = call_service(
            "POST",
            f"{ACCOUNT_SERVICE_URL}/internal/accounts/{payment.payer_user_id}/debit",
            json={
                "amount": str(payment.amount),
                "reference": payment.id,
                "description": f"Thanh toán học phí {payment.semester} - MSSV {payment.student_code}",
            },
        )
    except APIError as exc:
        _event(db, payment.id, "DEBIT", "FAILED", exc.message)
        _fail(db, payment, exc.code, exc.message)
        raise
    _event(db, payment.id, "DEBIT", "OK", f"số dư còn {debit['balance_after']}")

    # Bước 4 — gạch nợ học phí. Thất bại ở đây phải hoàn tiền cho người nộp.
    try:
        call_service(
            "POST",
            f"{TUITION_SERVICE_URL}/internal/tuitions/fees/{payment.fee_id}/pay",
            json={"payment_ref": payment.id},
        )
    except APIError as exc:
        _event(db, payment.id, "MARK_TUITION_PAID", "FAILED", exc.message)
        call_service(
            "POST",
            f"{ACCOUNT_SERVICE_URL}/internal/accounts/{payment.payer_user_id}/credit",
            json={
                "amount": str(payment.amount),
                "reference": f"{payment.id}:refund",
                "description": f"Hoàn tiền giao dịch {payment.id} - {exc.message}",
            },
        )
        _event(db, payment.id, "REFUND", "COMPENSATED", "đã hoàn tiền do gạch nợ thất bại")
        _fail(db, payment, exc.code, exc.message)
        raise
    _event(db, payment.id, "MARK_TUITION_PAID", "OK")

    # Bước 5 — kết thúc giao dịch.
    payment.status = SUCCESS
    payment.balance_after = Decimal(str(debit["balance_after"]))
    payment.completed_at = datetime.now(UTC)
    db.commit()
    _event(db, payment.id, "PAYMENT_COMPLETED", "OK")

    # Bước 6 — biên lai. Email hỏng không được phép làm hỏng giao dịch đã thành công.
    try:
        call_service(
            "POST",
            f"{NOTIFICATION_SERVICE_URL}/internal/notifications/email",
            json={
                "to": payment.payer_email,
                "template": "RECEIPT",
                "data": {
                    "payment_id": payment.id,
                    "payer_name": payment.payer_name,
                    "student_code": payment.student_code,
                    "student_name": payment.student_name,
                    "semester": payment.semester,
                    "amount": float(payment.amount),
                    "balance_after": float(payment.balance_after or 0),
                    "completed_at": payment.completed_at.strftime("%d/%m/%Y %H:%M:%S UTC"),
                },
            },
        )
        _event(db, payment.id, "RECEIPT_EMAIL", "OK")
    except APIError as exc:
        log.error("không gửi được biên lai payment=%s err=%s", payment.id, exc.message)
        _event(db, payment.id, "RECEIPT_EMAIL", "FAILED", exc.message)

    return _response(payment)


@app.get("/api/v1/payments/{payment_id}", response_model=PaymentResponse, tags=["public"], summary="Chi tiết giao dịch")
def get_payment(
    payment_id: str, user: CurrentUser = Depends(current_user), db: Session = Depends(get_session)
) -> PaymentResponse:
    return _response(_owned(db, payment_id, user))


@app.get(
    "/api/v1/payments/{payment_id}/events",
    response_model=list[PaymentEventItem],
    tags=["public"],
    summary="Nhật ký các bước xử lý của giao dịch (saga trace)",
)
def get_events(
    payment_id: str, user: CurrentUser = Depends(current_user), db: Session = Depends(get_session)
) -> list[PaymentEventItem]:
    _owned(db, payment_id, user)
    rows = db.scalars(
        select(PaymentEvent).where(PaymentEvent.payment_id == payment_id).order_by(PaymentEvent.created_at)
    ).all()
    return [
        PaymentEventItem(
            step=r.step,
            status=r.status,
            detail=r.detail,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]


@app.get(
    "/api/v1/payments",
    response_model=PaymentListResponse,
    tags=["public"],
    summary="Lịch sử giao dịch thanh toán học phí của người dùng",
)
def list_payments(
    limit: int = 20,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_session),
) -> PaymentListResponse:
    rows = db.scalars(
        select(Payment)
        .where(Payment.payer_user_id == user.user_id)
        .order_by(desc(Payment.created_at))
        .limit(min(limit, 100))
    ).all()
    total = db.scalar(select(func.count(Payment.id)).where(Payment.payer_user_id == user.user_id)) or 0
    return PaymentListResponse(items=[_response(r) for r in rows], total=total)
