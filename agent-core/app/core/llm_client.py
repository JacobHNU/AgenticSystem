import anthropic
from typing import List, Dict, Any, Optional


class LLMClient:
    """LLM API wrapper with retry and timeout"""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = None, timeout: float = 60.0):
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.timeout = timeout

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: str = None,
        max_tokens: int = 4096,
        response_format: Dict = None,
        temperature: float = 0.0,
    ) -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = await self.client.messages.create(**kwargs)
        return response.content[0].text
