import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from .models import SkillDefinition, VersionedDefinition, SkillSummary

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Skill definition registry with version history and execution binding"""

    def __init__(self, max_history_versions: int = 3):
        self._skills: Dict[str, VersionedDefinition] = {}
        self._history: Dict[str, List[VersionedDefinition]] = {}
        self._active_bindings: Dict[str, int] = {}  # execution_id -> version
        self._max_history = max_history_versions
        self._lock = asyncio.Lock()

    def register(self, skill_def: SkillDefinition):
        self._skills[skill_def.name] = VersionedDefinition(
            version=1,
            definition=skill_def,
            created_at=datetime.now()
        )

    def get(self, name: str, execution_id: str = None) -> Optional[SkillDefinition]:
        versioned = self._skills.get(name)
        if not versioned:
            return None

        if execution_id and execution_id in self._active_bindings:
            bound_version = self._active_bindings[execution_id]
            if bound_version != versioned.version:
                return self._get_historical_version(name, bound_version)

        return versioned.definition

    def _get_historical_version(self, name: str, version: int) -> Optional[SkillDefinition]:
        history = self._history.get(name, [])
        for v in history:
            if v.version == version:
                return v.definition
        logger.warning(f"Historical version {version} not found for '{name}', using current")
        current = self._skills.get(name)
        return current.definition if current else None

    def bind(self, name: str, execution_id: str) -> SkillDefinition:
        versioned = self._skills.get(name)
        if not versioned:
            from ..core.exceptions import SkillNotFoundError
            raise SkillNotFoundError(name)
        self._active_bindings[execution_id] = versioned.version
        return versioned.definition

    def release(self, execution_id: str):
        self._active_bindings.pop(execution_id, None)

    def list_by_names(self, names: List[str]) -> List[SkillSummary]:
        return [self._skills[n].to_summary() for n in names if n in self._skills]

    def list_all(self) -> List[SkillSummary]:
        return [v.to_summary() for v in self._skills.values()]

    def count(self) -> int:
        return len(self._skills)

    async def promote_skill(self, name: str, workflow_def: Any):
        """Solidify a flexible skill into a fixed one with the provided workflow"""
        async with self._lock:
            versioned = self._skills.get(name)
            if not versioned:
                return

            # Update definition
            new_def = versioned.definition.model_copy(deep=True)
            new_def.type = "fixed"
            new_def.workflows.main = workflow_def.name
            
            # Save history
            if name not in self._history:
                self._history[name] = []
            self._history[name].append(versioned)
            if len(self._history[name]) > self._max_history:
                self._history[name] = self._history[name][-self._max_history:]

            # Update current
            self._skills[name] = VersionedDefinition(
                version=versioned.version + 1,
                definition=new_def,
                created_at=datetime.now()
            )
            logger.info(f"Skill '{name}' promoted to fixed mode (v{self._skills[name].version})")

    async def replace_all(self, new_skills: Dict[str, SkillDefinition]):
        async with self._lock:
            old_skills = self._skills.copy()
            try:
                self._skills = {
                    name: VersionedDefinition(
                        version=(old_skills[name].version + 1) if name in old_skills else 1,
                        definition=defn,
                        created_at=datetime.now()
                    )
                    for name, defn in new_skills.items()
                }

                for name, old_def in old_skills.items():
                    if name not in self._history:
                        self._history[name] = []
                    self._history[name].append(old_def)
                    if len(self._history[name]) > self._max_history:
                        self._history[name] = self._history[name][-self._max_history:]
            except Exception as e:
                self._skills = old_skills
                raise
