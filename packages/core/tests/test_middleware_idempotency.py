# packages/core/tests/test_middleware_idempotency.py
import asyncio

import pytest
from sutram_core.middleware.idempotency import IdempotencyStore


@pytest.mark.asyncio
async def test_first_request_not_duplicate(fake_redis):
    store = IdempotencyStore(redis=fake_redis)
    is_duplicate = await store.check_and_store("key-123", ttl_seconds=86400)
    assert is_duplicate is False


@pytest.mark.asyncio
async def test_second_request_is_duplicate(fake_redis):
    store = IdempotencyStore(redis=fake_redis)
    await store.check_and_store("key-456", ttl_seconds=86400)
    is_duplicate = await store.check_and_store("key-456", ttl_seconds=86400)
    assert is_duplicate is True


@pytest.mark.asyncio
async def test_different_keys_are_independent(fake_redis):
    store = IdempotencyStore(redis=fake_redis)
    await store.check_and_store("key-aaa", ttl_seconds=86400)
    is_duplicate = await store.check_and_store("key-bbb", ttl_seconds=86400)
    assert is_duplicate is False


@pytest.mark.asyncio
async def test_key_is_namespaced_in_redis(fake_redis):
    store = IdempotencyStore(redis=fake_redis)
    await store.check_and_store("my-key", ttl_seconds=86400)
    # Raw key in Redis should be namespaced to avoid collisions
    raw = await fake_redis.get("idempotency:my-key")
    assert raw is not None


@pytest.mark.asyncio
async def test_key_not_duplicate_after_ttl_expires(fake_redis):
    store = IdempotencyStore(redis=fake_redis)
    await store.check_and_store("expiry-key", ttl_seconds=1)

    # Wait for TTL to expire
    await asyncio.sleep(1.2)

    # After expiry, should no longer be a duplicate
    is_duplicate = await store.check_and_store("expiry-key", ttl_seconds=1)
    assert is_duplicate is False
