import pytest
from unittest.mock import AsyncMock
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowDefinition, WorkflowStep, StepType, StepResult, WorkflowResult
from app.workflow.context import WorkflowContext

class TestWorkflowEngine:
    @pytest.fixture
    def mcp_client(self):
        client = AsyncMock()
        client.call_tool = AsyncMock(return_value=type("R", (), {"success": True, "data": {"verified": True}})())
        return client

    @pytest.fixture
    def engine(self, mcp_client):
        return WorkflowEngine(mcp_client=mcp_client, context_builder=None, llm_client=None)

    @pytest.mark.asyncio
    async def test_execute_simple_workflow(self, engine, mcp_client):
        workflow = WorkflowDefinition(
            name="test_wf",
            steps=[
                WorkflowStep(
                    name="step1",
                    type=StepType.MCP_TOOL,
                    mcp_tool="mcp-hr",
                    action="verify",
                    input_template={"id": "{{ user_id }}"},
                    output_key="result"
                )
            ]
        )
        engine.definitions["test_wf"] = workflow

        ctx = WorkflowContext(data={"user_id": "E001"})
        result = await engine.execute("test_wf", ctx, trace_id="test123")

        assert result.status == "success"
        assert ctx.get("result") == {"verified": True}

    @pytest.mark.asyncio
    async def test_skip_on_condition_false(self, engine):
        workflow = WorkflowDefinition(
            name="test_wf",
            steps=[
                WorkflowStep(
                    name="conditional_step",
                    type=StepType.MCP_TOOL,
                    mcp_tool="mcp-hr",
                    action="verify",
                    input_template={},
                    output_key="result",
                    condition="{{ approved }} == true"
                )
            ]
        )
        engine.definitions["test_wf"] = workflow

        ctx = WorkflowContext(data={"approved": "false"})
        result = await engine.execute("test_wf", ctx)

        assert result.status == "success"
        assert len(ctx.history) == 1
        assert ctx.history[0]["status"] == "SKIPPED"

    @pytest.mark.asyncio
    async def test_workflow_not_found(self, engine):
        ctx = WorkflowContext(data={})
        result = await engine.execute("nonexistent", ctx)
        assert result.status == "failed"
        assert "not found" in result.error
