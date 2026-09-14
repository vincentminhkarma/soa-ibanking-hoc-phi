"""tuition-service — sở hữu dữ liệu sinh viên và công nợ học phí.

Tình huống concurrency 5.2 của đề bài (hai người cùng đóng một khoản học phí)
được xử lý ở `mark_paid`: khoá dòng học phí rồi mới đổi trạng thái, nên chỉ
giao dịch đầu tiên thành công, giao dịch sau nhận 409 TUITION_ALREADY_PAID.
"""
import logging
import os
import time
import uuid
from datetime import UTC, datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.app import create_app
from common.db import get_session
from common.errors import APIError
from common.security import CurrentUser, InternalOnly, current_user

from .models import STATUS_PAID, STATUS_UNPAID, Student, TuitionFee
from .schemas import (
    CreateFeeRequest,
    FeeItem,
    FeeStateResponse,
    PayFeeRequest,
    StudentInfo,
    TuitionLookupResponse,
)
from .seed import seed

log = logging.getLogger(__name__)

# Xem chú thích tương tự ở account-service: chỉ dùng để demo tranh chấp.
LOCK_HOLD_MS = int(os.getenv("LOCK_HOLD_MS", "0"))

app = create_app(
    "Tuition Service",
    "Tra cứu sinh viên, công nợ học phí và gạch nợ khi thanh toán thành công.",
    on_start=seed,
)


def _lock_fee(db: Session, fee_id: str) -> TuitionFee:
    fee = db.execute(select(TuitionFee).where(TuitionFee.id == fee_id).with_for_update()).scalar_one_or_none()
    if not fee:
        raise APIError(404, "FEE_NOT_FOUND", "Không tìm thấy khoản học phí.")
    if LOCK_HOLD_MS:
        time.sleep(LOCK_HOLD_MS / 1000)
    return fee


@app.get(
    "/api/v1/tuitions/{student_code}",
    response_model=TuitionLookupResponse,
    tags=["public"],
    summary="Tra cứu học phí theo MSSV",
    responses={404: {"description": "MSSV không tồn tại"}},
)
def lookup(
    student_code: str,
    _: CurrentUser = Depends(current_user),
    db: Session = Depends(get_session),
) -> TuitionLookupResponse:
    code = student_code.strip().upper()
    student = db.get(Student, code)
    if not student:
        raise APIError(404, "STUDENT_NOT_FOUND", f"Không tìm thấy sinh viên với MSSV {code}.")

    fees = db.scalars(
        select(TuitionFee).where(TuitionFee.student_code == code).order_by(TuitionFee.semester)
    ).all()
    outstanding = next((f for f in fees if f.status == STATUS_UNPAID), None)
    return TuitionLookupResponse(
        student=StudentInfo(
            student_code=student.student_code,
            full_name=student.full_name,
            program=student.program,
            faculty=student.faculty,
        ),
        outstanding_fee=FeeItem(**outstanding.as_dict()) if outstanding else None,
        fees=[FeeItem(**f.as_dict()) for f in fees],
    )


@app.get(
    "/internal/tuitions/students/{student_code}",
    response_model=TuitionLookupResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Tra cứu công nợ theo MSSV (service-to-service)",
)
def lookup_internal(student_code: str, db: Session = Depends(get_session)) -> TuitionLookupResponse:
    code = student_code.strip().upper()
    student = db.get(Student, code)
    if not student:
        raise APIError(404, "STUDENT_NOT_FOUND", f"Không tìm thấy sinh viên với MSSV {code}.")
    fees = db.scalars(select(TuitionFee).where(TuitionFee.student_code == code)).all()
    outstanding = next((f for f in fees if f.status == STATUS_UNPAID), None)
    return TuitionLookupResponse(
        student=StudentInfo(
            student_code=student.student_code,
            full_name=student.full_name,
            program=student.program,
            faculty=student.faculty,
        ),
        outstanding_fee=FeeItem(**outstanding.as_dict()) if outstanding else None,
        fees=[FeeItem(**f.as_dict()) for f in fees],
    )


@app.get(
    "/internal/tuitions/fees/{fee_id}",
    response_model=FeeItem,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Đọc khoản học phí (service-to-service)",
)
def read_fee(fee_id: str, db: Session = Depends(get_session)) -> FeeItem:
    fee = db.get(TuitionFee, fee_id)
    if not fee:
        raise APIError(404, "FEE_NOT_FOUND", "Không tìm thấy khoản học phí.")
    return FeeItem(**fee.as_dict())


@app.post(
    "/internal/tuitions/fees",
    response_model=FeeItem,
    status_code=201,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Tạo sinh viên/khoản học phí (admin, dùng cho vận hành và test tự động)",
)
def create_fee(req: CreateFeeRequest, db: Session = Depends(get_session)) -> FeeItem:
    code = req.student_code.strip().upper()
    if not db.get(Student, code):
        db.add(Student(student_code=code, full_name=req.full_name, program=req.program, faculty=req.faculty))
        db.flush()
    if db.scalar(
        select(TuitionFee).where(TuitionFee.student_code == code, TuitionFee.semester == req.semester)
    ):
        raise APIError(409, "FEE_ALREADY_EXISTS", "Khoản học phí của học kỳ này đã tồn tại.")

    fee = TuitionFee(id=str(uuid.uuid4()), student_code=code, semester=req.semester, amount=req.amount)
    db.add(fee)
    db.commit()
    return FeeItem(**fee.as_dict())


@app.post(
    "/internal/tuitions/fees/{fee_id}/pay",
    response_model=FeeStateResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Gạch nợ học phí — chỉ thành công một lần duy nhất",
    responses={409: {"description": "Khoản học phí đã được thanh toán bởi giao dịch khác"}},
)
def mark_paid(fee_id: str, req: PayFeeRequest, db: Session = Depends(get_session)) -> FeeStateResponse:
    fee = _lock_fee(db, fee_id)

    if fee.status == STATUS_PAID:
        if fee.payment_ref == req.payment_ref:
            # Cùng giao dịch gọi lại (retry) => idempotent, không coi là lỗi.
            return FeeStateResponse(fee=FeeItem(**fee.as_dict()), idempotent_replay=True)
        raise APIError(
            409,
            "TUITION_ALREADY_PAID",
            "Khoản học phí này đã được thanh toán.",
            {"paid_by_ref": fee.payment_ref, "paid_at": fee.paid_at.isoformat() if fee.paid_at else None},
        )

    fee.status = STATUS_PAID
    fee.payment_ref = req.payment_ref
    fee.paid_at = datetime.now(UTC)
    db.commit()
    log.info("gạch nợ học phí fee=%s ref=%s", fee_id, req.payment_ref)
    return FeeStateResponse(fee=FeeItem(**fee.as_dict()))


@app.post(
    "/internal/tuitions/fees/{fee_id}/revert",
    response_model=FeeStateResponse,
    tags=["internal"],
    dependencies=[InternalOnly],
    summary="Huỷ gạch nợ — bước bù trừ (compensation) của saga",
)
def revert(fee_id: str, req: PayFeeRequest, db: Session = Depends(get_session)) -> FeeStateResponse:
    fee = _lock_fee(db, fee_id)
    # Chỉ chủ nhân của lần gạch nợ mới được huỷ, tránh xoá nhầm giao dịch khác.
    if fee.status == STATUS_PAID and fee.payment_ref == req.payment_ref:
        fee.status = STATUS_UNPAID
        fee.payment_ref = None
        fee.paid_at = None
        db.commit()
        log.warning("huỷ gạch nợ fee=%s ref=%s", fee_id, req.payment_ref)
        return FeeStateResponse(fee=FeeItem(**fee.as_dict()))
    return FeeStateResponse(fee=FeeItem(**fee.as_dict()), idempotent_replay=True)
