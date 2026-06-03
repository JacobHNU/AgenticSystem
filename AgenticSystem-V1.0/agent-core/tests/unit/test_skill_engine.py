import pytest
from unittest.mock import AsyncMock
from app.skill.engine import SkillEngine
from app.skill.models import SkillDefinition, SkillResult

class TestSkillEngine:
    @pytest.fixture
    def engine(self):
        workflow_engine = AsyncMock()
        context_builder = AsyncMock()
        mcp_client = AsyncMock()
        return SkillEngine(
            workflow_engine=workflow_engine,
            context_builder=context_builder,
            mcp_client=mcp_client
        )

    def test_init(self, engine):
        assert engine.registry is not None
        assert engine.matcher is not None
        assert engine.executor is not None

    @pytest.mark.asyncio
    async def test_execute_not_found(self, engine):
        result = await engine.execute("nonexistent", {})
        assert result.status == "failed"
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_list_available_all(self, engine):
        engine.registry.register(SkillDefinition(name="a", workflows={"main": "wf"}))
        engine.registry.register(SkillDefinition(name="b", workflows={"main": "wf"}))
        result = await engine.list_available([])
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_available_filtered(self, engine):
        engine.registry.register(SkillDefinition(name="a", workflows={"main": "wf"}))
        engine.registry.register(SkillDefinition(name="b", workflows={"main": "wf"}))
        result = await engine.list_available(["a"])
        assert len(result) == 1
        assert result[0].name == "a"
