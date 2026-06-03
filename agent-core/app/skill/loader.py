import yaml
import logging
from pathlib import Path
from typing import Dict, List

from .models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillLoader:
    """Skill definition loader from YAML files"""

    def __init__(self, skills_dir: str, embedding_client=None):
        self.skills_dir = Path(skills_dir)
        self.embedding_client = embedding_client

    async def load_all(self) -> Dict[str, SkillDefinition]:
        skills = {}
        if not self.skills_dir.exists():
            return skills

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            yaml_path = skill_dir / "skill.yaml"
            if not yaml_path.exists():
                continue
            try:
                skill_def = await self._load_skill(skill_dir)
                skills[skill_def.name] = skill_def
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_dir}: {e}")
        return skills

    async def _load_skill(self, skill_dir: Path) -> SkillDefinition:
        with open(skill_dir / "skill.yaml", 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f)

        skill_def = SkillDefinition(**raw)
        skill_def.base_dir = str(skill_dir)

        # Load context templates
        context_dir = skill_dir / "context"
        if context_dir.exists():
            for template_file in context_dir.glob("*.jinja2"):
                layer_name = template_file.stem
                if layer_name in skill_def.context.layers:
                    skill_def.context.layers[layer_name].template_content = \
                        template_file.read_text(encoding='utf-8')

        # Load prompts
        prompts_dir = skill_dir / "prompts"
        if prompts_dir.exists():
            think_path = prompts_dir / "think.md"
            if think_path.exists():
                skill_def.agent.think_prompt_content = think_path.read_text(encoding='utf-8')
            reflect_path = prompts_dir / "reflect.md"
            if reflect_path.exists():
                skill_def.agent.reflect_prompt_content = reflect_path.read_text(encoding='utf-8')

        # Pre-compute embedding
        if self.embedding_client and skill_def.intent.embedding_text:
            try:
                skill_def.intent.embedding_vector = \
                    await self.embedding_client.encode(skill_def.intent.embedding_text)
            except Exception as e:
                logger.warning(f"Failed to compute embedding for {skill_def.name}: {e}")

        return skill_def

    async def reload_changed(self, changed_files: List[str]) -> Dict[str, SkillDefinition]:
        affected_skills = set()
        for file_path in changed_files:
            parts = Path(file_path).relative_to(self.skills_dir).parts
            if len(parts) >= 1:
                affected_skills.add(parts[0])

        updated = {}
        for skill_name in affected_skills:
            skill_dir = self.skills_dir / skill_name
            if skill_dir.exists():
                skill_def = await self._load_skill(skill_dir)
                updated[skill_def.name] = skill_def
        return updated
