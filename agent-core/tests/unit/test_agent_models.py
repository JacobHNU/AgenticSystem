import pytest
from app.agent.models import Thought, ActionResult, Observation, Reflection, TaskResult

def test_thought_parse():
    data = {
        "reasoning": "user wants expense reimbursement",
        "action_type": "skill",
        "skill_name": "expense-reimbursement",
        "params": {"amount": 3500},
        "confidence": 0.92
    }
    thought = Thought(**data)
    assert thought.action_type == "skill"
    assert thought.confidence == 0.92

def test_action_result_degraded():
    result = ActionResult(
        status="degraded_success",
        data={"ok": True},
        degradation_info={"skipped": ["risk_analysis"]}
    )
    assert result.status == "degraded_success"

def test_task_result():
    result = TaskResult(
        status="completed",
        message="done",
        total_iterations=2,
        trace_id="abc123"
    )
    assert result.total_iterations == 2
