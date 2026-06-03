import uuid
import json
import logging
from typing import Dict, Any, List, Optional

from .models import (
    Thought, ActionResult, Observation, Reflection,
    TaskResult, AgentState, TaskFrame
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

        max_iter = getattr(self.config, 'max_iterations', 10)
        checkpoint_interval = getattr(self.config, 'checkpoint_interval', 3)

        for iteration in range(max_iter):
            try:
                # Think
                thought = await self._think(task, context)

                if thought.action_type == "respond":
                    return TaskResult(
                        status="completed", message=thought.response_text or "",
                        total_iterations=iteration + 1, trace_id=self.trace_id
                    )

                if thought.action_type == "clarify":
                    return TaskResult(
                        status="completed", message=thought.response_text or "",
                        data={"clarification_needed": True},
                        total_iterations=iteration + 1, trace_id=self.trace_id
                    )

                # Act
                action_result = await self._act(thought)

                # Observe
                observation = await self._observe(action_result)

                # Reflect
                reflection = await self._reflect(observation, thought)

                self._update_state(reflection)

                if reflection.should_stop:
                    return reflection.result or TaskResult(
                        status="completed", message="done",
                        total_iterations=iteration + 1, trace_id=self.trace_id
                    )

                if iteration % checkpoint_interval == 0:
                    await self._checkpoint()

            except Exception as e:
                logger.error(f"[{self.trace_id}] Agent loop error at iteration {iteration}: {e}")
                return TaskResult(
                    status="failed", message=str(e),
                    total_iterations=iteration + 1, trace_id=self.trace_id
                )

        return TaskResult(
            status="failed", message="Max iterations exceeded",
            total_iterations=max_iter, trace_id=self.trace_id
        )

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
                degradation_info=result.degradation_info.model_dump() if result.degradation_info else None
            )
        elif thought.action_type == "tool":
            response = await self.skill_engine.mcp_client.call_tool(
                tool_name=thought.tool_name, action=thought.action,
                params=thought.params, trace_id=self.trace_id
            )
            if response.success:
                return ActionResult(status="success", data=response.data)
            else:
                return ActionResult(
                    status="failed", error=response.error,
                    error_type=response.error_type, retry_after=response.retry_after
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
                key_findings.append(f"{key} = {str(value)[:100]}")

        return Observation(
            status=result.status,
            data_summary=json.dumps(result.data, ensure_ascii=False)[:500],
            key_findings=key_findings[:10],
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
Decide next step. Return JSON:
{{"should_stop": true/false, "result": {{"status": "...", "message": "..."}}, "reason": "...", "update_memory": ["..."]}}
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
