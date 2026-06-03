import pytest
from app.mcp.client import MCPClientLayer
from app.mcp.circuit_breaker import CircuitBreaker, CircuitState

class TestMCPClientLayer:
    def test_init(self):
        client = MCPClientLayer(discovery_url="http://localhost:8080")
        assert client.discovery_url == "http://localhost:8080"
        assert len(client.circuit_breakers) == 0

    def test_get_or_create_circuit_breaker(self):
        client = MCPClientLayer(discovery_url="http://localhost:8080")
        cb = client._get_circuit_breaker("mcp-hr")
        assert isinstance(cb, CircuitBreaker)
        assert cb.state == CircuitState.CLOSED
        # Same instance on second call
        cb2 = client._get_circuit_breaker("mcp-hr")
        assert cb is cb2
