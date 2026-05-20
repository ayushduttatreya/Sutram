from __future__ import annotations
import httpx


class OpenAIEmbedder:
    """Embedding provider backed by OpenAI text-embedding-3-small."""

    model_name: str = "text-embedding-3-small"
    dimensions: int = 1536

    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            "/embeddings",
            json={"model": self.model_name, "input": texts},
        )
        response.raise_for_status()
        data = response.json()
        try:
            return [item["embedding"] for item in data["data"]]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                f"Unexpected response structure from OpenAI embeddings API: {data}"
            ) from exc

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OpenAIEmbedder":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()
