import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agent.loop import AgentLoop
from app.agent.models import AgentState, TaskResult, ExecutionMode
from app.skill.models import SkillDefinition, SkillMatch, SkillResult


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


class TestWorkflowLifecycle:
    """Tests for Workflow Lifecycle Mode routing"""

    def _make_loop(self, config_overrides=None):
        """Helper to create an AgentLoop with configurable settings"""
        defaults = {
            'max_iterations': 3,
            'checkpoint_interval': 1,
            'think_system_prompt': '',
            'reflect_system_prompt': '',
            'enable_workflow_lifecycle': True,
            'fast_path_confidence_threshold': 0.6,
            'enable_post_evaluation': False,
        }
        if config_overrides:
            defaults.update(config_overrides)
        config = MagicMock(**defaults)

        skill_engine = AsyncMock()
        skill_engine.registry = MagicMock()
        skill_engine.match = AsyncMock(return_value=[])
        skill_engine.execute = AsyncMock(return_value=SkillResult(
            status="success", data={"result": "ok"}, metrics={"tool_calls": 1}
        ))
        skill_engine.persist_workflow = AsyncMock(return_value=True)

        llm_client = AsyncMock()
        llm_client.complete = AsyncMock(
            return_value='{"reasoning": "test", "action_type": "respond", "response_text": "done"}'
        )

        loop = AgentLoop(
            agent_id="test-agent",
            skill_set=["test-skill"],
            skill_engine=skill_engine,
            llm_client=llm_client,
            state_store=AsyncMock(),
            config=config
        )
        return loop

    @pytest.mark.asyncio
    async def test_fast_path_skips_think_and_reflect(self):
        """Fast path should NOT call _think() or _reflect()"""
        loop = self._make_loop()

        fixed_skill = SkillDefinition(
            name="test-skill", type="fixed",
            workflows={"main": "test_wf"}
        )
        loop.skill_engine.registry.get = MagicMock(return_value=fixed_skill)
        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="test-skill", confidence=0.95)
        ])

        llm_call_count = [0]
        async def counting_complete(*args, **kwargs):
            llm_call_count[0] += 1
            return '{"reasoning": "test", "action_type": "respond", "response_text": "done"}'
        loop.llm_client.complete = counting_complete

        result = await loop.run("test task", {"key": "val"})

        assert result.status == "completed"
        assert result.execution_mode == ExecutionMode.FAST_PATH
        assert result.total_iterations == 1
        assert llm_call_count[0] == 0

    @pytest.mark.asyncio
    async def test_fast_path_calls_skill_engine_execute(self):
        """Fast path should delegate to SkillEngine.execute()"""
        loop = self._make_loop()

        fixed_skill = SkillDefinition(
            name="test-skill", type="fixed",
            workflows={"main": "test_wf"}
        )
        loop.skill_engine.registry.get = MagicMock(return_value=fixed_skill)
        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="test-skill", confidence=0.9)
        ])

        await loop.run("test task", {"key": "val"})

        loop.skill_engine.execute.assert_called_once_with(
            skill_name="test-skill",
            params={"key": "val"},
            trace_id=loop.trace_id
        )

    @pytest.mark.asyncio
    async def test_build_path_for_flexible_skill(self):
        """Build path should execute, persist, and return BUILD_PATH mode"""
        loop = self._make_loop()

        flexible_skill = SkillDefinition(
            name="flex-skill", type="flexible",
            process_description="Do something complex"
        )
        loop.skill_engine.registry.get = MagicMock(return_value=flexible_skill)
        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="flex-skill", confidence=0.85)
        ])
        loop.skill_engine.persist_workflow = AsyncMock(return_value=True)

        result = await loop.run("do something complex", {})

        assert result.status == "completed"
        assert result.execution_mode == ExecutionMode.BUILD_PATH
        assert result.execution_report.get("promoted_to_fixed") is True
        assert result.execution_report.get("workflow_persisted") is True
        loop.skill_engine.persist_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_react_when_no_match(self):
        """Should fall back to ReAct cycle when no skill matches"""
        loop = self._make_loop()

        loop.skill_engine.match = AsyncMock(return_value=[])

        result = await loop.run("unknown task", {})

        assert result.execution_mode == ExecutionMode.REACT

    @pytest.mark.asyncio
    async def test_fallback_to_react_when_low_confidence(self):
        """Should fall back to ReAct when match confidence is below threshold"""
        loop = self._make_loop({'fast_path_confidence_threshold': 0.8})

        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="test-skill", confidence=0.5)
        ])

        result = await loop.run("ambiguous task", {})

        assert result.execution_mode == ExecutionMode.REACT

    @pytest.mark.asyncio
    async def test_fallback_to_react_when_lifecycle_disabled(self):
        """Should use ReAct when workflow lifecycle is disabled"""
        loop = self._make_loop({'enable_workflow_lifecycle': False})

        fixed_skill = SkillDefinition(
            name="test-skill", type="fixed",
            workflows={"main": "test_wf"}
        )
        loop.skill_engine.registry.get = MagicMock(return_value=fixed_skill)
        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="test-skill", confidence=0.95)
        ])

        result = await loop.run("test task", {})

        assert result.execution_mode == ExecutionMode.REACT

    @pytest.mark.asyncio
    async def test_post_evaluation_on_fast_path(self):
        """When post_evaluation is enabled, fast path should call LLM once for evaluation"""
        loop = self._make_loop({'enable_post_evaluation': True})

        fixed_skill = SkillDefinition(
            name="test-skill", type="fixed",
            workflows={"main": "test_wf"}
        )
        loop.skill_engine.registry.get = MagicMock(return_value=fixed_skill)
        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="test-skill", confidence=0.95)
        ])

        eval_response = '{"quality": "good", "message": "Well done"}'
        llm_call_count = [0]
        async def counting_complete(*args, **kwargs):
            llm_call_count[0] += 1
            return eval_response
        loop.llm_client.complete = counting_complete

        result = await loop.run("test task", {})

        assert result.execution_mode == ExecutionMode.FAST_PATH
        assert llm_call_count[0] == 1
        assert result.execution_report["evaluation"]["quality"] == "good"

    @pytest.mark.asyncio
    async def test_fast_path_handles_degraded_success(self):
        """Fast path should return 'partial' status for degraded_success"""
        from app.skill.models import DegradationInfo
        loop = self._make_loop()

        fixed_skill = SkillDefinition(
            name="test-skill", type="fixed",
            workflows={"main": "test_wf"}
        )
        loop.skill_engine.registry.get = MagicMock(return_value=fixed_skill)
        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="test-skill", confidence=0.9)
        ])
        loop.skill_engine.execute = AsyncMock(return_value=SkillResult(
            status="degraded_success",
            data={"result": "partial"},
            degradation_info=DegradationInfo(
                original_error="tool timeout",
                trigger_type="degraded",
                fallback_workflow="fallback_wf",
                skipped_steps=["step1"]
            )
        ))

        result = await loop.run("test task", {})

        assert result.status == "partial"
        assert result.execution_mode == ExecutionMode.FAST_PATH
        assert result.degradation_info is not None

    @pytest.mark.asyncio
    async def test_fast_path_handles_failure(self):
        """Fast path should return 'failed' status when skill execution fails"""
        loop = self._make_loop()

        fixed_skill = SkillDefinition(
            name="test-skill", type="fixed",
            workflows={"main": "test_wf"}
        )
        loop.skill_engine.registry.get = MagicMock(return_value=fixed_skill)
        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="test-skill", confidence=0.9)
        ])
        loop.skill_engine.execute = AsyncMock(return_value=SkillResult(
            status="failed", error="tool unavailable"
        ))

        result = await loop.run("test task", {})

        assert result.status == "failed"
        assert result.execution_mode == ExecutionMode.FAST_PATH
        assert "tool unavailable" in result.message

    @pytest.mark.asyncio
    async def test_build_path_persistence_failure_is_non_fatal(self):
        """Build path should succeed even if persistence fails"""
        loop = self._make_loop()

        flexible_skill = SkillDefinition(
            name="flex-skill", type="flexible",
            process_description="Do something"
        )
        loop.skill_engine.registry.get = MagicMock(return_value=flexible_skill)
        loop.skill_engine.match = AsyncMock(return_value=[
            SkillMatch(skill_name="flex-skill", confidence=0.85)
        ])
        loop.skill_engine.persist_workflow = AsyncMock(return_value=False)

        result = await loop.run("do something", {})

        assert result.status == "completed"
        assert result.execution_mode == ExecutionMode.BUILD_PATH
        assert result.execution_report.get("workflow_persisted") is False
