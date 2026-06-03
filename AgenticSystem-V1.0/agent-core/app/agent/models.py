from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel


class Thought(BaseModel):
    """Think phase output"""
    reasoning: str = ""
    action_type: Literal["skill", "tool", "respond", "clarify"] = "respond"
    skill_name: Optional[str] = None
    tool_name: Optional[str] = None
    action: Optional[str] = None
    params: Dict[str, Any] = {}
    confidence: float = 0.0
    response_text: Optional[str] = None


class ActionResult(BaseModel):
    """Act phase output"""
    status: Literal["success", "degraded_success", "failed"] = "failed"
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    error_type: Optional[str] = None
    retry_after: Optional[float] = None
    degradation_info: Optional[Dict[str, Any]] = None


class Observation(BaseModel):
    """Observe phase output"""
    status: str = ""
    data_summary: str = ""
    key_findings: List[str] = []
    is_degraded: bool = False
    degradation_summary: Optional[str] = None
    error_summary: Optional[str] = None


class Reflection(BaseModel):
    """Reflect phase output"""
    should_stop: bool = False
    result: Optional["TaskResult"] = None
    next_action: Optional[str] = None
    reason: str = ""
    update_memory: List[str] = []
    update_scratch_pad: Dict[str, Any] = {}


class TaskResult(BaseModel):
    """Final task result"""
    status: Literal["completed", "partial", "failed", "escalated"] = "failed"
    data: Dict[str, Any] = {}
    message: str = ""
    degradation_info: Optional[Dict[str, Any]] = None
    total_iterations: int = 0
    trace_id: str = ""


# Rebuild to resolve forward reference from Reflection -> TaskResult
Reflection.model_rebuild()


class TaskFrame(BaseModel):
    """Task stack frame"""
    task: str
    context: Dict[str, Any] = {}


class AgentState(BaseModel):
    """Agent Loop persistent state"""
    agent_id: str
    session_id: str = ""
    skill_set: List[str] = []
    trace_id: str = ""
    memory: List[Dict[str, Any]] = []
    task_stack: List[TaskFrame] = []
    current_step: int = 0
    scratch_pad: Dict[str, Any] = {}
    workflow_context: Optional[Dict[str, Any]] = None
    version: int = 1
