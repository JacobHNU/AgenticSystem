import pytest
import asyncio
from app.mcp.retry import RetryController, RetryConfig

class TestRetryController:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        controller = RetryController()
        config = RetryConfig(max_attempts=3, backoff_ms=[100, 200, 400])

        call_count = 0
        async def success_fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await controller.execute(success_fn, config=config)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        controller = RetryController()
        config = RetryConfig(max_attempts=3, backoff_ms=[10, 20, 40])

        call_count = 0
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "ok"

        result = await controller.execute(fail_then_succeed, config=config)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self):
        controller = RetryController()
        config = RetryConfig(max_attempts=2, backoff_ms=[10, 20])

        async def always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            await controller.execute(always_fail, config=config)
