from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.dependencies import (
    close_embedding,
    close_redis,
    init_db,
    init_embedding,
    init_redis,
)
from app.routes import memory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    init_redis()
    init_embedding()
    yield
    await close_embedding()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sutram Memory Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(memory.router, prefix="/v1")
    return app


app = create_app()
