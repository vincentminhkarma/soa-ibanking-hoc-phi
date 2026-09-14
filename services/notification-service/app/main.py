"""notification-service — cổng ra duy nhất tới hệ thống email (external service).

Tách riêng để các service nghiệp vụ không phải biết gì về SMTP; muốn đổi sang
SendGrid/SES chỉ sửa ở đây.
"""
import logging
import smtplib
import uuid
from email.message import EmailMessage

from fastapi import Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from common.app import create_app
from common.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from common.db import get_session
from common.errors import APIError
from common.security import InternalOnly

from .models import EmailLog
from .templates import RENDERERS

log = logging.getLogger(__name__)

app = create_app("Notification Service", "Gửi email OTP và biên lai giao dịch qua SMTP.")


class SendEmailRequest(BaseModel):
    to: EmailStr
    template: str = Field(examples=["OTP", "RECEIPT"])
    data: dict = Field(default_factory=dict)


class SendEmailResponse(BaseModel):
    id: str
    status: str


def _send_smtp(to: str, subject: str, html: str, text: str) -> None:
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        if SMTP_USER:  # MailHog không cần auth; SMTP thật thì có.
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


@app.post(
    "/internal/notifications/email",
    response_model=SendEmailResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Gửi email theo template",
)
def send_email(req: SendEmailRequest, db: Session = Depends(get_session)) -> SendEmailResponse:
    renderer = RENDERERS.get(req.template)
    if not renderer:
        raise APIError(400, "UNKNOWN_TEMPLATE", f"Template không tồn tại: {req.template}")

    subject, html, text = renderer(req.data)
    row = EmailLog(id=str(uuid.uuid4()), to_email=req.to, subject=subject, template=req.template, status="SENT")
    try:
        _send_smtp(req.to, subject, html, text)
    except Exception as exc:
        row.status, row.error = "FAILED", str(exc)[:500]
        db.add(row)
        db.commit()
        log.error("gửi email thất bại to=%s err=%s", req.to, exc)
        raise APIError(502, "EMAIL_SEND_FAILED", "Không gửi được email, vui lòng thử lại.")

    db.add(row)
    db.commit()
    log.info("đã gửi email template=%s to=%s", req.template, req.to)
    return SendEmailResponse(id=row.id, status=row.status)


@app.get(
    "/internal/notifications",
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Nhật ký email đã gửi",
)
def list_emails(limit: int = 20, db: Session = Depends(get_session)) -> dict:
    rows = db.scalars(select(EmailLog).order_by(desc(EmailLog.created_at)).limit(min(limit, 100))).all()
    return {
        "items": [
            {
                "id": r.id,
                "to": r.to_email,
                "subject": r.subject,
                "template": r.template,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
