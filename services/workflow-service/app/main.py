from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.dependencies import close_redis, init_db, init_redis
from app.routes import executions, internal, webhooks, workflows


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    init_redis()
    yield
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sutram Workflow Service",
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

    app.include_router(workflows.router, prefix="/v1")
    app.include_router(executions.router, prefix="/v1")
    app.include_router(webhooks.router, prefix="/v1")
    app.include_router(internal.router, prefix="/internal")
    return app


app = create_app()
