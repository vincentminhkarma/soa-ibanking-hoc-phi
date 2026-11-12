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

# Dữ liệu mở rộng để danh mục sinh viên/công nợ không quá ít khi demo.
# (student_code, full_name, program, faculty, amount, status)
EXTRA = [
    ("522H0006", "Đặng Hoàng Long", "Kỹ thuật phần mềm", "Công nghệ thông tin", "9500000.00", STATUS_UNPAID),
    ("522H0007", "Bùi Ngọc Ánh", "Khoa học máy tính", "Công nghệ thông tin", "8750000.00", STATUS_PAID),
    ("522H0008", "Hồ Gia Huy", "Mạng máy tính", "Công nghệ thông tin", "10200000.00", STATUS_UNPAID),
    ("522H0009", "Ngô Thanh Trúc", "Khoa học dữ liệu", "Công nghệ thông tin", "11000000.00", STATUS_PAID),
    ("522H0010", "Dương Minh Khoa", "Kỹ thuật phần mềm", "Công nghệ thông tin", "9500000.00", STATUS_UNPAID),
    ("522H0011", "Lý Bảo Ngọc", "Khoa học máy tính", "Công nghệ thông tin", "8750000.00", STATUS_UNPAID),
    ("522H0012", "Trương Đức Anh", "Mạng máy tính", "Công nghệ thông tin", "10200000.00", STATUS_PAID),
    ("522K0013", "Phan Thị Mai", "Kế toán", "Kế toán", "7800000.00", STATUS_UNPAID),
    ("522K0014", "Vũ Anh Tuấn", "Kế toán", "Kế toán", "7800000.00", STATUS_PAID),
    ("522K0015", "Đỗ Khánh Linh", "Kiểm toán", "Kế toán", "8100000.00", STATUS_UNPAID),
    ("522K0016", "Huỳnh Tấn Phát", "Kiểm toán", "Kế toán", "8100000.00", STATUS_UNPAID),
    ("522B0017", "Nguyễn Thùy Dương", "Quản trị kinh doanh", "Quản trị kinh doanh", "8400000.00", STATUS_PAID),
    ("522B0018", "Trần Quang Vinh", "Marketing", "Quản trị kinh doanh", "8900000.00", STATUS_UNPAID),
    ("522B0019", "Lê Hải Yến", "Marketing", "Quản trị kinh doanh", "8900000.00", STATUS_UNPAID),
    ("522B0020", "Phạm Nhật Nam", "Kinh doanh quốc tế", "Quản trị kinh doanh", "9200000.00", STATUS_PAID),
    ("522E0021", "Võ Thị Kim Chi", "Kỹ thuật điện", "Điện - Điện tử", "9900000.00", STATUS_UNPAID),
    ("522E0022", "Đinh Công Thành", "Kỹ thuật điện tử - viễn thông", "Điện - Điện tử", "10400000.00", STATUS_UNPAID),
    ("522E0023", "Mai Xuân Trường", "Tự động hóa", "Điện - Điện tử", "10400000.00", STATUS_PAID),
    ("522F0024", "Cao Thị Hồng Nhung", "Ngôn ngữ Anh", "Ngoại ngữ", "7600000.00", STATUS_UNPAID),
    ("522F0025", "Tạ Minh Quân", "Ngôn ngữ Anh", "Ngoại ngữ", "7600000.00", STATUS_PAID),
    ("522F0026", "Lâm Tuệ Nhi", "Ngôn ngữ Trung Quốc", "Ngoại ngữ", "7900000.00", STATUS_UNPAID),
    ("522D0027", "Châu Gia Bảo", "Thiết kế đồ họa", "Mỹ thuật công nghiệp", "12500000.00", STATUS_UNPAID),
    ("522D0028", "Quách Thanh Hằng", "Thiết kế thời trang", "Mỹ thuật công nghiệp", "12500000.00", STATUS_PAID),
    ("522L0029", "Tô Đức Mạnh", "Luật kinh tế", "Luật", "8300000.00", STATUS_UNPAID),
    ("522L0030", "Kiều Phương Thảo", "Luật", "Luật", "8300000.00", STATUS_UNPAID),
]
STUDENTS += [row[:4] for row in EXTRA]

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
FEES += [
    (f"f{n:07d}-0000-0000-0000-{n:012d}", code, amount, status)
    for n, (code, _, _, _, amount, status) in enumerate(EXTRA, start=6)
]


def seed() -> None:
    # Chèn từng sinh viên còn thiếu, nên database đã có dữ liệu vẫn nhận thêm dòng mới mà không cần xoá volume.
    with SessionLocal() as db:
        existing = set(db.scalars(select(Student.student_code)))
        missing = [s for s in STUDENTS if s[0] not in existing]
        if not missing:
            return
        db.add_all(Student(student_code=c, full_name=n, program=p, faculty=f) for c, n, p, f in missing)
        db.flush()
        codes = {s[0] for s in missing}
        for fid, code, amount, status in FEES:
            if code not in codes:
                continue
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
