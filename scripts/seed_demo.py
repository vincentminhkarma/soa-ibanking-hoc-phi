#!/usr/bin/env python3
"""Tạo lịch sử giao dịch mẫu bằng chính luồng thanh toán thật (gateway → OTP qua MailHog → saga).

Chạy sau khi hệ thống đã UP:  .venv/bin/python scripts/seed_demo.py
Chạy lại không tạo trùng: khoản học phí đã đóng thì bỏ qua.
Không đụng tới 4 tài khoản và 5 MSSV dùng cho kịch bản demo (minhnguyen, thuha, quocbao, itdu; 522H0001–522H0005).
"""
import os
import re
import time

import httpx

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080") + "/api/v1"
MAILHOG = os.getenv("MAILHOG_URL", "http://localhost:8025")

# username -> các MSSV người đó đóng hộ
PLAN = {
    "ngoclan": ["522H0006", "522K0013"],
    "ducthinh": ["522H0008"],
    "hoangyen": ["522B0018"],
    "giahan": ["522E0021", "522F0024", "522D0027"],
    "tuananh": ["522L0029"],
    "camtu": ["522K0015"],
}


def read_otp(payment_id: str) -> str:
    deadline = time.time() + 15
    while time.time() < deadline:
        items = httpx.get(f"{MAILHOG}/api/v2/messages", params={"limit": 200}, timeout=10).json().get("items", [])
        for item in items:
            body = item.get("Content", {}).get("Body", "").replace("=\r\n", "").replace("=\n", "")
            if payment_id in body and (found := re.search(r"OTP:\s*(\d{6})", body)):
                return found.group(1)
        time.sleep(0.5)
    raise SystemExit(f"Không thấy email OTP của giao dịch {payment_id} trong MailHog.")


def main() -> None:
    created = 0
    for username, codes in PLAN.items():
        login = httpx.post(f"{GATEWAY}/auth/login", json={"username": username, "password": "123456"}, timeout=15)
        login.raise_for_status()
        http = httpx.Client(base_url=GATEWAY, headers={"Authorization": f"Bearer {login.json()['access_token']}"}, timeout=30)
        for code in codes:
            if not http.get(f"/tuitions/{code}").json().get("outstanding_fee"):
                continue
            resp = http.post("/payments", json={"student_code": code, "accept_terms": True})
            resp.raise_for_status()
            payment_id = resp.json()["payment"]["id"]
            http.post(f"/payments/{payment_id}/confirm", json={"otp_code": read_otp(payment_id)}).raise_for_status()
            created += 1
            print(f"  {username} đã đóng học phí cho {code}")
    if created:
        # Dọn hộp thư để lúc demo chỉ còn email của giao dịch đang trình diễn.
        httpx.delete(f"{MAILHOG}/api/v1/messages", timeout=10)
    print(f"Đã tạo {created} giao dịch mẫu." if created else "Giao dịch mẫu đã có sẵn, không tạo thêm.")


if __name__ == "__main__":
    main()
