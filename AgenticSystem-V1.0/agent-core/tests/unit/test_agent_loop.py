import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agent.loop import AgentLoop
from app.agent.models import AgentState, TaskResult

class TestAgentLoop:
    def test_init(self):
        loop = AgentLoop(
            agent_id="test-agent",
            skill_set=["skill-a"],
            skill_engine=AsyncMock(),
            llm_client=AsyncMock(),
            state_store=AsyncMock(),
            config=MagicMock(max_iterations=3, checkpoint_interval=1,
                           think_system_prompt="", reflect_system_prompt="")
        )
        assert loop.agent_id == "test-agent"
        assert loop.skill_set == ["skill-a"]
