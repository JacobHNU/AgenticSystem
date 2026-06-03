from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel


class IntentConfig(BaseModel):
    keywords: List[str] = []
    embedding_text: str = ""
    embedding_vector: Optional[List[float]] = None


class Precondition(BaseModel):
    type: str  # time_window | role_check | feature_flag
    config: Dict[str, Any] = {}


class ContextDependency(BaseModel):
    skill: str
    required: bool = True
    result_key: str = ""
    fallback_value: Optional[Dict[str, Any]] = None


class ActivationRules(BaseModel):
    preconditions: List[Precondition] = []
    context_dependencies: List[ContextDependency] = []
    logic: str = "AND"  # AND | OR


class FallbackEntry(BaseModel):
    workflow: str
    skip_steps: List[str] = []
    conditions: List[str] = []
    action: Optional[str] = None  # "escalate"


class DegradationPolicy(BaseModel):
    triggers: List[Dict[str, Any]] = []
    fallbacks: List[FallbackEntry] = []


class WorkflowsConfig(BaseModel):
    main: str
    degradation_policy: DegradationPolicy = DegradationPolicy()


class LayerConfig(BaseModel):
    priority: int
    source: Optional[str] = None
    merge_strategy: str = "replace"
    domain_filter: bool = False
    template_content: Optional[str] = None


class ContextConfig(BaseModel):
    template_dir: str = "./context"
    token_limit: int = 4000
    layers: Dict[str, LayerConfig] = {}
    masking: Optional[Dict[str, Any]] = None


class AgentConfig(BaseModel):
    think_prompt: str = ""
    reflect_prompt: str = ""
    think_prompt_content: Optional[str] = None
    reflect_prompt_content: Optional[str] = None
    max_iterations: int = 5
    confidence_threshold: float = 0.85


class SkillDefinition(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    domain: str = ""
    tags: List[str] = []
    intent: IntentConfig = IntentConfig()
    activation_rules: Optional[ActivationRules] = None
    workflows: WorkflowsConfig = WorkflowsConfig(main="")
    context: ContextConfig = ContextConfig()
    agent: AgentConfig = AgentConfig()
    permissions: Dict[str, Any] = {}
    base_dir: Optional[str] = None


class VersionedDefinition(BaseModel):
    version: int = 1
    definition: SkillDefinition
    created_at: datetime = None

    def __init__(self, **data):
        if 'created_at' not in data:
            data['created_at'] = datetime.now()
        super().__init__(**data)

    def to_summary(self) -> "SkillSummary":
        return SkillSummary(
            name=self.definition.name,
            version=self.definition.version,
            description=self.definition.description,
            domain=self.definition.domain,
            tags=self.definition.tags,
            intent=self.definition.intent,
            activation_rules=self.definition.activation_rules
        )


class SkillSummary(BaseModel):
    name: str
    version: str = ""
    description: str = ""
    domain: str = ""
    tags: List[str] = []
    intent: IntentConfig = IntentConfig()
    activation_rules: Optional[ActivationRules] = None


class DegradationInfo(BaseModel):
    original_error: str = ""
    trigger_type: str = ""
    fallback_workflow: str = ""
    skipped_steps: List[str] = []
    timestamp: datetime = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now()
        super().__init__(**data)


class SkillResult(BaseModel):
    status: Literal["success", "failed", "degraded_success"]
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    degradation_info: Optional[DegradationInfo] = None


class IntentMatch(BaseModel):
    skill_name: str
    score: float = 0.0
    method: str = ""  # keyword | embedding | hybrid
    matched_keywords: List[str] = []


class ActivationResult(BaseModel):
    activated: bool = False
    confidence: float = 0.0
    matched_rules: Dict[str, Any] = {}


class SkillMatch(BaseModel):
    skill_name: str
    confidence: float = 0.0
    matched_rules: Dict[str, Any] = {}
