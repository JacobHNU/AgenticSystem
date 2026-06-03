import pytest
from app.skill.registry import SkillRegistry
from app.skill.models import SkillDefinition

class TestSkillRegistry:
    @pytest.fixture
    def registry(self):
        return SkillRegistry(max_history_versions=3)

    @pytest.fixture
    def skill_def(self):
        return SkillDefinition(name="test-skill", version="1.0.0", workflows={"main": "test_wf"})

    def test_register_and_get(self, registry, skill_def):
        registry.register(skill_def)
        result = registry.get("test-skill")
        assert result is not None
        assert result.name == "test-skill"

    def test_get_missing_returns_none(self, registry):
        assert registry.get("nonexistent") is None

    def test_replace_all_increments_version(self, registry, skill_def):
        registry.register(skill_def)
        new_def = SkillDefinition(name="test-skill", version="2.0.0", workflows={"main": "test_wf"})
        import asyncio
        asyncio.run(registry.replace_all({"test-skill": new_def}))
        assert registry._skills["test-skill"].version == 2

    def test_list_all(self, registry, skill_def):
        registry.register(skill_def)
        all_skills = registry.list_all()
        assert len(all_skills) == 1
        assert all_skills[0].name == "test-skill"

    def test_max_history_versions(self, registry, skill_def):
        import asyncio
        registry.register(skill_def)
        for i in range(5):
            new_def = SkillDefinition(name="test-skill", version=f"{i+2}.0.0", workflows={"main": "test_wf"})
            asyncio.run(registry.replace_all({"test-skill": new_def}))
        assert len(registry._history.get("test-skill", [])) <= 3
