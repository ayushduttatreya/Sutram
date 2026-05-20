from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.dependencies import (
    init_db, init_redis, init_embedding,
    close_redis, close_embedding,
)
from app.routes import memory


@asynccontextmanager
async def lifespan(app: FastAPI):
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
