"""otp-service — sinh, gửi và xác thực OTP một lần dùng.

Quy tắc theo đề bài: OTP gắn với một giao dịch, không trùng OTP đang hiệu lực
của giao dịch khác, hạn 5 phút, chỉ dùng thành công một lần.
"""
import hashlib
import logging
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from common.app import create_app
from common.config import NOTIFICATION_SERVICE_URL, OTP_MAX_ATTEMPTS, OTP_TTL_SECONDS
from common.db import get_session
from common.errors import APIError
from common.http import call_service
from common.security import InternalOnly

from .models import ACTIVE, EXPIRED, REVOKED, USED, OtpCode

log = logging.getLogger(__name__)

# Pepper: băm mã theo chính mã (không trộn payment_id) để index unique trên
# code_hash thực sự chặn được trùng mã giữa các giao dịch đang hiệu lực.
OTP_PEPPER = os.getenv("OTP_PEPPER", "tdtu-ibanking-pepper")

app = create_app("OTP Service", "Sinh, gửi qua email và xác thực mã OTP dùng một lần.")


class IssueOtpRequest(BaseModel):
    payment_id: str
    email: EmailStr
    recipient_name: str = ""
    student_code: str = ""
    student_name: str = ""
    amount: float = 0


class IssueOtpResponse(BaseModel):
    otp_id: str
    expires_at: datetime
    ttl_seconds: int
    email_masked: str


class VerifyOtpRequest(BaseModel):
    payment_id: str
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerifyOtpResponse(BaseModel):
    verified: bool


def _hash(code: str) -> str:
    return hashlib.sha256((OTP_PEPPER + code).encode()).hexdigest()


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    keep = name[:2] if len(name) > 2 else name[:1]
    return f"{keep}{'*' * max(len(name) - len(keep), 3)}@{domain}"


def _now() -> datetime:
    return datetime.now(UTC)


@app.post(
    "/internal/otp/issue",
    response_model=IssueOtpResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Sinh OTP mới cho giao dịch và gửi qua email",
)
def issue(req: IssueOtpRequest, db: Session = Depends(get_session)) -> IssueOtpResponse:
    # Phát hành lại (resend) sẽ vô hiệu hoá mã cũ của chính giao dịch này.
    # Commit ngay: nếu để chung transaction với vòng lặp sinh mã bên dưới, một
    # lần IntegrityError sẽ rollback luôn cả việc thu hồi mã cũ.
    for old in db.scalars(
        select(OtpCode).where(OtpCode.payment_id == req.payment_id, OtpCode.status == ACTIVE).with_for_update()
    ).all():
        old.status = REVOKED
    db.commit()

    expires_at = _now() + timedelta(seconds=OTP_TTL_SECONDS)
    for _ in range(10):  # thử lại nếu mã đụng OTP đang hiệu lực của giao dịch khác
        code = f"{secrets.randbelow(1_000_000):06d}"
        row = OtpCode(
            id=str(uuid.uuid4()),
            payment_id=req.payment_id,
            code_hash=_hash(code),
            status=ACTIVE,
            expires_at=expires_at,
        )
        db.add(row)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
    else:
        raise APIError(503, "OTP_GENERATION_FAILED", "Không sinh được mã OTP, vui lòng thử lại.")

    try:
        call_service(
            "POST",
            f"{NOTIFICATION_SERVICE_URL}/internal/notifications/email",
            json={
                "to": req.email,
                "template": "OTP",
                "data": {
                    "otp_code": code,
                    "payment_id": req.payment_id,
                    "recipient_name": req.recipient_name,
                    "student_code": req.student_code,
                    "student_name": req.student_name,
                    "amount": req.amount,
                    "ttl_minutes": OTP_TTL_SECONDS // 60,
                },
            },
        )
    except APIError:
        row.status = REVOKED  # không gửi được mail thì mã vừa sinh vô giá trị
        db.commit()
        raise

    log.info("phát hành OTP payment=%s hết hạn=%s", req.payment_id, expires_at.isoformat())
    return IssueOtpResponse(
        otp_id=row.id,
        expires_at=expires_at,
        ttl_seconds=OTP_TTL_SECONDS,
        email_masked=_mask(req.email),
    )


@app.post(
    "/internal/otp/verify",
    response_model=VerifyOtpResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Xác thực OTP (dùng một lần)",
    responses={400: {"description": "OTP sai, hết hạn hoặc đã sử dụng"}},
)
def verify(req: VerifyOtpRequest, db: Session = Depends(get_session)) -> VerifyOtpResponse:
    row = db.execute(
        select(OtpCode)
        .where(OtpCode.payment_id == req.payment_id, OtpCode.status == ACTIVE)
        .with_for_update()
    ).scalar_one_or_none()

    if not row:
        raise APIError(400, "OTP_NOT_FOUND", "Không có mã OTP hiệu lực cho giao dịch này. Vui lòng gửi lại mã.")

    if row.expires_at < _now():
        row.status = EXPIRED
        db.commit()
        raise APIError(400, "OTP_EXPIRED", "Mã OTP đã hết hạn. Vui lòng yêu cầu mã mới.")

    row.attempts += 1
    if row.code_hash != _hash(req.code):
        remaining = OTP_MAX_ATTEMPTS - row.attempts
        if remaining <= 0:
            row.status = REVOKED
            db.commit()
            raise APIError(400, "OTP_LOCKED", "Nhập sai quá số lần cho phép. Vui lòng yêu cầu mã OTP mới.")
        db.commit()
        raise APIError(400, "OTP_INVALID", "Mã OTP không đúng.", {"remaining_attempts": remaining})

    # Đánh dấu đã dùng ngay trong transaction đang giữ khoá => không thể dùng lại.
    row.status = USED
    row.used_at = _now()
    db.commit()
    log.info("xác thực OTP thành công payment=%s", req.payment_id)
    return VerifyOtpResponse(verified=True)


@app.get(
    "/internal/otp/{payment_id}/status",
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Trạng thái OTP hiện tại của giao dịch",
)
def status(payment_id: str, db: Session = Depends(get_session)) -> dict:
    row = db.scalar(
        select(OtpCode).where(OtpCode.payment_id == payment_id).order_by(OtpCode.created_at.desc()).limit(1)
    )
    if not row:
        raise APIError(404, "OTP_NOT_FOUND", "Giao dịch chưa phát hành OTP.")
    return {
        "status": row.status,
        "attempts": row.attempts,
        "expires_at": row.expires_at.isoformat(),
        "expired": row.expires_at < _now(),
    }
