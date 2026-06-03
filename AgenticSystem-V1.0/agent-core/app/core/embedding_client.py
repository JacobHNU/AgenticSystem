import httpx
from typing import List


class EmbeddingClient:
    """Embedding model API wrapper"""

    def __init__(self, api_url: str, api_key: str = None, dimension: int = 1024):
        self.api_url = api_url
        self.api_key = api_key
        self.dimension = dimension
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def encode(self, text: str) -> List[float]:
        client = await self._get_client()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = await client.post(
            self.api_url,
            json={"input": text, "dimension": self.dimension},
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0] if "embeddings" in data else data["data"][0]["embedding"]

    async def encode_batch(self, texts: List[str]) -> List[List[float]]:
        client = await self._get_client()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = await client.post(
            self.api_url,
            json={"input": texts, "dimension": self.dimension},
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"] if "embeddings" in data else [d["embedding"] for d in data["data"]]

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
