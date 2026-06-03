import pytest
from app.skill.models import (
    SkillDefinition, IntentConfig, ActivationRules, Precondition,
    ContextDependency, DegradationPolicy, FallbackEntry, SkillResult,
    DegradationInfo, SkillMatch
)

def test_skill_result_degraded():
    info = DegradationInfo(
        original_error="tool unavailable",
        trigger_type="tool_unavailable",
        fallback_workflow="expense_no_risk",
        skipped_steps=["risk_analysis"]
    )
    result = SkillResult(status="degraded_success", data={"ok": True}, degradation_info=info)
    assert result.status == "degraded_success"
    assert "risk_analysis" in result.degradation_info.skipped_steps

def test_skill_match_sorting():
    matches = [
        SkillMatch(skill_name="a", confidence=0.5),
        SkillMatch(skill_name="b", confidence=0.9),
        SkillMatch(skill_name="c", confidence=0.7),
    ]
    matches.sort(key=lambda x: x.confidence, reverse=True)
    assert matches[0].skill_name == "b"
