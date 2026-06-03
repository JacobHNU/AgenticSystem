from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class MCPResponse(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # tool_unavailable | timeout | rate_limited
    retry_after: Optional[float] = None


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_ms: List[int] = [1000, 2000, 4000]


class ToolEndpoint(BaseModel):
    name: str
    url: str
    auth_type: Optional[str] = None
    auth_config: Dict[str, Any] = {}
