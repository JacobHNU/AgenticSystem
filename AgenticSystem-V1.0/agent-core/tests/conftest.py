import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_mcp_client():
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value=type("R", (), {"success": True, "data": {"ok": True}})())
    return client

@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.complete = AsyncMock(return_value='{"reasoning": "test", "action_type": "respond", "response_text": "done"}')
    return client
