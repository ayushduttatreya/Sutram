# tests/unit/test_dependencies.py
import pytest
import app.dependencies as deps


def test_get_http_client_raises_before_init():
    original = deps._http_client
    deps._http_client = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            deps.get_http_client()
    finally:
        deps._http_client = original


def test_get_rate_limiter_raises_before_init():
    original = deps._rate_limiter
    deps._rate_limiter = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            deps.get_rate_limiter()
    finally:
        deps._rate_limiter = original


def test_get_idempotency_store_raises_before_init():
    original = deps._idempotency_store
    deps._idempotency_store = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            deps.get_idempotency_store()
    finally:
        deps._idempotency_store = original


def test_init_clients_creates_http_client():
    from unittest.mock import patch, MagicMock
    import httpx
    # Patch aioredis.from_url so no real Redis connection is attempted
    with patch("app.dependencies.aioredis") as mock_aioredis:
        mock_aioredis.from_url.return_value = MagicMock()
        deps.init_clients()
        assert isinstance(deps._http_client, httpx.AsyncClient)
        assert deps._rate_limiter is not None
        assert deps._idempotency_store is not None
        # Reset
        deps._http_client = None
        deps._redis_rate_limit = None
        deps._redis_idempotency = None
        deps._rate_limiter = None
        deps._idempotency_store = None


@pytest.mark.asyncio
async def test_close_clients_nulls_all_singletons():
    from unittest.mock import patch, AsyncMock, MagicMock
    import httpx

    with patch("app.dependencies.aioredis") as mock_aioredis:
        mock_aioredis.from_url.return_value = AsyncMock()
        deps.init_clients()
        assert deps._http_client is not None
        assert deps._rate_limiter is not None
        assert deps._idempotency_store is not None

        # Mock aclose to be awaitable
        deps._http_client = AsyncMock()
        deps._redis_rate_limit = AsyncMock()
        deps._redis_idempotency = AsyncMock()

        await deps.close_clients()

        assert deps._http_client is None
        assert deps._redis_rate_limit is None
        assert deps._redis_idempotency is None
        assert deps._rate_limiter is None
        assert deps._idempotency_store is None
