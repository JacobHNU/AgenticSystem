import asyncio
from typing import Callable, Any, Optional
from .models import RetryConfig


class RetryController:
    """Retry with exponential backoff"""

    async def execute(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        config: Optional[RetryConfig] = None
    ) -> Any:
        config = config or RetryConfig()
        kwargs = kwargs or {}
        last_error = None

        for attempt in range(config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < config.max_attempts - 1:
                    backoff = config.backoff_ms[attempt] / 1000.0
                    await asyncio.sleep(backoff)

        raise last_error
