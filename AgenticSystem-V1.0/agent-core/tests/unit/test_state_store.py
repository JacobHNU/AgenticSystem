import pytest
from unittest.mock import AsyncMock
from app.agent.state import StateStore
from app.agent.models import AgentState

class TestStateStore:
    def test_init(self):
        store = StateStore(cache=AsyncMock(), database=AsyncMock())
        assert store is not None
