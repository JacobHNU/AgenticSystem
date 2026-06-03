import logging
from typing import Dict, List, Any

from .models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillValidator:
    """Skill definition validator"""

    def validate(
        self,
        skill_def: SkillDefinition,
        workflow_registry: Dict[str, Any],
        all_skills: Dict[str, SkillDefinition]
    ) -> List[str]:
        errors = []

        if not skill_def.name:
            errors.append("missing 'name'")
        if not skill_def.version:
            errors.append("missing 'version'")
        if not skill_def.workflows.main:
            errors.append("missing 'workflows.main'")

        # Workflow existence
        if skill_def.workflows.main and skill_def.workflows.main not in workflow_registry:
            errors.append(f"workflow '{skill_def.workflows.main}' not found")

        for fallback in skill_def.workflows.degradation_policy.fallbacks:
            if fallback.workflow and fallback.workflow not in workflow_registry:
                errors.append(f"fallback workflow '{fallback.workflow}' not found")

        # Circular dependency detection
        if self._has_circular_dependency(skill_def, all_skills):
            errors.append("circular dependency detected in context_dependencies")

        # Template file existence
        if skill_def.base_dir:
            from pathlib import Path
            base = Path(skill_def.base_dir)
            for layer_name, layer_config in skill_def.context.layers.items():
                if layer_config.source:
                    template_path = base / layer_config.source
                    if not template_path.exists():
                        errors.append(f"template not found: {layer_config.source}")

        return errors

    def _has_circular_dependency(
        self, skill_def: SkillDefinition, all_skills: Dict[str, SkillDefinition]
    ) -> bool:
        visited = set()
        stack = [skill_def.name]
        while stack:
            current = stack.pop()
            if current in visited:
                return True
            visited.add(current)
            current_skill = all_skills.get(current)
            if current_skill and current_skill.activation_rules:
                for dep in current_skill.activation_rules.context_dependencies:
                    stack.append(dep.skill)
        return False
