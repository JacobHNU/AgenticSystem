import pytest
from unittest.mock import AsyncMock
from app.skill.matcher import SkillMatcher
from app.skill.registry import SkillRegistry
from app.skill.models import SkillDefinition, IntentConfig, ActivationRules


class TestSkillMatcher:
    @pytest.fixture
    def registry_with_skills(self):
        registry = SkillRegistry()
        registry.register(SkillDefinition(
            name="expense-reimbursement",
            intent=IntentConfig(keywords=["报销", "费用"]),
            workflows={"main": "expense_wf"}
        ))
        registry.register(SkillDefinition(
            name="leave-request",
            intent=IntentConfig(keywords=["请假", "休假"]),
            workflows={"main": "leave_wf"}
        ))
        return registry

    @pytest.fixture
    def matcher(self, registry_with_skills):
        return SkillMatcher(registry=registry_with_skills)

    @pytest.mark.asyncio
    async def test_keyword_match(self, matcher):
        matches = await matcher.match("我要报销3500元")
        assert len(matches) > 0
        assert matches[0].skill_name == "expense-reimbursement"

    @pytest.mark.asyncio
    async def test_keyword_match_leave(self, matcher):
        matches = await matcher.match("我想请假三天")
        assert len(matches) > 0
        assert matches[0].skill_name == "leave-request"

    @pytest.mark.asyncio
    async def test_no_match(self, matcher):
        matches = await matcher.match("今天天气怎么样")
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_agent_skill_set_filter(self, matcher):
        matches = await matcher.match("我要报销", agent_skill_set=["leave-request"])
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_empty_agent_skill_set_uses_all(self, matcher):
        matches = await matcher.match("我要报销", agent_skill_set=[])
        assert len(matches) > 0
