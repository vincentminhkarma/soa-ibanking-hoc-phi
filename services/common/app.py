"""Factory tạo FastAPI app: gắn sẵn logging, error handler, health check."""
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import SERVICE_NAME
from .db import Base, engine, wait_for_db
from .errors import install_error_handlers
from .observability import instrument


def create_app(title: str, description: str = "", on_start: Callable[[], None] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        wait_for_db()
        Base.metadata.create_all(engine)
        if on_start:
            on_start()
        yield

    app = FastAPI(
        title=title,
        description=description,
        version="1.0.0",
        lifespan=lifespan,
        openapi_tags=[{"name": "public", "description": "API cho client"},
                      {"name": "internal", "description": "API service-to-service"}],
    )
    instrument(app, SERVICE_NAME)
    install_error_handlers(app)

    @app.get("/health", tags=["internal"], summary="Health check")
    def health() -> dict:
        return {"status": "UP", "service": SERVICE_NAME}

    return app
