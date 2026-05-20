# packages/core/tests/test_middleware_rate_limit.py
import uuid

import pytest
from sutram_core.middleware.rate_limit import RateLimiter, RateLimitExceeded


@pytest.mark.asyncio
async def test_allows_requests_under_limit(fake_redis):
    limiter = RateLimiter(redis=fake_redis, requests_per_minute=10)
    tenant_id = str(uuid.uuid4())

    for _ in range(10):
        await limiter.check(tenant_id)  # Should not raise


@pytest.mark.asyncio
async def test_blocks_requests_over_limit(fake_redis):
    limiter = RateLimiter(redis=fake_redis, requests_per_minute=2)
    tenant_id = str(uuid.uuid4())

    await limiter.check(tenant_id)
    await limiter.check(tenant_id)

    with pytest.raises(RateLimitExceeded):
        await limiter.check(tenant_id)


@pytest.mark.asyncio
async def test_different_tenants_have_independent_limits(fake_redis):
    limiter = RateLimiter(redis=fake_redis, requests_per_minute=1)
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    await limiter.check(tenant_a)  # tenant_a at limit

    # tenant_b should be unaffected
    await limiter.check(tenant_b)  # should not raise


@pytest.mark.asyncio
async def test_rate_limit_exceeded_error_message(fake_redis):
    limiter = RateLimiter(redis=fake_redis, requests_per_minute=1)
    tenant_id = str(uuid.uuid4())
    await limiter.check(tenant_id)

    with pytest.raises(RateLimitExceeded) as exc_info:
        await limiter.check(tenant_id)

    assert tenant_id in str(exc_info.value)


@pytest.mark.asyncio
async def test_exactly_at_limit_is_allowed_then_next_raises(fake_redis):
    limiter = RateLimiter(redis=fake_redis, requests_per_minute=3)
    tenant_id = str(uuid.uuid4())

    # Exactly 3 requests must all pass
    for _ in range(3):
        await limiter.check(tenant_id)

    # 4th must fail
    with pytest.raises(RateLimitExceeded):
        await limiter.check(tenant_id)
