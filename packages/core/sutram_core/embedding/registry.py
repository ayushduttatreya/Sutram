from __future__ import annotations
from .base import EmbeddingProvider


class EmbeddingRegistry:
    """Maps embedding model names to EmbeddingProvider instances.

    Each MemoryItem stores the model name used to create its embedding.
    Queries must embed with the same model to produce comparable vectors.
    """

    def __init__(self) -> None:
        self._providers: dict[str, EmbeddingProvider] = {}

    def register(self, provider: EmbeddingProvider) -> None:
        """Register a provider. Overwrites any existing provider for the same model name."""
        self._providers[provider.model_name] = provider

    def get(self, model_name: str) -> EmbeddingProvider:
        """Retrieve provider by model name. Raises KeyError if not registered."""
        if model_name not in self._providers:
            raise KeyError(f"No embedding provider registered for model: {model_name}")
        return self._providers[model_name]

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Embed texts using the named provider. Raises KeyError if model not registered."""
        provider = self.get(model)
        return await provider.embed(texts)

    @property
    def registered_models(self) -> list[str]:
        """Return list of registered model names."""
        return list(self._providers.keys())
