"""api-gateway — điểm vào duy nhất của hệ thống.

Trách nhiệm:
  - Định tuyến theo tiền tố URI tới đúng microservice (không chứa nghiệp vụ).
  - Xác thực JWT sớm (fail fast) cho mọi API trừ đăng nhập.
  - Chặn tuyệt đối các endpoint /internal/* của service khỏi thế giới bên ngoài.
  - Sinh X-Request-Id để trace một giao dịch xuyên nhiều service.
"""
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from common.config import (
    ACCOUNT_SERVICE_URL,
    AUTH_SERVICE_URL,
    NOTIFICATION_SERVICE_URL,
    OTP_SERVICE_URL,
    PAYMENT_SERVICE_URL,
    TUITION_SERVICE_URL,
)
from common.errors import install_error_handlers
from common.observability import REQUEST_ID_HEADER, get_request_id, instrument
from common.security import decode_token

log = logging.getLogger(__name__)

ROUTES = {
    "auth": AUTH_SERVICE_URL,
    "accounts": ACCOUNT_SERVICE_URL,
    "tuitions": TUITION_SERVICE_URL,
    "payments": PAYMENT_SERVICE_URL,
}
BACKENDS = {
    "auth-service": AUTH_SERVICE_URL,
    "account-service": ACCOUNT_SERVICE_URL,
    "tuition-service": TUITION_SERVICE_URL,
    "payment-service": PAYMENT_SERVICE_URL,
    "otp-service": OTP_SERVICE_URL,
    "notification-service": NOTIFICATION_SERVICE_URL,
}
PUBLIC_PATHS = {"auth/login"}
HOP_BY_HOP = {"content-length", "transfer-encoding", "connection", "keep-alive", "host"}

client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await client.aclose()


app = FastAPI(
    title="iBanking API Gateway",
    description="Cổng API duy nhất cho phân hệ đóng học phí iBanking (TDTU).",
    version="1.0.0",
    lifespan=lifespan,
)
instrument(app, "api-gateway")
install_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)

def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": {}, "request_id": get_request_id()}},
    )


@app.get("/health", summary="Liveness của gateway")
def health() -> dict:
    return {"status": "UP", "service": "api-gateway"}


@app.get("/health/services", summary="Health check tổng hợp toàn hệ thống")
async def health_services() -> JSONResponse:
    results = {}
    for name, url in BACKENDS.items():
        try:
            resp = await client.get(f"{url}/health", timeout=3)
            results[name] = "UP" if resp.status_code == 200 else f"DOWN({resp.status_code})"
        except httpx.HTTPError:
            results[name] = "DOWN"
    healthy = all(v == "UP" for v in results.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "UP" if healthy else "DEGRADED", "services": results},
    )


@app.get("/services", summary="Danh sách service và link tài liệu OpenAPI")
def services() -> dict:
    return {
        "gateway_docs": "/docs",
        "services": {
            name: {"base_url": url, "swagger": f"{url}/docs", "openapi": f"{url}/openapi.json"}
            for name, url in BACKENDS.items()
        },
    }


@app.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    summary="Proxy tới microservice tương ứng",
)
async def proxy(path: str, request: Request) -> Response:
    segment = path.split("/", 1)[0]
    target = ROUTES.get(segment)
    if not target:
        return _error(404, "ROUTE_NOT_FOUND", f"Không có service nào phụ trách /api/v1/{segment}.")

    # Endpoint nội bộ không bao giờ được lộ qua gateway.
    if "internal" in path.split("/"):
        return _error(403, "FORBIDDEN", "Endpoint nội bộ không truy cập được từ bên ngoài.")

    if path not in PUBLIC_PATHS:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return _error(401, "UNAUTHORIZED", "Thiếu access token.")
        decode_token(auth.split(" ", 1)[1].strip())  # ném APIError nếu token hỏng/hết hạn

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    headers[REQUEST_ID_HEADER] = get_request_id()

    try:
        upstream = await client.request(
            request.method,
            f"{target}/api/v1/{path}",
            content=await request.body(),
            params=request.query_params,
            headers=headers,
        )
    except httpx.HTTPError as exc:
        log.error("upstream_error target=%s path=%s err=%s", target, path, exc)
        return _error(503, "SERVICE_UNAVAILABLE", f"Dịch vụ '{segment}' hiện không phản hồi.")

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP},
        media_type=upstream.headers.get("content-type"),
    )
