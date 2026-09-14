"""Structured logging + correlation ID + OpenTelemetry distributed tracing.

Mỗi request vào gateway được gán X-Request-Id; id này được truyền tiếp qua mọi
lời gọi service-to-service nên có thể trace nguyên một giao dịch trong log.
Tích hợp Distributed Tracing (OpenTelemetry) xuất trace sang Jaeger qua OTLP HTTP.
"""
import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

REQUEST_ID_HEADER = "X-Request-Id"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


class _JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "service": self.service,
            "request_id": get_request_id(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            payload["trace_id"] = f"{ctx.trace_id:032x}"
            payload["span_id"] = f"{ctx.span_id:016x}"

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(service: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter(service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").handlers = []


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Gán/kế thừa request id và ghi access log dạng JSON."""

    def __init__(self, app, service: str):
        super().__init__(app)
        self.service = service
        self.log = logging.getLogger("access")

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        token = _request_id.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers[REQUEST_ID_HEADER] = rid
            # Ghi access log TRƯỚC khi reset contextvar, nếu không dòng log này
            # mất request_id và không trace được nữa.
            self.log.info(
                "%s %s -> %s (%sms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                extra={
                    "extra": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": elapsed_ms,
                    }
                },
            )
            return response
        finally:
            _request_id.reset(token)


def instrument(app: FastAPI, service: str, tracer_provider: TracerProvider | None = None) -> None:
    setup_logging(service)
    app.add_middleware(RequestContextMiddleware, service=service)
    provider = tracer_provider
    if provider is None:
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        if not endpoint:
            return
        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
        ))
        trace.set_tracer_provider(provider)
    httpx_instrumentor = HTTPXClientInstrumentor()
    if not httpx_instrumentor.is_instrumented_by_opentelemetry:
        httpx_instrumentor.instrument(tracer_provider=provider)
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls="^.*/health(/.*)?$",
        exclude_spans=["receive", "send"],
    )
