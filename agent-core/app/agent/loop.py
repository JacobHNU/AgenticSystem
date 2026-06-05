import uuid
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple

from .models import (
    Thought, ActionResult, Observation, Reflection,
    TaskResult, AgentState, TaskFrame, ExecutionMode
)

logger = logging.getLogger(__name__)


class AgentLoop:
    """Agent Loop - ReAct cycle: Think -> Act -> Observe -> Reflect"""

    def __init__(self, agent_id, skill_set, skill_engine, llm_client, state_store, config):
        self.agent_id = agent_id
        self.skill_set = skill_set
        self.skill_engine = skill_engine
        self.llm_client = llm_client
        self.state_store = state_store
        self.config = config
        self.state = AgentState(agent_id=agent_id, skill_set=skill_set)
        self.trace_id = ""

    async def run(self, task: str, context: Dict[str, Any] = None) -> TaskResult:
        self.trace_id = uuid.uuid4().hex[:16]
        self.state.trace_id = self.trace_id
        self.state.task_stack.append(TaskFrame(task=task, context=context or {}))
        context = context or {}

        # --- Workflow Lifecycle Mode Routing ---
        enable_lifecycle = getattr(self.config, 'enable_workflow_lifecycle', True)

        if enable_lifecycle:
            skill_name, match = await self._resolve_skill(task, context)

            if skill_name:
                skill_def = self.skill_engine.registry.get(skill_name)
                if skill_def:
                    if skill_def.type == "fixed" and skill_def.workflows.main:
                        logger.info(f"[{self.trace_id}] Fast path: skill '{skill_name}'")
                        return await self._fast_path(skill_name, skill_def, task, context)

                    if skill_def.type == "flexible" and skill_def.process_description:
                        logger.info(f"[{self.trace_id}] Build path: skill '{skill_name}'")
                        return await self._build_path(skill_name, skill_def, task, context)

        # --- Fallback: Full ReAct Cycle ---
        return await self._react_loop(task, context)

    async def _react_loop(self, task: str, context: Dict[str, Any]) -> TaskResult:
        """Full ReAct cycle: Think -> Act -> Observe -> Reflect (original behavior)."""
        max_iter = getattr(self.config, 'max_iterations', 10)
        checkpoint_interval = getattr(self.config, 'checkpoint_interval', 3)

        for iteration in range(max_iter):
            try:
                # Think
                thought = await self._think(task, context)

                if thought.action_type == "respond":
                    return TaskResult(
                        status="completed", message=thought.response_text or "",
                        total_iterations=iteration + 1, trace_id=self.trace_id,
                        execution_mode=ExecutionMode.REACT
                    )

                if thought.action_type == "clarify":
                    return TaskResult(
                        status="completed", message=thought.response_text or "",
                        data={"clarification_needed": True},
                        total_iterations=iteration + 1, trace_id=self.trace_id,
                        execution_mode=ExecutionMode.REACT
                    )

                # Act
                action_result = await self._act(thought)

                # Observe
                observation = await self._observe(action_result)

                # Reflect
                reflection = await self._reflect(observation, thought)

                self._update_state(reflection)

                if reflection.should_stop:
                    result = reflection.result or TaskResult(
                        status="completed", message="done",
                        total_iterations=iteration + 1, trace_id=self.trace_id,
                        execution_mode=ExecutionMode.REACT
                    )
                    result.execution_mode = ExecutionMode.REACT
                    return result

                if iteration % checkpoint_interval == 0:
                    await self._checkpoint()

            except Exception as e:
                logger.error(f"[{self.trace_id}] Agent loop error at iteration {iteration}: {e}")
                return TaskResult(
                    status="failed", message=str(e),
                    total_iterations=iteration + 1, trace_id=self.trace_id,
                    execution_mode=ExecutionMode.REACT
                )

        return TaskResult(
            status="failed", message="Max iterations exceeded",
            total_iterations=max_iter, trace_id=self.trace_id,
            execution_mode=ExecutionMode.REACT
        )

    async def _resolve_skill(self, task: str, context: Dict[str, Any]) -> Tuple[Optional[str], Optional[Any]]:
        """Resolve skill using matcher only (no LLM call). Returns (skill_name, match) or (None, None)."""
        min_confidence = getattr(self.config, 'fast_path_confidence_threshold', 0.6)

        matches = await self.skill_engine.match(
            request=task, context=context, agent_skill_set=self.skill_set
        )

        if not matches:
            return None, None

        best = matches[0]
        if best.confidence < min_confidence:
            logger.info(
                f"[{self.trace_id}] Best match '{best.skill_name}' "
                f"confidence {best.confidence:.2f} < threshold {min_confidence}"
            )
            return None, None

        return best.skill_name, best

    async def _fast_path(
        self, skill_name: str, skill_def, task: str, context: Dict[str, Any]
    ) -> TaskResult:
        """Execute a fixed skill's pre-defined workflow without Think/Reflect LLM calls."""
        try:
            result = await self.skill_engine.execute(
                skill_name=skill_name,
                params=context,
                trace_id=self.trace_id
            )

            # Optional post-execution evaluation
            evaluation = None
            enable_post_eval = getattr(self.config, 'enable_post_evaluation', False)
            if enable_post_eval:
                evaluation = await self._post_evaluate(task, context, result)

            if result.status == "success":
                return TaskResult(
                    status="completed",
                    message=evaluation.get("message", "Workflow executed successfully") if evaluation else "Workflow executed successfully",
                    data=result.data,
                    execution_report={
                        "metrics": result.metrics,
                        "evaluation": evaluation
                    },
                    total_iterations=1,
                    trace_id=self.trace_id,
                    execution_mode=ExecutionMode.FAST_PATH
                )
            elif result.status == "degraded_success":
                return TaskResult(
                    status="partial",
                    message=f"Degraded: {result.degradation_info.fallback_workflow if result.degradation_info else 'unknown'}",
                    data=result.data,
                    degradation_info=result.degradation_info.model_dump() if result.degradation_info else None,
                    execution_report={"metrics": result.metrics, "evaluation": evaluation},
                    total_iterations=1,
                    trace_id=self.trace_id,
                    execution_mode=ExecutionMode.FAST_PATH
                )
            else:
                return TaskResult(
                    status="failed",
                    message=result.error or "Workflow execution failed",
                    execution_report={"metrics": result.metrics},
                    total_iterations=1,
                    trace_id=self.trace_id,
                    execution_mode=ExecutionMode.FAST_PATH
                )

        except Exception as e:
            logger.error(f"[{self.trace_id}] Fast path failed for '{skill_name}': {e}")
            return TaskResult(
                status="failed",
                message=f"Fast path error: {str(e)}",
                total_iterations=1,
                trace_id=self.trace_id,
                execution_mode=ExecutionMode.FAST_PATH
            )

    async def _build_path(
        self, skill_name: str, skill_def, task: str, context: Dict[str, Any]
    ) -> TaskResult:
        """Build a workflow from process_description, execute it, optionally persist and promote."""
        try:
            result = await self.skill_engine.execute(
                skill_name=skill_name,
                params=context,
                trace_id=self.trace_id
            )

            if result.status == "success":
                # Persist workflow to disk for restart recovery
                dynamic_wf_name = f"{skill_name}_dynamic"
                persisted = await self.skill_engine.persist_workflow(dynamic_wf_name)
                if persisted:
                    logger.info(f"[{self.trace_id}] Dynamic workflow '{dynamic_wf_name}' persisted to disk")

                # Optional post-execution evaluation
                evaluation = None
                enable_post_eval = getattr(self.config, 'enable_post_evaluation', True)
                if enable_post_eval:
                    evaluation = await self._post_evaluate(task, context, result)

                return TaskResult(
                    status="completed",
                    message=evaluation.get("message", "Workflow built and executed successfully") if evaluation else "Workflow built and executed successfully",
                    data=result.data,
                    execution_report={
                        "metrics": result.metrics,
                        "evaluation": evaluation,
                        "workflow_persisted": persisted,
                        "promoted_to_fixed": True
                    },
                    total_iterations=1,
                    trace_id=self.trace_id,
                    execution_mode=ExecutionMode.BUILD_PATH
                )
            else:
                return TaskResult(
                    status="failed",
                    message=result.error or "Dynamic workflow execution failed",
                    execution_report={"metrics": result.metrics},
                    total_iterations=1,
                    trace_id=self.trace_id,
                    execution_mode=ExecutionMode.BUILD_PATH
                )

        except Exception as e:
            logger.error(f"[{self.trace_id}] Build path failed for '{skill_name}': {e}")
            return TaskResult(
                status="failed",
                message=f"Build path error: {str(e)}",
                total_iterations=1,
                trace_id=self.trace_id,
                execution_mode=ExecutionMode.BUILD_PATH
            )

    async def _post_evaluate(
        self, task: str, context: Dict[str, Any], skill_result
    ) -> Dict[str, Any]:
        """Single LLM call to evaluate execution quality after workflow completes."""
        prompt = f"""## Task
{task}

## Execution Result
Status: {skill_result.status}
Data: {json.dumps(skill_result.data, ensure_ascii=False)[:500]}

## Instructions
Evaluate the execution result. Was the task completed adequately?
Return JSON:
{{"quality": "good|acceptable|poor", "message": "...", "suggestions": ["..."]}}
"""
        try:
            system = getattr(self.config, 'post_evaluate_system_prompt', None) or \
                     "You are a task quality evaluator. Be concise."
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                system=system
            )
            return json.loads(response)
        except Exception as e:
            logger.warning(f"[{self.trace_id}] Post-evaluation failed: {e}")
            return {"quality": "unknown", "message": "Evaluation unavailable"}

    async def _think(self, task: str, context: Dict[str, Any]) -> Thought:
        matches = await self.skill_engine.match(
            request=task, context=context, agent_skill_set=self.skill_set
        )

        prompt = self._build_think_prompt(task, context, matches)

        system = getattr(self.config, 'think_system_prompt', None) or "You are a task planning agent."
        response = await self.llm_client.complete(
            messages=[{"role": "user", "content": prompt}],
            system=system
        )

        try:
            data = json.loads(response)
            thought = Thought(**data)
        except (json.JSONDecodeError, Exception):
            thought = Thought(reasoning=response, action_type="respond", response_text=response)

        # Validate skill selection
        if thought.action_type == "skill" and thought.skill_name:
            available = [m.skill_name for m in matches]
            if thought.skill_name not in available:
                if matches:
                    thought.skill_name = matches[0].skill_name
                else:
                    thought.action_type = "respond"
                    thought.response_text = "No matching skill found."

        return thought

    def _build_think_prompt(self, task: str, context: Dict, matches: List) -> str:
        skill_list = ""
        if matches:
            for i, m in enumerate(matches, 1):
                skill_list += f"### {i}. {m.skill_name} (confidence: {m.confidence:.2f})\n"
                skill_list += self._format_activation_details(m) + "\n"
        else:
            skill_list = "No matching skills\n"

        memory_lines = "\n".join(f"- {m}" for m in self.state.memory[-5:]) or "None"

        return f"""## Task
{task}

## Available Skills
{skill_list}

## Context
{json.dumps(context, ensure_ascii=False, indent=2) if context else "None"}

## Memory
{memory_lines}

## Instructions
Analyze the task and skill activation states. Choose the best action.

Return JSON:
{{"reasoning": "...", "action_type": "skill|tool|respond|clarify", "skill_name": "...", "params": {{}}, "confidence": 0.0}}
"""

    def _format_activation_details(self, match) -> str:
        lines = []
        rules = match.matched_rules
        if not rules:
            return "  Status: active (no rules)"

        all_passed = rules.get("all_passed", True)
        lines.append(f"  Status: {'active' if all_passed else 'inactive'}")

        preconditions = rules.get("preconditions", {})
        if preconditions:
            lines.append("  Preconditions:")
            for cond, passed in preconditions.items():
                lines.append(f"    {'pass' if passed else 'fail'} {cond}")

        dependencies = rules.get("dependencies", {})
        if dependencies:
            lines.append("  Dependencies:")
            for dep, passed in dependencies.items():
                lines.append(f"    {'pass' if passed else 'fail'} {dep}")

        return "\n".join(lines)

    async def _act(self, thought: Thought) -> ActionResult:
        if thought.action_type == "skill":
            result = await self.skill_engine.execute(
                skill_name=thought.skill_name,
                params=thought.params,
                trace_id=self.trace_id
            )
            return ActionResult(
                status=result.status, data=result.data,
                degradation_info=result.degradation_info.model_dump() if result.degradation_info else None,
                metrics=result.metrics
            )
        elif thought.action_type == "tool":
            start = time.time()
            response = await self.skill_engine.mcp_client.call_tool(
                tool_name=thought.tool_name, action=thought.action,
                params=thought.params, trace_id=self.trace_id
            )
            duration = (time.time() - start) * 1000
            if response.success:
                return ActionResult(status="success", data=response.data, metrics={"duration_ms": duration})
            else:
                return ActionResult(
                    status="failed", error=response.error,
                    error_type=response.error_type, retry_after=response.retry_after,
                    metrics={"duration_ms": duration}
                )
        return ActionResult(status="failed", error="Unknown action type")

    async def _observe(self, result: ActionResult) -> Observation:
        key_findings = []
        is_degraded = False
        degradation_summary = None
        error_summary = None

        if result.status == "degraded_success":
            is_degraded = True
            deg = result.degradation_info
            if deg:
                skipped = deg.get("skipped_steps", [])
                degradation_summary = f"Degraded via {deg.get('fallback_workflow', 'unknown')}, skipped: {', '.join(skipped) or 'none'}"
                key_findings.append(f"Degraded: {deg.get('fallback_workflow')}")

        elif result.status == "failed":
            error_summary = f"Failed: {result.error}"
            if result.retry_after:
                error_summary += f" (retry after {result.retry_after:.0f}s)"
            key_findings.append(f"Error: {result.error_type}")
        else:
            for key, value in result.data.items():
                if not key.startswith("_"): # Skip internal metadata
                    key_findings.append(f"{key} = {str(value)[:100]}")

        # Add metrics to findings
        if result.metrics:
            key_findings.append(f"Metrics: {json.dumps(result.metrics)}")

        return Observation(
            status=result.status,
            data_summary=json.dumps({k: v for k, v in result.data.items() if not k.startswith("_")}, ensure_ascii=False)[:500],
            key_findings=key_findings[:15],
            is_degraded=is_degraded,
            degradation_summary=degradation_summary,
            error_summary=error_summary
        )

    async def _reflect(self, observation: Observation, thought: Thought) -> Reflection:
        prompt = f"""## Execution Result
Status: {observation.status}
Key Findings:
{chr(10).join(f'- {f}' for f in observation.key_findings)}
{"Degradation: " + observation.degradation_summary if observation.is_degraded else ""}
{"Error: " + observation.error_summary if observation.error_summary else ""}

## Action Taken
Type: {thought.action_type}
Skill: {thought.skill_name or "N/A"}
Reasoning: {thought.reasoning}

## Instructions
Decide next step.
If the task is a 'flexible' skill that was just executed successfully, 
evaluate if the generated workflow is optimal and should be solidified.
Return JSON:
{{
  "should_stop": true/false, 
  "result": {{"status": "completed|failed", "message": "...", "execution_report": {{ "metrics": "..." }} }}, 
  "reason": "...", 
  "update_memory": ["..."],
  "solidify_workflow": true/false
}}
"""

        system = getattr(self.config, 'reflect_system_prompt', None) or "You are a task evaluation agent."
        response = await self.llm_client.complete(
            messages=[{"role": "user", "content": prompt}],
            system=system
        )

        try:
            data = json.loads(response)
            reflection = Reflection(**data)
        except (json.JSONDecodeError, Exception):
            reflection = Reflection(
                should_stop=True,
                reason="Failed to parse reflection",
                result=TaskResult(
                    status="completed" if observation.status == "success" else "failed",
                    message=observation.data_summary if observation.status == "success" else (observation.error_summary or "failed"),
                    trace_id=self.trace_id
                )
            )

        if reflection.should_stop and not reflection.result:
            if observation.status == "success":
                reflection.result = TaskResult(status="completed", message="Task completed", data={"summary": observation.data_summary}, trace_id=self.trace_id)
            elif observation.is_degraded:
                reflection.result = TaskResult(status="partial", message=f"Partial: {observation.degradation_summary}", trace_id=self.trace_id)
            else:
                reflection.result = TaskResult(status="failed", message=observation.error_summary or "Failed", trace_id=self.trace_id)

        return reflection

    def _update_state(self, reflection: Reflection):
        for item in reflection.update_memory:
            self.state.memory.append(item)
            if len(self.state.memory) > 50:
                self.state.memory = self.state.memory[-50:]
        self.state.scratch_pad.update(reflection.update_scratch_pad)

    async def _checkpoint(self):
        await self.state_store.save(self.state)

    async def pause(self):
        await self._checkpoint()

    async def resume(self):
        state = await self.state_store.load(self.agent_id)
        if state:
            self.state = state

    def event_stream(self):
        """Yield events for WebSocket streaming (placeholder)"""
        import asyncio
        return _EventStream(self)


class _EventStream:
    def __init__(self, agent_loop):
        self.agent_loop = agent_loop
        self._queue = []

    async def __aiter__(self):
        for event in self._queue:
            yield event
