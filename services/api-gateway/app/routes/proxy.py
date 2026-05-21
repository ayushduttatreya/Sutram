# services/api-gateway/app/routes/proxy.py
"""Reverse proxy for all /v1/ paths.

Design decisions:
- Single catch-all route handles all /v1/ traffic
- Rate limit checked on every authenticated request
- Idempotency enforced only on POST /v1/.../execute and POST /v1/memory/items
- Idempotency keys are tenant-scoped: stored as "{tenant_id}:{Idempotency-Key-header}"
  to prevent cross-tenant collisions
- SSE endpoint (/v1/executions/{id}/stream) uses a separate streaming code path
  via httpx.AsyncClient.stream() — never buffered
- Authorization header stripped before forwarding
- X-Internal-Token and X-Tenant-ID injected on every forwarded request
"""
from __future__ import annotations
import uuid

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from sutram_core.middleware.idempotency import IdempotencyStore
from sutram_core.middleware.rate_limit import RateLimiter, RateLimitExceeded

from app.dependencies import get_http_client, get_idempotency_store, get_rate_limiter
from app.middleware.auth import AuthDep
from app.settings import get_settings

router = APIRouter()

# Headers that must not be forwarded downstream (hop-by-hop)
_HOP_BY_HOP = frozenset(
    [
        "connection",
        "content-length",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "proxy-authorization",
        "proxy-authenticate",
    ]
)


def _downstream_url(path: str, settings) -> str:
    """Map /v1/... path to the correct downstream service base URL + path."""
    if path.startswith("/v1/memory"):
        return settings.memory_service_url + path
    if (
        path.startswith("/v1/traces")
        or path.startswith("/v1/metrics")
        or path.startswith("/v1/audit")
    ):
        return settings.observability_service_url + path
    return settings.workflow_service_url + path


def _build_forward_headers(
    request: Request,
    tenant_id: uuid.UUID,
    internal_token: str,
) -> dict[str, str]:
    """Strip hop-by-hop and Authorization headers; inject X-Internal-Token and X-Tenant-ID."""
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "authorization"
    }
    headers["X-Internal-Token"] = internal_token
    headers["X-Tenant-ID"] = str(tenant_id)
    return headers


async def _check_rate_limit(tenant_id: uuid.UUID, rate_limiter: RateLimiter) -> None:
    try:
        await rate_limiter.check(str(tenant_id))
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "message": str(e)},
        ) from e


async def _check_idempotency(
    tenant_id: uuid.UUID,
    idempotency_key: str | None,
    store: IdempotencyStore,
) -> None:
    """Raise 409 if this idempotency key has been seen before for this tenant."""
    if idempotency_key is None:
        return
    # Tenant-scoped key: prevents cross-tenant collision on identical key strings
    scoped_key = f"{tenant_id}:{idempotency_key}"
    is_duplicate = await store.check_and_store(scoped_key)
    if is_duplicate:
        raise HTTPException(
            status_code=409,
            detail={"error": "duplicate_request", "idempotency_key": idempotency_key},
        )


@router.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(
    path: str,
    request: Request,
    tenant_id: AuthDep,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Response:
    """Transparent reverse proxy for all /v1/ routes.

    SSE streams (/v1/executions/{id}/stream) use StreamingResponse.
    All other routes return buffered responses.
    """
    settings = get_settings()

    # 1. Rate limit check (every request)
    await _check_rate_limit(tenant_id, get_rate_limiter())

    # 2. Idempotency check — only on specific mutating endpoints
    full_path = f"/v1/{path}"
    is_execute_endpoint = full_path.rstrip("/").endswith("/execute")
    is_memory_items_post = full_path.rstrip("/") == "/v1/memory/items"
    if request.method == "POST" and (is_execute_endpoint or is_memory_items_post):
        await _check_idempotency(tenant_id, idempotency_key, get_idempotency_store())

    # 3. Build target URL and forward headers
    target_url = _downstream_url(full_path, settings)
    forward_headers = _build_forward_headers(request, tenant_id, settings.internal_auth_token)

    # 4. SSE streaming — separate code path, never buffer
    is_sse = full_path.endswith("/stream") and request.method == "GET"
    if is_sse:
        return await _proxy_sse(get_http_client(), target_url, forward_headers, settings, request.query_params)

    # 5. Normal buffered proxy
    return await _proxy_buffered(get_http_client(), request, target_url, forward_headers)


async def _proxy_buffered(
    client: httpx.AsyncClient,
    request: Request,
    target_url: str,
    forward_headers: dict[str, str],
) -> Response:
    """Read full request body, send to downstream, return full response."""
    body = await request.body()
    upstream_request = client.build_request(
        method=request.method,
        url=target_url,
        headers=forward_headers,
        content=body,
        params=request.query_params,
    )
    response = await client.send(upstream_request)
    response_headers = {
        k: v for k, v in response.headers.items() if k.lower() not in _HOP_BY_HOP
    }
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
    )


async def _proxy_sse(
    client: httpx.AsyncClient,
    target_url: str,
    forward_headers: dict[str, str],
    settings,
    query_params,
) -> StreamingResponse:
    """Proxy an SSE stream. Checks upstream status before committing to 200 stream."""

    async def event_stream():
        sse_timeout = httpx.Timeout(settings.stream_timeout_seconds)
        async with client.stream(
            "GET",
            target_url,
            headers=forward_headers,
            params=query_params,
            timeout=sse_timeout,
        ) as response:
            if response.status_code != 200:
                await response.aread()
                raise HTTPException(
                    status_code=response.status_code,
                    detail="upstream sse error",
                )
            async for chunk in response.aiter_bytes():
                yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
