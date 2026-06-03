import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from .models import (
    SkillDefinition, SkillResult, DegradationInfo,
    DegradationPolicy, FallbackEntry
)

logger = logging.getLogger(__name__)


class SkillExecutor:
    """Skill executor with degradation support"""

    def __init__(self, workflow_engine, context_builder, mcp_client=None):
        self.workflow_engine = workflow_engine
        self.context_builder = context_builder
        self.mcp_client = mcp_client

    async def execute(
        self,
        skill_def: SkillDefinition,
        params: Dict[str, Any],
        trace_id: str = None,
        max_iterations: int = None
    ) -> SkillResult:
        trace_id = trace_id or uuid.uuid4().hex[:16]
        logger.info(f"[{trace_id}] Execute skill: {skill_def.name}")

        # Build context (six layers)
        from ..context.models import ContextBuildRequest
        request = ContextBuildRequest(
            layers_config={k: v for k, v in skill_def.context.layers.items()},
            domain=skill_def.domain,
            variables=params,
            token_limit=skill_def.context.token_limit
        )
        context_result = await self.context_builder.build(request)

        # Execute with degradation
        from ..workflow.context import WorkflowContext
        wf_context = WorkflowContext(data=params)

        return await self._execute_with_degradation(
            skill_def=skill_def,
            workflow_name=skill_def.workflows.main,
            context=wf_context,
            trace_id=trace_id
        )

    async def _execute_with_degradation(
        self,
        skill_def: SkillDefinition,
        workflow_name: str,
        context,
        trace_id: str,
        depth: int = 0,
        accumulated_skipped: List[str] = None
    ) -> SkillResult:
        accumulated_skipped = accumulated_skipped or []
        max_depth = 2

        if depth >= max_depth:
            return SkillResult(
                status="failed",
                degradation_info=DegradationInfo(
                    original_error="Max degradation depth exceeded",
                    trigger_type="depth_limit",
                    fallback_workflow="escalate",
                    skipped_steps=accumulated_skipped,
                    timestamp=datetime.now()
                )
            )

        # Execute workflow
        wf_result = await self.workflow_engine.execute(
            workflow_name=workflow_name,
            context=context,
            trace_id=trace_id
        )

        # Success
        if wf_result.status == "success":
            if depth > 0:
                return SkillResult(
                    status="degraded_success",
                    data=wf_result.data,
                    degradation_info=DegradationInfo(
                        original_error="",
                        trigger_type="degraded",
                        fallback_workflow=workflow_name,
                        skipped_steps=accumulated_skipped,
                        timestamp=datetime.now()
                    )
                )
            return SkillResult(status="success", data=wf_result.data)

        # Failed - try degradation
        policy = skill_def.workflows.degradation_policy
        matched_fallback = self._match_fallback(wf_result.error, policy)

        if not matched_fallback or matched_fallback.action == "escalate":
            return SkillResult(
                status="failed",
                degradation_info=DegradationInfo(
                    original_error=wf_result.error,
                    trigger_type="escalate",
                    fallback_workflow="escalate",
                    skipped_steps=accumulated_skipped,
                    timestamp=datetime.now()
                )
            )

        # Accumulate skipped steps and recurse
        new_skipped = accumulated_skipped + (matched_fallback.skip_steps or [])
        logger.info(
            f"[{trace_id}] Degrading to {matched_fallback.workflow} "
            f"(depth={depth + 1}, skipped={new_skipped})"
        )

        return await self._execute_with_degradation(
            skill_def=skill_def,
            workflow_name=matched_fallback.workflow,
            context=context,
            trace_id=trace_id,
            depth=depth + 1,
            accumulated_skipped=new_skipped
        )

    def _match_fallback(self, error: str, policy: DegradationPolicy) -> Optional[FallbackEntry]:
        for fallback in policy.fallbacks:
            for condition in fallback.conditions:
                if self._evaluate_condition(condition, error):
                    return fallback
            if not fallback.conditions:
                return fallback
        return None

    def _evaluate_condition(self, condition: str, error: str) -> bool:
        if "==" in condition:
            parts = condition.split("==")
            key = parts[0].strip()
            value = parts[1].strip().strip('"').strip("'")
            if key == "error_type":
                return value in error.lower()
            if key == "always":
                return True
        if condition.strip() == "always":
            return True
        return False
