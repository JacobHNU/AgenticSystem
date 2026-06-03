from app.core.exceptions import (
    AgentCoreError, SkillNotFoundError, WorkflowNotFoundError,
    ActivationRuleFailedError, MaxDegradationDepthError,
    CircuitOpenError, MaxIterationsError
)

def test_agent_core_error_has_details():
    err = AgentCoreError("test", details={"key": "val"})
    assert err.message == "test"
    assert err.details == {"key": "val"}
    assert err.error_type == "internal_error"
    assert err.status_code == 500

def test_skill_not_found_error():
    err = SkillNotFoundError("my-skill")
    assert err.status_code == 404
    assert "my-skill" in err.message

def test_circuit_open_error_has_retry_after():
    err = CircuitOpenError("mcp-finance", retry_after=60.0)
    assert err.details["retry_after"] == 60.0
    assert err.status_code == 503
