"""Embedding cache wrapper around EmbeddingRegistry.

Cache key: embedding:{model_name}:{sha256(text)}
TTL: configurable (default 1 hour)
"""

from __future__ import annotations

import hashlib
import json
from typing import cast

import redis.asyncio as aioredis
from sutram_core.embedding.registry import EmbeddingRegistry


class Embedder:
    """Wraps EmbeddingRegistry with a Redis cache to avoid redundant API calls."""

    def __init__(
        self,
        registry: EmbeddingRegistry,
        redis: aioredis.Redis,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self._registry = registry
        self._redis = redis
        self._ttl = cache_ttl_seconds

    async def embed(self, text: str, model: str) -> list[float]:
        """Embed text with cache. Returns vector for the given model."""
        cache_key = f"embedding:{model}:{hashlib.sha256(text.encode()).hexdigest()}"
        cached = await self._redis.get(cache_key)
        if cached is not None:
            return cast(list[float], json.loads(cached))
        vector = cast(list[float], (await self._registry.embed([text], model=model))[0])
        await self._redis.setex(cache_key, self._ttl, json.dumps(vector))
        return vector
