from decimal import Decimal

from pydantic import BaseModel, Field


class StudentInfo(BaseModel):
    student_code: str
    full_name: str
    program: str
    faculty: str


class FeeItem(BaseModel):
    id: str
    student_code: str
    semester: str
    amount: Decimal
    status: str
    payment_ref: str | None = None
    paid_at: str | None = None


class TuitionLookupResponse(BaseModel):
    student: StudentInfo
    outstanding_fee: FeeItem | None = Field(
        default=None, description="Khoản học phí chưa thanh toán; null nghĩa là đã đóng đủ."
    )
    fees: list[FeeItem]


class CreateFeeRequest(BaseModel):
    student_code: str = Field(min_length=3, max_length=20)
    full_name: str = Field(default="Sinh viên TDTU", max_length=120)
    program: str = Field(default="Kỹ thuật phần mềm", max_length=120)
    faculty: str = Field(default="Công nghệ thông tin", max_length=120)
    semester: str = Field(default="HK1/2026-2027", max_length=20)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class PayFeeRequest(BaseModel):
    payment_ref: str = Field(min_length=6, max_length=80, description="payment_id của giao dịch")


class FeeStateResponse(BaseModel):
    fee: FeeItem
    idempotent_replay: bool = False
