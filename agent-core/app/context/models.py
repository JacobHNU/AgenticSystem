from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class LayerType(str, Enum):
    BASE = "L1_base"
    BUSINESS = "L2_business"
    DYNAMIC = "L3_dynamic"
    HISTORY = "L4_history"
    TOOLS = "L5_tools"
    OUTPUT = "L6_output"


class MergeStrategy(str, Enum):
    REPLACE = "replace"
    APPEND = "append"
    UNION = "union"


class LayerConfig(BaseModel):
    priority: int
    source: Optional[str] = None
    merge_strategy: MergeStrategy = MergeStrategy.REPLACE
    domain_filter: bool = False
    template_content: Optional[str] = None


class ContextBuildRequest(BaseModel):
    layers_config: Dict[str, LayerConfig]
    domain: str = ""
    variables: Dict[str, Any] = {}
    token_limit: int = 4000
    history: List[Dict[str, Any]] = []
    available_tools: List[Dict[str, Any]] = []
    user_info: Dict[str, Any] = {}
    workflow_context: Optional[Dict[str, Any]] = None
    mask_sensitive: bool = False
    sensitive_fields: List[str] = ["phone", "id_card", "email", "bank_card"]
    masking_config_path: Optional[str] = None


class ContextLayerResult(BaseModel):
    layer: LayerType
    content: str
    token_count: int
    priority: int


class ContextBuildResult(BaseModel):
    prompt: str
    total_tokens: int
    layer_details: List[ContextLayerResult]
    trimmed: bool = False
    trimmed_layers: List[str] = []
