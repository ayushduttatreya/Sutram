import pytest
from sutram_core.embedding.registry import EmbeddingRegistry
from sutram_core.embedding.base import EmbeddingProvider


class FakeEmbedder:
    """Concrete test stub implementing EmbeddingProvider protocol."""

    def __init__(self, model_name: str, dims: int) -> None:
        self.model_name = model_name
        self.dimensions = dims
        self._call_count = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._call_count += 1
        return [[0.1] * self.dimensions for _ in texts]


def test_registry_registers_and_retrieves_provider():
    registry = EmbeddingRegistry()
    provider = FakeEmbedder("text-embedding-3-small", 1536)
    registry.register(provider)
    retrieved = registry.get("text-embedding-3-small")
    assert retrieved is provider


def test_registry_raises_for_unknown_model():
    registry = EmbeddingRegistry()
    with pytest.raises(KeyError, match="unknown-model"):
        registry.get("unknown-model")


@pytest.mark.asyncio
async def test_registry_embed_uses_correct_provider():
    registry = EmbeddingRegistry()
    provider = FakeEmbedder("text-embedding-3-small", 1536)
    registry.register(provider)

    vectors = await registry.embed(["hello world"], model="text-embedding-3-small")
    assert len(vectors) == 1
    assert len(vectors[0]) == 1536
    assert provider._call_count == 1


def test_registry_registered_models_returns_model_names():
    registry = EmbeddingRegistry()
    registry.register(FakeEmbedder("model-a", 512))
    registry.register(FakeEmbedder("model-b", 768))
    assert set(registry.registered_models) == {"model-a", "model-b"}


def test_registry_overwrite_provider_with_same_model_name():
    registry = EmbeddingRegistry()
    p1 = FakeEmbedder("model-x", 512)
    p2 = FakeEmbedder("model-x", 1024)
    registry.register(p1)
    registry.register(p2)
    assert registry.get("model-x") is p2


@pytest.mark.asyncio
async def test_registry_raises_for_unregistered_model_on_embed():
    registry = EmbeddingRegistry()
    with pytest.raises(KeyError):
        await registry.embed(["text"], model="not-registered")


def test_fake_embedder_satisfies_protocol():
    """Verify FakeEmbedder is a valid EmbeddingProvider at runtime."""
    embedder = FakeEmbedder("test-model", 512)
    assert isinstance(embedder, EmbeddingProvider)
