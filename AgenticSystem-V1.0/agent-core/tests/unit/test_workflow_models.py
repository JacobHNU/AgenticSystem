import pytest
from app.workflow.models import WorkflowStep, WorkflowDefinition, StepStatus
from app.workflow.context import WorkflowContext

class TestWorkflowContext:
    def test_set_and_get(self):
        ctx = WorkflowContext(data={"user_id": "E001"})
        ctx.set("employee_info", {"name": "test"})
        assert ctx.get("employee_info") == {"name": "test"}
        assert ctx.get("user_id") == "E001"

    def test_get_nested_key(self):
        ctx = WorkflowContext(data={"info": {"level": 5}})
        assert ctx.get("info.level") == 5

    def test_get_missing_returns_none(self):
        ctx = WorkflowContext(data={})
        assert ctx.get("nonexistent") is None

    def test_add_history(self):
        ctx = WorkflowContext(data={})
        ctx.add_history("step1", StepStatus.COMPLETED, {"result": "ok"})
        assert len(ctx.history) == 1
        assert ctx.history[0]["step"] == "step1"
        assert ctx.history[0]["status"] == "COMPLETED"

    def test_getattr_dotted(self):
        ctx = WorkflowContext(data={"a": {"b": {"c": 42}}})
        assert ctx.get("a.b.c") == 42
