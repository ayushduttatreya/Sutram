# services/api-gateway/app/main.py
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.dependencies import close_clients, init_clients
from app.routes import health, proxy


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_clients()
    yield
    await close_clients()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sutram API Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(proxy.router)
    return app


app = create_app()
