"""Unit tests cho module observability (OpenTelemetry tracing & structured logging).

Kiểm tra:
1. X-Request-Id sinh mới hoặc kế thừa từ client header.
2. Log JSON tự động bổ sung trace_id/span_id khi có active span, và không lộ thông tin nhạy cảm.
3. Health check endpoints bị loại trừ khỏi trace (excluded_urls).
4. Các route bình thường sinh trace đầy đủ qua FastAPI + HTTPX instrumentation.
5. Hỗ trợ cả sync client (common/http) và pre-created AsyncClient (api-gateway).
"""
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from common.observability import (
    REQUEST_ID_HEADER,
    _JsonFormatter,
    get_request_id,
    instrument,
)


@pytest.fixture(autouse=True)
def restore_httpx_and_logging():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    instrumentor = HTTPXClientInstrumentor()
    if instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.uninstrument()
    root.handlers, root.level = handlers, level


def _create_isolated_tracer():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_request_id_generation_and_inheritance():
    app = FastAPI()
    instrument(app, "test-service")

    @app.get("/api/v1/echo-id")
    def echo_id():
        return {"rid": get_request_id()}

    client = TestClient(app)

    # Tự sinh mới nếu client không truyền
    r1 = client.get("/api/v1/echo-id")
    assert r1.status_code == 200
    rid1 = r1.headers.get(REQUEST_ID_HEADER)
    assert rid1 and len(rid1) >= 16
    assert r1.json()["rid"] == rid1

    # Kế thừa nếu client truyền header
    custom_rid = "client-req-999"
    r2 = client.get("/api/v1/echo-id", headers={REQUEST_ID_HEADER: custom_rid})
    assert r2.status_code == 200
    assert r2.headers.get(REQUEST_ID_HEADER) == custom_rid
    assert r2.json()["rid"] == custom_rid


def test_json_formatter_with_and_without_span():
    provider, _ = _create_isolated_tracer()
    tracer = provider.get_tracer("test-logger")
    formatter = _JsonFormatter("account-service")

    record = logging.LogRecord("test", logging.INFO, "test.py", 10, "Thông báo log", (), None)

    # Khi không có span
    raw_no_span = formatter.format(record)
    data_no_span = json.loads(raw_no_span)
    assert data_no_span["service"] == "account-service"
    assert data_no_span["message"] == "Thông báo log"
    assert "trace_id" not in data_no_span
    assert "span_id" not in data_no_span

    # Khi có span đang chạy
    with tracer.start_as_current_span("active-operation") as span:
        ctx = span.get_span_context()
        raw_with_span = formatter.format(record)
        data_with_span = json.loads(raw_with_span)
        assert data_with_span["trace_id"] == f"{ctx.trace_id:032x}"
        assert data_with_span["span_id"] == f"{ctx.span_id:016x}"


def test_fastapi_health_endpoints_excluded_from_tracing():
    provider, exporter = _create_isolated_tracer()
    app = FastAPI()
    instrument(app, "payment-service", tracer_provider=provider)

    @app.get("/health")
    def health():
        return {"status": "UP"}

    @app.get("/health/services")
    def health_services():
        return {"status": "UP"}

    @app.get("/api/v1/tuitions")
    def tuitions():
        return {"tuitions": []}

    client = TestClient(app)

    # Các endpoint health không được tạo span
    client.get("/health")
    client.get("/health/services")
    assert len(exporter.get_finished_spans()) == 0

    # Endpoint nghiệp vụ thông thường phải tạo server span
    client.get("/api/v1/tuitions")
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "GET /api/v1/tuitions"
    # Không có span nội bộ 'receive'/'send'
    span_names = [s.name for s in spans]
    assert "http.receive" not in span_names
    assert "http.send" not in span_names


def test_spans_do_not_leak_sensitive_payloads():
    provider, exporter = _create_isolated_tracer()
    app = FastAPI()
    instrument(app, "auth-service", tracer_provider=provider)

    @app.post("/api/v1/auth/login")
    def login(body: dict):
        return {"token": "jwt-token-xyz"}

    client = TestClient(app)
    sensitive_data = {
        "password": "super-secret-password",
        "otp": "654321",
        "jwt": "bearer-token-val",
    }
    client.post("/api/v1/auth/login", json=sensitive_data)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    attributes_str = json.dumps({k: str(v) for k, v in span.attributes.items()})
    assert "super-secret-password" not in attributes_str
    assert "654321" not in attributes_str
    assert "jwt-token-xyz" not in attributes_str


def test_sync_and_precreated_async_httpx_instrumentation():
    """Kiểm tra HTTPXClientInstrumentor trace cả sync client và pre-created AsyncClient."""
    class MockHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), MockHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        provider, exporter = _create_isolated_tracer()

        # Mô phỏng pre-created client như trong api-gateway
        pre_created_async = httpx.AsyncClient()

        # Khởi tạo instrumentation
        app = FastAPI()
        instrument(app, "api-gateway", tracer_provider=provider)

        # 1. Gọi bằng Sync client (như trong common/http)
        with httpx.Client() as sync_client:
            resp = sync_client.get(f"http://127.0.0.1:{port}/sync-call")
            assert resp.status_code == 200

        # 2. Gọi bằng pre-created AsyncClient
        import anyio
        async def run_async():
            resp = await pre_created_async.get(f"http://127.0.0.1:{port}/async-call")
            assert resp.status_code == 200
            await pre_created_async.aclose()

        anyio.run(run_async)

        spans = exporter.get_finished_spans()
        urls = [s.attributes.get("http.url") for s in spans]
        assert any(f"http://127.0.0.1:{port}/sync-call" in str(u) for u in urls)
        assert any(f"http://127.0.0.1:{port}/async-call" in str(u) for u in urls)
    finally:
        server.shutdown()
        server.server_close()
