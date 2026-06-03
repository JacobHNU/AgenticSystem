import re
import json
import asyncio
import logging
from typing import Dict, Any, Optional

from .models import (
    WorkflowDefinition, WorkflowStep, StepType, StepResult, WorkflowResult, StepStatus
)
from .context import WorkflowContext
from ..core.trace import TraceContext

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Workflow execution engine"""

    def __init__(self, mcp_client=None, context_builder=None, llm_client=None):
        self.definitions: Dict[str, WorkflowDefinition] = {}
        self.mcp_client = mcp_client
        self.context_builder = context_builder
        self.llm_client = llm_client

    async def execute(
        self,
        workflow_name: str,
        context: WorkflowContext,
        trace_id: str = None
    ) -> WorkflowResult:
        trace_id = trace_id or TraceContext.get_or_create()

        workflow = self.definitions.get(workflow_name)
        if not workflow:
            return WorkflowResult(status="failed", error=f"Workflow '{workflow_name}' not found")

        for step in workflow.steps:
            # 1. Condition evaluation
            if step.condition and not self._evaluate_condition(context, step.condition):
                context.add_history(step.name, StepStatus.SKIPPED)
                continue

            # 2. Build input
            step_input = self._build_input(context, step.input_template)

            # 3. Execute by type
            if step.type == StepType.MCP_TOOL:
                result = await self._execute_mcp_tool(step, step_input, trace_id)
            elif step.type == StepType.LLM_REASONING:
                result = await self._execute_llm_reasoning(step, step_input, context, trace_id)
            elif step.type == StepType.SUB_WORKFLOW:
                result = await self._execute_sub_workflow(step, context, trace_id)
            elif step.type == StepType.SKILL_CALL:
                result = await self._execute_skill_call(step, step_input, trace_id)
            else:
                result = StepResult(status="failed", error=f"Unknown step type: {step.type}")

            # 4. Handle result
            if result.status == "success":
                context.set(step.output_key, result.data)
                context.add_history(step.name, StepStatus.COMPLETED, result.data)
            else:
                context.add_history(step.name, StepStatus.FAILED, result.error)
                return WorkflowResult(
                    status="failed", error=result.error,
                    data=context.data, history=context.history
                )

        return WorkflowResult(
            status="success", data=context.data, history=context.history
        )

    def _build_input(self, ctx: WorkflowContext, template: Dict[str, Any]) -> Dict[str, Any]:
        """Build input from template with variable substitution"""
        def replace_var(match):
            var_path = match.group(1).strip()
            value = ctx.get(var_path, "")
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            if value is None:
                return '""'
            return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value

        rendered = json.dumps(template, ensure_ascii=False)
        pattern = r'\{\{\s*([^}]+)\s*\}\}'
        rendered = re.sub(pattern, replace_var, rendered)
        return json.loads(rendered)

    def _evaluate_condition(self, ctx: WorkflowContext, condition: str) -> bool:
        """Evaluate condition: supports {{ key }} == value"""
        pattern = r'\{\{\s*([^}]+)\s*\}\}\s*==\s*(.+)'
        match = re.match(pattern, condition.strip())
        if match:
            key, expected = match.groups()
            value = ctx.get(key.strip())
            expected = expected.strip().strip('"\'')
            return str(value) == expected
        return True

    async def _execute_mcp_tool(self, step: WorkflowStep, step_input: Dict, trace_id: str) -> StepResult:
        """Execute MCP tool step with retry"""
        for attempt in range(step.retry.max_attempts):
            try:
                response = await self.mcp_client.call_tool(
                    tool_name=step.mcp_tool,
                    action=step.action,
                    params=step_input,
                    retry_config=step.retry,
                    trace_id=trace_id
                )
                if response.success:
                    return StepResult(status="success", data=response.data)
                else:
                    if attempt < step.retry.max_attempts - 1:
                        await asyncio.sleep(step.retry.backoff_ms[attempt] / 1000)
            except Exception as e:
                if attempt == step.retry.max_attempts - 1:
                    return StepResult(status="failed", error=str(e))
        return StepResult(status="failed", error="Max retries exceeded")

    async def _execute_llm_reasoning(self, step: WorkflowStep, step_input: Dict,
                                      context: WorkflowContext, trace_id: str) -> StepResult:
        if not self.llm_client:
            return StepResult(status="failed", error="LLM client not configured")
        try:
            prompt = json.dumps(step_input, ensure_ascii=False)
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}]
            )
            return StepResult(status="success", data={"response": response})
        except Exception as e:
            return StepResult(status="failed", error=str(e))

    async def _execute_sub_workflow(self, step: WorkflowStep,
                                     context: WorkflowContext, trace_id: str) -> StepResult:
        sub_result = await self.execute(step.workflow, context, trace_id)
        return StepResult(
            status=sub_result.status,
            data=sub_result.data,
            error=sub_result.error
        )

    async def _execute_skill_call(self, step: WorkflowStep, step_input: Dict, trace_id: str) -> StepResult:
        if not hasattr(self, 'skill_engine') or not self.skill_engine:
            return StepResult(status="failed", error="Skill engine not configured")
        try:
            timeout = (step.timeout_ms or 30000) / 1000
            result = await asyncio.wait_for(
                self.skill_engine.execute(
                    skill_name=step.skill,
                    params=step_input,
                    trace_id=trace_id,
                    max_iterations=step.max_iterations
                ),
                timeout=timeout
            )
            return StepResult(status=result.status, data=result.data)
        except asyncio.TimeoutError:
            return StepResult(status="failed", error="Skill call timeout")
        except Exception as e:
            return StepResult(status="failed", error=str(e))
