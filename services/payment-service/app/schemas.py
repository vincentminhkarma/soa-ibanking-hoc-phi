from decimal import Decimal

from pydantic import BaseModel, Field


class PayerInfo(BaseModel):
    name: str
    email: str
    phone: str


class CreatePaymentRequest(BaseModel):
    student_code: str = Field(min_length=3, max_length=20, examples=["522H0001"])
    accept_terms: bool = Field(default=True, description="Người dùng đã đồng ý điều khoản giao dịch")


class PaymentResponse(BaseModel):
    id: str
    status: str
    payer: PayerInfo
    student_code: str
    student_name: str
    fee_id: str
    semester: str
    amount: Decimal
    balance_after: Decimal | None = None
    failure_code: str | None = None
    failure_reason: str | None = None
    otp_expires_at: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class CreatePaymentResponse(BaseModel):
    payment: PaymentResponse
    otp_sent_to: str = Field(description="Email đã che bớt, ví dụ mi****@tdtu.edu.vn")
    otp_ttl_seconds: int


class ConfirmPaymentRequest(BaseModel):
    otp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$", examples=["123456"])


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int


class PaymentEventItem(BaseModel):
    step: str
    status: str
    detail: str | None = None
    created_at: str | None = None
