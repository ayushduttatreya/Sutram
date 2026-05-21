# services/observability-service/app/main.py
from __future__ import annotations
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sutram Observability Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(traces.router, prefix="/v1")
    app.include_router(audit.router, prefix="/v1")
    app.include_router(metrics_api.router, prefix="/v1")
    # Prometheus scrape endpoint — NOT under /v1/ to avoid api-gateway proxy
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
