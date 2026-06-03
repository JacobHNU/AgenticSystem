import pytest
import asyncio
from pathlib import Path
from app.skill.loader import SkillLoader
from app.skill.validator import SkillValidator
from app.skill.models import SkillDefinition

class TestSkillLoader:
    def test_load_from_yaml(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "skill.yaml").write_text("""
name: test-skill
version: "1.0.0"
description: "Test skill"
intent:
  keywords: ["test", "测试"]
workflows:
  main: test_workflow
""", encoding="utf-8")

        loader = SkillLoader(str(tmp_path))
        skills = asyncio.run(loader.load_all())
        assert "test-skill" in skills
        assert skills["test-skill"].intent.keywords == ["test", "测试"]

class TestSkillValidator:
    def test_valid_skill(self):
        validator = SkillValidator()
        skill = SkillDefinition(name="test", workflows={"main": "wf"})
        errors = validator.validate(skill, {"wf": True}, {})
        assert len(errors) == 0

    def test_missing_workflow(self):
        validator = SkillValidator()
        skill = SkillDefinition(name="test", workflows={"main": "nonexistent"})
        errors = validator.validate(skill, {}, {})
        assert any("not found" in e for e in errors)
