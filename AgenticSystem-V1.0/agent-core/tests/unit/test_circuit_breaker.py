import pytest
import asyncio
from app.mcp.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        for _ in range(2):
            cb.record_failure()
        await asyncio.sleep(0.15)
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_retry_after_value(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        for _ in range(2):
            cb.record_failure()
        assert cb.retry_after > 0
