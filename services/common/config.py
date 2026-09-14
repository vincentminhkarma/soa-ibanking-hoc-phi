"""Cấu hình dùng chung cho mọi service, đọc từ biến môi trường (12-factor)."""
import os

SERVICE_NAME = os.getenv("SERVICE_NAME", "unknown-service")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# JWT dùng chung giữa gateway và các service (HS256, shared secret).
JWT_SECRET = os.getenv("JWT_SECRET", "dev-jwt-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "60"))

# Token cho các lời gọi service-to-service (endpoint /internal/*).
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "dev-internal-token")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://account-service:8000")
TUITION_SERVICE_URL = os.getenv("TUITION_SERVICE_URL", "http://tuition-service:8000")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8000")
OTP_SERVICE_URL = os.getenv("OTP_SERVICE_URL", "http://otp-service:8000")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8000")

SMTP_HOST = os.getenv("SMTP_HOST", "mailhog")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@ibanking.tdtu.edu.vn")

OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "300"))  # 5 phút theo đề bài
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
