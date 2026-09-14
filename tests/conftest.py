"""Tiện ích dùng chung cho integration test.

Test chạy ngoài Docker, gọi hệ thống đúng như một client thật:
  - nghiệp vụ đi qua API Gateway (http://localhost:8080)
  - mã OTP được bóc từ hộp thư MailHog, tức là chứng minh email thật sự được gửi
  - dữ liệu test tự tạo qua endpoint admin nên chạy lại nhiều lần vẫn đúng
"""
import os
import random
import re
import time
from decimal import Decimal

import httpx
import pytest

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")
TUITION_URL = os.getenv("TUITION_URL", "http://localhost:8003")
ACCOUNT_URL = os.getenv("ACCOUNT_URL", "http://localhost:8002")
MAILHOG = os.getenv("MAILHOG_URL", "http://localhost:8025")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "tdtu-soa-internal-token")

PASSWORD = "123456"
INTERNAL_HEADERS = {"X-Internal-Token": INTERNAL_TOKEN}


@pytest.fixture(scope="session", autouse=True)
def wait_for_stack():
    """Chờ toàn bộ service UP trước khi chạy test."""
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{GATEWAY}/health/services", timeout=5)
            if resp.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(3)
    pytest.fail("Hệ thống chưa sẵn sàng: chạy `docker compose up -d` trước khi test.")


class Client:
    """Client của một người dùng đã đăng nhập."""

    def __init__(self, username: str):
        self.username = username
        resp = httpx.post(
            f"{GATEWAY}/api/v1/auth/login", json={"username": username, "password": PASSWORD}, timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data["access_token"]
        self.user = data["user"]
        self.http = httpx.Client(
            base_url=f"{GATEWAY}/api/v1", headers={"Authorization": f"Bearer {self.token}"}, timeout=30
        )

    def balance(self) -> Decimal:
        return Decimal(str(self.http.get("/accounts/me").json()["balance"]))

    def lookup(self, student_code: str) -> httpx.Response:
        return self.http.get(f"/tuitions/{student_code}")

    def create_payment(self, student_code: str, idem: str | None = None) -> httpx.Response:
        headers = {"Idempotency-Key": idem} if idem else {}
        return self.http.post(
            "/payments", json={"student_code": student_code, "accept_terms": True}, headers=headers
        )

    def confirm(self, payment_id: str, code: str) -> httpx.Response:
        return self.http.post(f"/payments/{payment_id}/confirm", json={"otp_code": code})

    def resend(self, payment_id: str) -> httpx.Response:
        return self.http.post(f"/payments/{payment_id}/otp/resend")


@pytest.fixture
def alice() -> Client:
    return Client("minhnguyen")


@pytest.fixture
def bob() -> Client:
    return Client("thuha")


@pytest.fixture
def carol() -> Client:
    return Client("quocbao")


def new_fee(amount: str | Decimal, prefix: str = "T") -> dict:
    """Tạo một sinh viên + khoản học phí mới tinh cho mỗi test."""
    code = f"{prefix}{random.randint(100000, 999999)}"
    resp = httpx.post(
        f"{TUITION_URL}/internal/tuitions/fees",
        json={"student_code": code, "full_name": f"Sinh viên {code}", "amount": str(amount)},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fee_state(fee_id: str) -> dict:
    resp = httpx.get(f"{TUITION_URL}/internal/tuitions/fees/{fee_id}", headers=INTERNAL_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def top_up(user_id: str, amount: str, reference: str) -> Decimal:
    """Nạp tiền qua endpoint nội bộ để test có số dư xác định."""
    resp = httpx.post(
        f"{ACCOUNT_URL}/internal/accounts/{user_id}/credit",
        json={"amount": amount, "reference": reference, "description": "Nạp tiền phục vụ kiểm thử"},
        headers=INTERNAL_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return Decimal(str(resp.json()["balance_after"]))


def read_otp(payment_id: str, timeout: float = 15) -> str:
    """Lấy mã OTP của giao dịch từ MailHog (chứng minh email đã được gửi thật)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{MAILHOG}/api/v2/messages", params={"limit": 200}, timeout=10)
        for item in resp.json().get("items", []):
            body = item.get("Content", {}).get("Body", "")
            body = body.replace("=\r\n", "").replace("=\n", "")
            if payment_id in body and "OTP:" in body:
                found = re.search(r"OTP:\s*(\d{6})", body)
                if found:
                    return found.group(1)
        time.sleep(0.5)
    raise AssertionError(f"Không tìm thấy email OTP cho giao dịch {payment_id} trong MailHog.")


def receipt_exists(payment_id: str, timeout: float = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{MAILHOG}/api/v2/messages", params={"limit": 200}, timeout=10)
        for item in resp.json().get("items", []):
            body = item.get("Content", {}).get("Body", "").replace("=\r\n", "").replace("=\n", "")
            if payment_id in body and "STATUS: SUCCESS" in body:
                return True
        time.sleep(0.5)
    return False


def error_code(resp: httpx.Response) -> str:
    return resp.json().get("error", {}).get("code", "")


def pay_flow(client: Client, student_code: str) -> httpx.Response:
    """Tạo giao dịch, lấy OTP và xác nhận — luồng hạnh phúc rút gọn."""
    created = client.create_payment(student_code)
    created.raise_for_status()
    payment_id = created.json()["payment"]["id"]
    return client.confirm(payment_id, read_otp(payment_id))
