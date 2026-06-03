import uuid
import httpx
import logging
from typing import Dict, Any, Optional

from .circuit_breaker import CircuitBreaker, CircuitState
from .models import MCPResponse, RetryConfig
from .retry import RetryController
from .auth import AuthManager
from .discovery import ToolDiscoveryClient
from .pool import ConnectionPool
from ..core.trace import TraceContext

logger = logging.getLogger(__name__)


class MCPClientLayer:
    """Unified MCP client with connection pool, auth, retry, and circuit breaker"""

    def __init__(self, discovery_url: str, pool_size: int = 10, request_timeout: float = 30.0,
                 failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.discovery_url = discovery_url
        self.discovery = ToolDiscoveryClient(discovery_url)
        self.auth = AuthManager()
        self.retry = RetryController()
        self.pools: Dict[str, ConnectionPool] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.pool_size = pool_size
        self.request_timeout = request_timeout
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout

    def _get_circuit_breaker(self, tool_name: str) -> CircuitBreaker:
        if tool_name not in self.circuit_breakers:
            self.circuit_breakers[tool_name] = CircuitBreaker(
                failure_threshold=self._failure_threshold,
                recovery_timeout=self._recovery_timeout
            )
        return self.circuit_breakers[tool_name]

    def _get_pool(self, base_url: str) -> ConnectionPool:
        if base_url not in self.pools:
            self.pools[base_url] = ConnectionPool(base_url, self.pool_size, self.request_timeout)
        return self.pools[base_url]

    async def call_tool(
        self,
        tool_name: str,
        action: str,
        params: Dict[str, Any],
        retry_config: Optional[RetryConfig] = None,
        trace_id: Optional[str] = None
    ) -> MCPResponse:
        trace_id = trace_id or TraceContext.get_or_create()
        TraceContext.set_trace_id(trace_id)

        logger.info(f"[{trace_id}] MCP call: {tool_name}/{action}")

        # Circuit breaker check
        cb = self._get_circuit_breaker(tool_name)
        if cb.state == CircuitState.OPEN:
            return MCPResponse(
                success=False,
                error="tool_unavailable",
                error_type="tool_unavailable",
                retry_after=cb.retry_after
            )

        try:
            endpoint = await self.discovery.get_endpoint(tool_name)
            pool = self._get_pool(endpoint["url"])
            client = await pool.get_client()
            headers = self.auth.get_headers(tool_name)
            headers["X-Trace-Id"] = trace_id

            response = await self.retry.execute(
                func=self._do_request,
                args=(client, action, params, headers),
                config=retry_config
            )

            cb.record_success()
            return response

        except Exception as e:
            cb.record_failure()
            logger.error(f"[{trace_id}] MCP call failed: {tool_name}/{action}: {e}")
            return MCPResponse(
                success=False,
                error=str(e),
                error_type="tool_unavailable"
            )

    async def _do_request(
        self, client: httpx.AsyncClient, action: str,
        params: Dict[str, Any], headers: Dict[str, str]
    ) -> MCPResponse:
        response = await client.post(
            f"/tools/{action}",
            json=params,
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return MCPResponse(success=True, data=data)

    async def close(self):
        for pool in self.pools.values():
            await pool.close()
        await self.discovery.close()
