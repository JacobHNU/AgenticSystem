import re
import json
import asyncio
import logging
import time
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

from .models import (
    WorkflowDefinition, WorkflowStep, StepType, StepResult, WorkflowResult, StepStatus, WorkflowMetrics
)
from .context import WorkflowContext
from ..core.trace import TraceContext

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Workflow execution engine with parallel support and metrics"""

    def __init__(self, mcp_client=None, context_builder=None, llm_client=None, workflows_dir: str = "./workflows"):
        self.definitions: Dict[str, WorkflowDefinition] = {}
        self.mcp_client = mcp_client
        self.context_builder = context_builder
        self.llm_client = llm_client
        self.workflows_dir = Path(workflows_dir)

    async def execute(
        self,
        workflow_name: str,
        context: WorkflowContext,
        trace_id: str = None
    ) -> WorkflowResult:
        trace_id = trace_id or TraceContext.get_or_create()
        start_time = time.time()

        workflow = self.definitions.get(workflow_name)
        if not workflow:
            return WorkflowResult(status="failed", error=f"Workflow '{workflow_name}' not found")

        metrics = WorkflowMetrics()
        completed_steps: Set[str] = set()
        failed_step: Optional[str] = None
        error_msg: Optional[str] = None

        # Helper to execute a single step
        async def run_step(step: WorkflowStep):
            nonlocal failed_step, error_msg
            if failed_step:
                return

            # Wait for dependencies
            for dep in step.depends_on:
                while dep not in completed_steps and not failed_step:
                    await asyncio.sleep(0.1)
            
            if failed_step:
                return

            # 1. Condition evaluation
            if step.condition and not self._evaluate_condition(context, step.condition):
                context.add_history(step.name, StepStatus.SKIPPED)
                completed_steps.add(step.name)
                return

            # 2. Build input
            step_input = self._build_input(context, step.input_template)

            # 3. Execute by type
            step_start = time.time()
            try:
                if step.type == StepType.MCP_TOOL:
                    metrics.tool_calls += 1
                    result = await self._execute_mcp_tool(step, step_input, trace_id)
                elif step.type == StepType.LLM_REASONING:
                    metrics.llm_calls += 1
                    result = await self._execute_llm_reasoning(step, step_input, context, trace_id)
                elif step.type == StepType.SUB_WORKFLOW:
                    result = await self._execute_sub_workflow(step, context, trace_id)
                    # Merge sub-workflow metrics if available
                    # (Simplified for now)
                elif step.type == StepType.SKILL_CALL:
                    result = await self._execute_skill_call(step, step_input, trace_id)
                else:
                    result = StepResult(status="failed", error=f"Unknown step type: {step.type}")
            except Exception as e:
                result = StepResult(status="failed", error=str(e))
            
            result.duration_ms = (time.time() - step_start) * 1000

            # 4. Handle result
            if result.status == "success":
                context.set(step.output_key, result.data)
                context.add_history(step.name, StepStatus.COMPLETED, result.data)
                completed_steps.add(step.name)
            else:
                context.add_history(step.name, StepStatus.FAILED, result.error)
                failed_step = step.name
                error_msg = result.error

        # Schedule all steps
        tasks = [asyncio.create_task(run_step(step)) for step in workflow.steps]
        await asyncio.gather(*tasks)

        metrics.total_duration_ms = (time.time() - start_time) * 1000
        metrics.completion_rate = len([h for h in context.history if h["status"] == StepStatus.COMPLETED]) / len(workflow.steps)

        if failed_step:
            return WorkflowResult(
                status="failed", error=error_msg,
                data=context.data, history=context.history,
                metrics=metrics
            )

        return WorkflowResult(
            status="success", data=context.data, history=context.history,
            metrics=metrics
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

    async def save_definition(self, definition: WorkflowDefinition) -> bool:
        """Persist a workflow definition to disk as YAML."""
        try:
            self.workflows_dir.mkdir(parents=True, exist_ok=True)
            file_path = self.workflows_dir / f"{definition.name}.yaml"
            data = definition.model_dump()
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Workflow '{definition.name}' saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save workflow '{definition.name}': {e}")
            return False

    async def load_definitions_from_disk(self) -> int:
        """Load all workflow YAML files from the workflows directory at startup."""
        if not self.workflows_dir.exists():
            return 0
        count = 0
        for yaml_file in self.workflows_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if data:
                    definition = WorkflowDefinition(**data)
                    self.definitions[definition.name] = definition
                    count += 1
            except Exception as e:
                logger.error(f"Failed to load workflow from {yaml_file}: {e}")
        logger.info(f"Loaded {count} workflow definitions from disk")
        return count

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
