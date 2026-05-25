# services/observability-service/app/main.py
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.consumer.loop import run_consumer_loop
from app.dependencies import close_redis, get_redis_streams, init_db, init_redis
from app.routes import audit, metrics_api, traces


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    init_redis()

    consumer_task = asyncio.create_task(run_consumer_loop(get_redis_streams()))

    yield

    consumer_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await consumer_task
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sutram Observability Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        from sqlalchemy import text

        from app.dependencies import _redis_streams, get_db_session_context

        errors: dict[str, str] = {}

        if _redis_streams is None:
            errors["redis"] = "unreachable"
        else:
            try:
                await _redis_streams.ping()
            except Exception:
                errors["redis"] = "unreachable"

        try:
            async with get_db_session_context() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            errors["db"] = "unreachable"

        if errors:
            return JSONResponse({"status": "degraded", **errors}, status_code=503)
        return JSONResponse({"status": "ok"})

    app.include_router(traces.router, prefix="/v1")
    app.include_router(audit.router, prefix="/v1")
    app.include_router(metrics_api.router, prefix="/v1")
    # Prometheus scrape endpoint — NOT under /v1/ to avoid api-gateway proxy
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
