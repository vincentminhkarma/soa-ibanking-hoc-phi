"""Client gọi service khác: gắn internal token + truyền tiếp request id."""
import logging
from typing import Any

import httpx

from .config import INTERNAL_TOKEN
from .errors import APIError
from .observability import REQUEST_ID_HEADER, get_request_id

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def call_service(method: str, url: str, *, json: dict | None = None, params: dict | None = None) -> Any:
    """Gọi service nội bộ và chuyển lỗi upstream thành APIError giữ nguyên mã lỗi.

    Nhờ vậy lỗi nghiệp vụ (ví dụ INSUFFICIENT_FUNDS của account-service) không bị
    payment-service nuốt mất thành lỗi 500 vô nghĩa.
    """
    headers = {"X-Internal-Token": INTERNAL_TOKEN, REQUEST_ID_HEADER: get_request_id()}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.request(method, url, json=json, params=params, headers=headers)
    except httpx.HTTPError as exc:
        log.error("service_unavailable url=%s err=%s", url, exc)
        raise APIError(503, "SERVICE_UNAVAILABLE", f"Không kết nối được dịch vụ phụ thuộc: {url}")

    if resp.status_code >= 400:
        try:
            err = resp.json()["error"]
        except Exception:
            err = {"code": "UPSTREAM_ERROR", "message": resp.text[:200]}
        raise APIError(resp.status_code, err.get("code", "UPSTREAM_ERROR"), err.get("message", ""), err.get("details"))

    return resp.json() if resp.content else None
