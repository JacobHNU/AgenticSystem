import logging
from typing import Dict, Any, List

from .models import SkillDefinition, SkillResult, SkillSummary, SkillMatch
from .registry import SkillRegistry
from .matcher import SkillMatcher
from .executor import SkillExecutor
from .loader import SkillLoader
from .validator import SkillValidator
from .builder import DynamicWorkflowBuilder

logger = logging.getLogger(__name__)


class SkillEngine:
    """Skill Engine - Agent Loop's only execution entry point"""

    def __init__(self, workflow_engine, context_builder, mcp_client, llm_client=None, embedding_client=None):
        self.workflow_engine = workflow_engine
        self.context_builder = context_builder
        self.mcp_client = mcp_client
        self.llm_client = llm_client

        self.registry = SkillRegistry(max_history_versions=3)
        self.matcher = SkillMatcher(self.registry, embedding_client=embedding_client)
        self.dynamic_builder = DynamicWorkflowBuilder(llm_client) if llm_client else None
        self.executor = SkillExecutor(
            workflow_engine, context_builder, mcp_client, 
            dynamic_builder=self.dynamic_builder
        )
        self.validator = SkillValidator()
        self.loader: SkillLoader = None  # Set after init

    async def execute(
        self,
        skill_name: str,
        params: Dict[str, Any],
        trace_id: str = None,
        max_iterations: int = None
    ) -> SkillResult:
        skill_def = self.registry.get(skill_name)
        if not skill_def:
            return SkillResult(status="failed", error=f"Skill '{skill_name}' not found")
        
        result = await self.executor.execute(
            skill_def=skill_def,
            params=params,
            trace_id=trace_id,
            max_iterations=max_iterations
        )

        # Handle solidification if requested in result
        if result.status == "success" and "_dynamic_workflow" in result.data:
            from ..workflow.models import WorkflowDefinition
            wf_def = WorkflowDefinition(**result.data.pop("_dynamic_workflow"))
            await self.registry.promote_skill(skill_name, wf_def)
            # Persist to disk so it survives restarts
            await self.persist_workflow(wf_def.name)

        return result

    async def match(
        self,
        request: str,
        context: Dict = None,
        agent_skill_set: List[str] = None
    ) -> List[SkillMatch]:
        return await self.matcher.match(request, context, agent_skill_set)

    async def persist_workflow(self, workflow_name: str) -> bool:
        """Save a workflow definition to disk for persistence across restarts."""
        wf_def = self.workflow_engine.definitions.get(workflow_name)
        if not wf_def:
            logger.warning(f"Cannot persist: workflow '{workflow_name}' not found in engine")
            return False
        return await self.workflow_engine.save_definition(wf_def)

    async def list_available(self, agent_skill_set: List[str]) -> List[SkillSummary]:
        if agent_skill_set:
            return self.registry.list_by_names(agent_skill_set)
        return self.registry.list_all()

    async def reload(self, changed_files: List[str] = None):
        """Reload skills from disk"""
        if not self.loader:
            logger.warning("SkillLoader not configured, skipping reload")
            return

        if changed_files:
            new_skills = await self.loader.reload_changed(changed_files)
        else:
            new_skills = await self.loader.load_all()

        if new_skills:
            # Validate
            workflow_names = set(self.workflow_engine.definitions.keys())
            for name, skill_def in new_skills.items():
                errors = self.validator.validate(skill_def, workflow_names, dict(self.registry._skills))
                if errors:
                    logger.error(f"Skill '{name}' validation failed: {errors}")
                    continue

            await self.registry.replace_all(new_skills)
            logger.info(f"Reloaded {len(new_skills)} skills")
