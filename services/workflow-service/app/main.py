from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    app.include_router(workflows.router, prefix="/v1")
    app.include_router(executions.router, prefix="/v1")
    app.include_router(webhooks.router, prefix="/v1")
    app.include_router(internal.router, prefix="/internal")
    return app


app = create_app()
