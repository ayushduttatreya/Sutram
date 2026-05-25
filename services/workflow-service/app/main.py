from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.dependencies import close_redis, init_db, init_redis
from app.routes import executions, internal, webhooks, workflows


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    import asyncio
    import contextlib

    init_db()
    init_redis()

    from app.dependencies import get_redis_lock
    from app.engine.recovery import RecoveryHandler, get_stale_executions
    from app.tasks.execute import execute_workflow

    async def _enqueue(execution_id: str) -> None:
        execute_workflow.delay(execution_id=execution_id)

    recovery_handler = RecoveryHandler(lock=get_redis_lock(), enqueue_fn=_enqueue)
    recovery_task = asyncio.create_task(recovery_handler.run_forever(get_stale_executions))

    yield

    recovery_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await recovery_task
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sutram Workflow Service",
        version="0.1.0",
        lifespan=lifespan,
    )
    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(workflows.router, prefix="/v1")
    app.include_router(executions.router, prefix="/v1")
    app.include_router(webhooks.router, prefix="/v1")
    app.include_router(internal.router, prefix="/internal")
    return app


app = create_app()
