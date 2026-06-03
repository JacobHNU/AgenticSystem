from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class StepStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StepType(str, Enum):
    MCP_TOOL = "mcp_tool"
    LLM_REASONING = "llm_reasoning"
    SUB_WORKFLOW = "sub_workflow"
    SKILL_CALL = "skill_call"


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_ms: List[int] = [1000, 2000, 4000]


class WorkflowStep(BaseModel):
    name: str
    type: StepType
    mcp_tool: Optional[str] = None
    action: Optional[str] = None
    input_template: Dict[str, Any] = {}
    output_key: str = ""
    condition: Optional[str] = None
    retry: RetryConfig = RetryConfig()
    # For sub_workflow
    workflow: Optional[str] = None
    # For skill_call
    skill: Optional[str] = None
    timeout_ms: Optional[int] = None
    max_iterations: Optional[int] = None
    # For llm_reasoning
    domain: Optional[str] = None
    prompt_template: Optional[str] = None
    output_schema: Optional[Dict[str, str]] = None


class WorkflowDefinition(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    steps: List[WorkflowStep] = []


class StepResult(BaseModel):
    status: str
    data: Dict[str, Any] = {}
    error: Optional[str] = None


class WorkflowResult(BaseModel):
    status: str
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    history: List[Dict[str, Any]] = []
