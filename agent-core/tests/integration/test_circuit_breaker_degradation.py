import pytest
from app.mcp.circuit_breaker import CircuitBreaker, CircuitState

class TestCircuitBreakerDegradation:
    def test_circuit_open_blocks_calls(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.retry_after > 0

    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        import asyncio
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
