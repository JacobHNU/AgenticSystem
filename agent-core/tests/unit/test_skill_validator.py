import pytest
from app.skill.validator import SkillValidator
from app.skill.models import SkillDefinition, WorkflowsConfig


class TestSkillValidator:
    @pytest.fixture
    def validator(self):
        return SkillValidator()

    def test_fixed_skill_requires_workflows_main(self, validator):
        """Fixed skill without workflows.main should fail validation"""
        skill = SkillDefinition(
            name="test", type="fixed", version="1.0.0",
            workflows=WorkflowsConfig(main="")
        )
        errors = validator.validate(skill, {}, {})
        assert any("workflows.main" in e for e in errors)

    def test_fixed_skill_with_valid_workflow_passes(self, validator):
        """Fixed skill with existing workflow should pass"""
        skill = SkillDefinition(
            name="test", type="fixed", version="1.0.0",
            workflows=WorkflowsConfig(main="test_wf")
        )
        errors = validator.validate(skill, {"test_wf": object()}, {})
        assert not any("workflows.main" in e for e in errors)

    def test_flexible_skill_without_workflows_main_passes(self, validator):
        """Flexible skill with process_description but no workflows.main should pass"""
        skill = SkillDefinition(
            name="test", type="flexible", version="1.0.0",
            process_description="Do something complex",
            workflows=WorkflowsConfig(main="")
        )
        errors = validator.validate(skill, {}, {})
        assert not any("workflows.main" in e for e in errors)

    def test_flexible_skill_requires_process_description(self, validator):
        """Flexible skill without process_description should fail"""
        skill = SkillDefinition(
            name="test", type="flexible", version="1.0.0",
            process_description=None,
            workflows=WorkflowsConfig(main="")
        )
        errors = validator.validate(skill, {}, {})
        assert any("process_description" in e for e in errors)

    def test_flexible_skill_with_main_workflow_validates_existence(self, validator):
        """If a flexible skill has workflows.main set, the workflow must exist"""
        skill = SkillDefinition(
            name="test", type="flexible", version="1.0.0",
            process_description="desc",
            workflows=WorkflowsConfig(main="nonexistent_wf")
        )
        errors = validator.validate(skill, {}, {})
        assert any("nonexistent_wf" in e for e in errors)

    def test_fixed_skill_missing_version_fails(self, validator):
        """Both types still require version"""
        skill = SkillDefinition(
            name="test", type="fixed", version="",
            workflows=WorkflowsConfig(main="wf")
        )
        errors = validator.validate(skill, {"wf": object()}, {})
        assert any("version" in e for e in errors)
