import httpx
from typing import Dict, Any, List, Optional


class ToolDiscoveryClient:
    """MCP tool discovery client"""

    def __init__(self, discovery_url: str):
        self.discovery_url = discovery_url
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def get_endpoint(self, tool_name: str) -> Dict[str, Any]:
        if tool_name in self._cache:
            return self._cache[tool_name]

        client = await self._get_client()
        response = await client.get(f"{self.discovery_url}/tools/{tool_name}")
        response.raise_for_status()
        endpoint = response.json()
        self._cache[tool_name] = endpoint
        return endpoint

    async def list_tools(self, domain: str = None) -> List[Dict[str, Any]]:
        client = await self._get_client()
        params = {}
        if domain:
            params["domain"] = domain
        response = await client.get(f"{self.discovery_url}/tools", params=params)
        response.raise_for_status()
        return response.json()

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
