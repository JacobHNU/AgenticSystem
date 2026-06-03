import httpx
from typing import Optional


class ConnectionPool:
    """HTTP connection pool for a single MCP endpoint"""

    def __init__(self, base_url: str, pool_size: int = 10, timeout: float = 30.0):
        self.base_url = base_url
        self.pool_size = pool_size
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=self.pool_size)
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
