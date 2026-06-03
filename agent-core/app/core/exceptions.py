from typing import Dict, Any, List, Optional


class AgentCoreError(Exception):
    """Base exception for Agent Core"""
    error_type: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str, details: Dict[str, Any] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class SkillNotFoundError(AgentCoreError):
    error_type = "skill_not_found"
    status_code = 404

    def __init__(self, skill_name: str):
        super().__init__(
            f"Skill '{skill_name}' not found",
            details={"skill_name": skill_name}
        )


class WorkflowNotFoundError(AgentCoreError):
    error_type = "workflow_not_found"
    status_code = 404

    def __init__(self, workflow_name: str):
        super().__init__(
            f"Workflow '{workflow_name}' not found",
            details={"workflow_name": workflow_name}
        )


class ActivationRuleFailedError(AgentCoreError):
    error_type = "activation_rule_failed"
    status_code = 403

    def __init__(self, skill_name: str, failed_rules: Dict):
        super().__init__(
            f"Skill '{skill_name}' activation rules failed",
            details={"skill_name": skill_name, "failed_rules": failed_rules}
        )


class MaxDegradationDepthError(AgentCoreError):
    error_type = "max_degradation_depth"
    status_code = 503

    def __init__(self, workflow_name: str, depth: int, skipped_steps: List[str]):
        super().__init__(
            f"Max degradation depth ({depth}) exceeded for workflow '{workflow_name}'",
            details={"workflow_name": workflow_name, "depth": depth, "skipped_steps": skipped_steps}
        )


class CircuitOpenError(AgentCoreError):
    error_type = "circuit_open"
    status_code = 503

    def __init__(self, tool_name: str, retry_after: float):
        super().__init__(
            f"Tool '{tool_name}' circuit breaker is open",
            details={"tool_name": tool_name, "retry_after": retry_after}
        )


class MaxIterationsError(AgentCoreError):
    error_type = "max_iterations_exceeded"
    status_code = 504

    def __init__(self, agent_id: str, max_iterations: int):
        super().__init__(
            f"Agent '{agent_id}' exceeded max iterations ({max_iterations})",
            details={"agent_id": agent_id, "max_iterations": max_iterations}
        )
