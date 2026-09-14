"""Sinh viên và học phí mẫu của HK1/2026-2027."""
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from common.db import SessionLocal

from .models import STATUS_PAID, STATUS_UNPAID, Student, TuitionFee

SEMESTER = "HK1/2026-2027"

STUDENTS = [
    ("522H0001", "Nguyễn Văn Minh", "Kỹ thuật phần mềm", "Công nghệ thông tin"),
    ("522H0002", "Trần Thu Hà", "Khoa học máy tính", "Công nghệ thông tin"),
    ("522H0003", "Phạm Minh Tuấn", "Mạng máy tính", "Công nghệ thông tin"),
    ("522H0004", "Lê Thị Lan", "Kỹ thuật phần mềm", "Công nghệ thông tin"),
    ("522H0005", "Võ Quốc Bảo", "Khoa học dữ liệu", "Công nghệ thông tin"),
]

FEES = [
    # (fee_id, student_code, amount, status)
    ("f0000001-0000-0000-0000-000000000001", "522H0001", "9500000.00", STATUS_UNPAID),
    ("f0000002-0000-0000-0000-000000000002", "522H0002", "8750000.00", STATUS_UNPAID),
    ("f0000003-0000-0000-0000-000000000003", "522H0003", "10200000.00", STATUS_UNPAID),
    # Đã đóng: dùng để kiểm thử tình huống học phí đã thanh toán.
    ("f0000004-0000-0000-0000-000000000004", "522H0004", "7300000.00", STATUS_PAID),
    # Dùng cho kịch bản concurrency: hai người cùng đóng cho MSSV này.
    ("f0000005-0000-0000-0000-000000000005", "522H0005", "11000000.00", STATUS_UNPAID),
]


def seed() -> None:
    with SessionLocal() as db:
        if db.scalar(select(Student).limit(1)):
            return
        db.add_all(
            Student(student_code=c, full_name=n, program=p, faculty=f) for c, n, p, f in STUDENTS
        )
        db.flush()
        for fid, code, amount, status in FEES:
            db.add(
                TuitionFee(
                    id=fid,
                    student_code=code,
                    semester=SEMESTER,
                    amount=Decimal(amount),
                    status=status,
                    payment_ref="SEED-" + fid if status == STATUS_PAID else None,
                    paid_at=datetime.now(UTC) if status == STATUS_PAID else None,
                )
            )
        db.commit()
