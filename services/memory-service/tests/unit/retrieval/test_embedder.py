import pytest
import json
import uuid
from unittest.mock import AsyncMock, MagicMock
from sutram_core.embedding.registry import EmbeddingRegistry
from app.retrieval.embedder import Embedder


def make_registry(model_name: str = "text-embedding-3-small", dims: int = 1536) -> EmbeddingRegistry:
    registry = EmbeddingRegistry()
    provider = MagicMock()
    provider.model_name = model_name
    provider.dimensions = dims
    provider.embed = AsyncMock(return_value=[[0.1] * dims])
    registry.register(provider)
    return registry


@pytest.mark.asyncio
async def test_embed_calls_registry_on_cache_miss(fake_redis):
    registry = make_registry()
    embedder = Embedder(registry=registry, redis=fake_redis, cache_ttl_seconds=3600)
    vector = await embedder.embed("hello world", model="text-embedding-3-small")
    assert len(vector) == 1536
    registry.get("text-embedding-3-small").embed.assert_called_once_with(["hello world"])


@pytest.mark.asyncio
async def test_embed_uses_cache_on_second_call(fake_redis):
    registry = make_registry()
    embedder = Embedder(registry=registry, redis=fake_redis, cache_ttl_seconds=3600)
    v1 = await embedder.embed("hello", model="text-embedding-3-small")
    v2 = await embedder.embed("hello", model="text-embedding-3-small")
    assert v1 == v2
    # Provider only called once — second is cache hit
    assert registry.get("text-embedding-3-small").embed.call_count == 1


@pytest.mark.asyncio
async def test_embed_different_models_have_different_cache_keys(fake_redis):
    registry = EmbeddingRegistry()
    for model in ["model-a", "model-b"]:
        p = MagicMock()
        p.model_name = model
        p.dimensions = 512
        p.embed = AsyncMock(return_value=[[0.1] * 512])
        registry.register(p)

    embedder = Embedder(registry=registry, redis=fake_redis, cache_ttl_seconds=3600)
    await embedder.embed("text", model="model-a")
    await embedder.embed("text", model="model-b")

    # Both providers called — different cache keys
    assert registry.get("model-a").embed.call_count == 1
    assert registry.get("model-b").embed.call_count == 1

    # Verify the Redis key format includes the model name (prevents cross-model collisions)
    keys = await fake_redis.keys("embedding:*")
    key_strings = [k.decode() if isinstance(k, bytes) else k for k in keys]
    assert any("model-a" in k for k in key_strings)
    assert any("model-b" in k for k in key_strings)
