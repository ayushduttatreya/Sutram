# services/api-gateway/app/routes/health.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    from app.dependencies import get_idempotency_store, get_rate_limiter

    errors: dict[str, str] = {}

    try:
        await get_rate_limiter()._redis.ping()
    except Exception:
        errors["redis_rate_limit"] = "unreachable"

    try:
        await get_idempotency_store()._redis.ping()
    except Exception:
        errors["redis_idempotency"] = "unreachable"

    if errors:
        return JSONResponse({"status": "degraded", **errors}, status_code=503)
    return JSONResponse({"status": "ok", "service": "api-gateway"})
