from typing import Any, Dict, List, Optional
from .models import StepStatus


class WorkflowContext:
    """Workflow execution context with variable storage and history"""

    def __init__(self, data: Dict[str, Any] = None):
        self.data: Dict[str, Any] = data or {}
        self.history: List[Dict[str, Any]] = []

    def set(self, key: str, value: Any):
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Support dotted key access: 'info.level' → data['info']['level']"""
        parts = key.split(".")
        current = self.data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def add_history(self, step_name: str, status: StepStatus, output: Any = None):
        entry = {
            "step": step_name,
            "status": status.value if isinstance(status, StepStatus) else status,
        }
        if output is not None:
            entry["output"] = output
        self.history.append(entry)
