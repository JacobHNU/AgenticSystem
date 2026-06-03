import pytest
from unittest.mock import AsyncMock
from app.skill.executor import SkillExecutor
from app.skill.models import (
    SkillDefinition, WorkflowsConfig, DegradationPolicy, FallbackEntry,
    ContextConfig, SkillResult
)


class TestSkillExecutor:
    @pytest.fixture
    def workflow_engine(self):
        engine = AsyncMock()
        # First call fails, second succeeds (degradation)
        engine.execute = AsyncMock(side_effect=[
            type("R", (), {"status": "failed", "error": "tool_unavailable", "data": {}})(),
            type("R", (), {"status": "success", "data": {"result": "ok"}, "history": []})()
        ])
        return engine

    @pytest.fixture
    def context_builder(self):
        builder = AsyncMock()
        builder.build = AsyncMock(return_value=type("R", (), {"prompt": "test", "total_tokens": 10})())
        return builder

    @pytest.fixture
    def executor(self, workflow_engine, context_builder):
        return SkillExecutor(workflow_engine=workflow_engine, context_builder=context_builder, mcp_client=None)

    @pytest.mark.asyncio
    async def test_success_path(self, executor, workflow_engine):
        workflow_engine.execute = AsyncMock(
            return_value=type("R", (), {"status": "success", "data": {"ok": True}, "history": []})()
        )
        skill_def = SkillDefinition(
            name="test",
            workflows=WorkflowsConfig(main="test_wf"),
            context=ContextConfig()
        )
        result = await executor.execute(skill_def, {"key": "val"}, trace_id="t1")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_degradation_success(self, executor, workflow_engine):
        skill_def = SkillDefinition(
            name="test",
            workflows=WorkflowsConfig(
                main="main_wf",
                degradation_policy=DegradationPolicy(
                    fallbacks=[FallbackEntry(
                        workflow="fallback_wf",
                        skip_steps=["step1"],
                        conditions=["error_type == tool_unavailable"]
                    )]
                )
            ),
            context=ContextConfig()
        )
        result = await executor.execute(skill_def, {}, trace_id="t1")
        assert result.status == "degraded_success"
        assert result.degradation_info is not None
        assert "step1" in result.degradation_info.skipped_steps
