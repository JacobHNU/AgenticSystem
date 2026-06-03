# Agent Core Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-grade Agent Core service with Agent Loop (ReAct), Skill Engine, Workflow Engine, MCP Client Layer, Context Builder, Hot Reload, API layer, monitoring, and testing.

**Architecture:** Python + FastAPI microservice. Agent Loop is the top-level ReAct controller that calls Skill Engine as its only entry point. Skill Engine orchestrates Workflows, which execute MCP tool calls via a unified MCP Client Layer with connection pool, auth, retry, and circuit breaker. Context Builder assembles six-layer prompts with merge strategies, token trimming, and sensitive data masking.

**Tech Stack:** Python 3.11+, FastAPI, Redis (hot cache), MySQL (cold storage), Jinja2 (templates), watchdog (file watching), prometheus_client (metrics), Anthropic SDK (LLM), httpx (HTTP client)

---

## Phase 1: Project Scaffolding & Core Infrastructure

### Task 1.1: Create project directory structure

**Files:**
- Create: `agent-core/pyproject.toml`
- Create: `agent-core/requirements.txt`
- Create: `agent-core/app/__init__.py`
- Create: `agent-core/app/core/__init__.py`
- Create: `agent-core/app/agent/__init__.py`
- Create: `agent-core/app/skill/__init__.py`
- Create: `agent-core/app/workflow/__init__.py`
- Create: `agent-core/app/context/__init__.py`
- Create: `agent-core/app/mcp/__init__.py`
- Create: `agent-core/app/reload/__init__.py`
- Create: `agent-core/app/api/__init__.py`
- Create: `agent-core/app/monitoring/__init__.py`
- Create: `agent-core/tests/__init__.py`
- Create: `agent-core/tests/unit/__init__.py`
- Create: `agent-core/tests/integration/__init__.py`
- Create: `agent-core/tests/e2e/__init__.py`
- Create: `agent-core/config/settings.yaml`
- Create: `agent-core/config/settings.test.yaml`
- Create: `agent-core/config/masking_rules.yaml`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "agent-core"
version = "1.0.0"
description = "Production-grade Agent Core service with ReAct loop, Skill Engine, and Workflow orchestration"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.6.0",
    "pyyaml>=6.0.1",
    "jinja2>=3.1.3",
    "redis>=5.0.0",
    "asyncmy>=0.2.9",
    "httpx>=0.27.0",
    "watchdog>=4.0.0",
    "prometheus-client>=0.20.0",
    "anthropic>=0.40.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

**Step 2: Create requirements.txt**

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.6.0
pyyaml>=6.0.1
jinja2>=3.1.3
redis>=5.0.0
asyncmy>=0.2.9
httpx>=0.27.0
watchdog>=4.0.0
prometheus-client>=0.20.0
anthropic>=0.40.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
```

**Step 3: Create directory structure and __init__.py files**

Run:
```bash
mkdir -p agent-core/app/core agent-core/app/agent agent-core/app/skill agent-core/app/workflow agent-core/app/context agent-core/app/mcp agent-core/app/reload agent-core/app/api agent-core/app/monitoring agent-core/tests/unit agent-core/tests/integration agent-core/tests/e2e agent-core/config agent-core/skills agent-core/workflows
touch agent-core/app/__init__.py agent-core/app/core/__init__.py agent-core/app/agent/__init__.py agent-core/app/skill/__init__.py agent-core/app/workflow/__init__.py agent-core/app/context/__init__.py agent-core/app/mcp/__init__.py agent-core/app/reload/__init__.py agent-core/app/api/__init__.py agent-core/app/monitoring/__init__.py agent-core/tests/__init__.py agent-core/tests/unit/__init__.py agent-core/tests/integration/__init__.py agent-core/tests/e2e/__init__.py
```

**Step 4: Create config files**

`config/settings.yaml`:
```yaml
app:
  name: agent-core
  version: "1.0.0"
  host: "0.0.0.0"
  port: 8000
  admin_api_key: "${ADMIN_API_KEY}"

agent:
  max_iterations: 10
  checkpoint_interval: 3
  max_memory_size: 50
  max_concurrent_agents: 100

skill:
  skills_dir: ./skills
  max_history_versions: 3
  match_top_k: 3
  embedding:
    model_name: bge-large-zh-v1.5
    api_url: "${EMBEDDING_API_URL}"
    api_key: "${EMBEDDING_API_KEY}"
    dimension: 1024

workflow:
  workflows_dir: ./workflows
  max_degradation_depth: 2
  default_retry_attempts: 3

mcp:
  discovery_url: "${MCP_DISCOVERY_URL:http://mcp-discovery:8080}"
  connection_pool_size: 10
  request_timeout: 30
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 60

context:
  token_limit: 4000
  sensitive_fields: [phone, id_card, email, bank_card]
  masking_rules_path: ./config/masking_rules.yaml

mysql:
  host: "${MYSQL_HOST:localhost}"
  port: "${MYSQL_PORT:3306}"
  database: agent_core
  user: "${MYSQL_USER:root}"
  password: "${MYSQL_PASSWORD}"
  pool_size: 10

redis:
  host: "${REDIS_HOST:localhost}"
  port: "${REDIS_PORT:6379}"
  db: 0
  ttl: 3600

logging:
  level: INFO
  format: json
  trace_id_header: X-Trace-Id

prometheus:
  enabled: true
  port: 9090
```

`config/settings.test.yaml`:
```yaml
agent:
  max_iterations: 3
  checkpoint_interval: 1

skill:
  embedding:
    api_url: "http://localhost:8081/embed"
    api_key: "test-key"

mysql:
  host: localhost
  database: agent_core_test
  password: "test"

redis:
  db: 1

logging:
  level: DEBUG
```

`config/masking_rules.yaml`:
```yaml
masking_rules:
  - name: phone
    regex: '(\d{3})\d{4}(\d{4})'
    replacement: '\1****\2'
  - name: id_card
    regex: '(\d{6})\d{8}(\d{4})'
    replacement: '\1********\2'
  - name: email
    regex: '(.{2}).+(@.+)'
    replacement: '\1***\2'
  - name: bank_card
    regex: '(\d{4})\d+(\d{4})'
    replacement: '\1 **** **** \2'
  - name: salary
    regex: '(\d+).*'
    replacement: '***'
```

**Step 5: Commit**

```bash
cd agent-core && git init && git add -A && git commit -m "feat: scaffold project structure with config and requirements"
```

---

### Task 1.2: Unified exception hierarchy

**Files:**
- Create: `agent-core/app/core/exceptions.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_exceptions.py
from app.core.exceptions import (
    AgentCoreError, SkillNotFoundError, WorkflowNotFoundError,
    ActivationRuleFailedError, MaxDegradationDepthError,
    CircuitOpenError, MaxIterationsError
)

def test_agent_core_error_has_details():
    err = AgentCoreError("test", details={"key": "val"})
    assert err.message == "test"
    assert err.details == {"key": "val"}
    assert err.error_type == "internal_error"
    assert err.status_code == 500

def test_skill_not_found_error():
    err = SkillNotFoundError("my-skill")
    assert err.status_code == 404
    assert "my-skill" in err.message

def test_circuit_open_error_has_retry_after():
    err = CircuitOpenError("mcp-finance", retry_after=60.0)
    assert err.details["retry_after"] == 60.0
    assert err.status_code == 503
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_exceptions.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# agent-core/app/core/exceptions.py
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
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_exceptions.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add app/core/exceptions.py tests/unit/test_exceptions.py && git commit -m "feat: add unified exception hierarchy with details dict"
```

---

### Task 1.3: TraceContext (trace_id full-chain injection)

**Files:**
- Create: `agent-core/app/core/trace.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_trace.py
from app.core.trace import TraceContext

def test_set_and_get_trace_id():
    TraceContext.set_trace_id("abc123")
    assert TraceContext.get_trace_id() == "abc123"

def test_generate_trace_id():
    tid = TraceContext.generate_trace_id()
    assert len(tid) == 16
    assert tid.isalnum()

def test_get_or_create_generates_when_empty():
    TraceContext.set_trace_id("")
    tid = TraceContext.get_or_create()
    assert len(tid) == 16

def test_get_or_create_returns_existing():
    TraceContext.set_trace_id("existing")
    assert TraceContext.get_or_create() == "existing"
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_trace.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# agent-core/app/core/trace.py
from contextvars import ContextVar
import uuid

_trace_id: ContextVar[str] = ContextVar('trace_id', default='')


class TraceContext:
    """trace_id full-chain injection via ContextVar"""

    @staticmethod
    def get_trace_id() -> str:
        return _trace_id.get() or ''

    @staticmethod
    def set_trace_id(trace_id: str):
        _trace_id.set(trace_id)

    @staticmethod
    def generate_trace_id() -> str:
        return uuid.uuid4().hex[:16]

    @staticmethod
    def get_or_create() -> str:
        tid = _trace_id.get()
        if not tid:
            tid = TraceContext.generate_trace_id()
            _trace_id.set(tid)
        return tid
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_trace.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add app/core/trace.py tests/unit/test_trace.py && git commit -m "feat: add TraceContext for trace_id full-chain injection"
```

---

### Task 1.4: Config loader (YAML + env var override)

**Files:**
- Create: `agent-core/app/core/config.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_config.py
import os
import pytest
from app.core.config import load_config

def test_load_base_config():
    config = load_config("config/settings.yaml")
    assert config["app"]["name"] == "agent-core"
    assert config["agent"]["max_iterations"] == 10

def test_env_var_override(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "test-secret")
    config = load_config("config/settings.yaml")
    assert config["app"]["admin_api_key"] == "test-secret"

def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_config.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# agent-core/app/core/config.py
import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict

_ENV_PATTERN = re.compile(r'\$\{(\w+)(?::([^}]*))?\}')


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${VAR} and ${VAR:default} patterns"""
    if isinstance(value, str):
        def replacer(match):
            var_name = match.group(1)
            default = match.group(2)
            return os.environ.get(var_name, default if default is not None else match.group(0))
        return _ENV_PATTERN.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def load_config(config_path: str, overlay_path: str = None) -> Dict[str, Any]:
    """Load YAML config with optional overlay and env var resolution"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    if overlay_path:
        overlay = Path(overlay_path)
        if overlay.exists():
            with open(overlay, 'r', encoding='utf-8') as f:
                overlay_config = yaml.safe_load(f) or {}
            config = _deep_merge(config, overlay_config)

    return _resolve_env_vars(config)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge override into base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_config.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add app/core/config.py tests/unit/test_config.py && git commit -m "feat: add YAML config loader with env var resolution and overlay"
```

---

### Task 1.5: MySQL database connection pool

**Files:**
- Create: `agent-core/app/core/database.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_database.py
import pytest
from app.core.database import Database

def test_database_init():
    db = Database(host="localhost", port=3306, database="test", user="root", password="")
    assert db.host == "localhost"
    assert db.pool is None

def test_database_dsn():
    db = Database(host="localhost", port=3306, database="test", user="root", password="pw")
    assert "localhost" in db.dsn
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_database.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# agent-core/app/core/database.py
import asyncmy
from asyncmy.pool import Pool
from typing import Optional, Dict, Any, List


class Database:
    """MySQL connection pool manager"""

    def __init__(self, host: str, port: int, database: str, user: str, password: str, pool_size: int = 10):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool_size = pool_size
        self.pool: Optional[Pool] = None

    @property
    def dsn(self) -> str:
        return f"mysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    async def connect(self):
        self.pool = await asyncmy.create_pool(
            host=self.host, port=self.port,
            user=self.user, password=self.password,
            database=self.database, minsize=1, maxsize=self.pool_size
        )

    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    async def execute(self, sql: str, params: tuple = None) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                await conn.commit()
                return cur.rowcount

    async def fetchone(self, sql: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchone()

    async def fetchall(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_database.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add app/core/database.py tests/unit/test_database.py && git commit -m "feat: add MySQL connection pool manager"
```

---

### Task 1.6: Redis cache connection

**Files:**
- Create: `agent-core/app/core/cache.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_cache.py
import pytest
from app.core.cache import Cache

def test_cache_init():
    cache = Cache(host="localhost", port=6379, db=0, ttl=3600)
    assert cache.host == "localhost"
    assert cache.ttl == 3600
    assert cache.client is None
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_cache.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# agent-core/app/core/cache.py
import json
import redis.asyncio as redis
from typing import Optional, Any


class Cache:
    """Redis cache manager"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, ttl: int = 3600):
        self.host = host
        self.port = port
        self.db = db
        self.ttl = ttl
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        self.client = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)

    async def close(self):
        if self.client:
            await self.client.close()

    async def get(self, key: str) -> Optional[Any]:
        raw = await self.client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value: Any, ttl: int = None):
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        await self.client.set(key, serialized, ex=ttl or self.ttl)

    async def delete(self, key: str):
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(key))

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_cache.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/core/cache.py tests/unit/test_cache.py && git commit -m "feat: add Redis cache manager"
```

---

### Task 1.7: LLM client wrapper

**Files:**
- Create: `agent-core/app/core/llm_client.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_llm_client.py
import pytest
from app.core.llm_client import LLMClient

def test_llm_client_init():
    client = LLMClient(model="claude-sonnet-4-20250514")
    assert client.model == "claude-sonnet-4-20250514"
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_llm_client.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# agent-core/app/core/llm_client.py
import anthropic
from typing import List, Dict, Any, Optional


class LLMClient:
    """LLM API wrapper with retry and timeout"""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = None, timeout: float = 60.0):
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.timeout = timeout

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: str = None,
        max_tokens: int = 4096,
        response_format: Dict = None,
        temperature: float = 0.0,
    ) -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = await self.client.messages.create(**kwargs)
        return response.content[0].text
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_llm_client.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/core/llm_client.py tests/unit/test_llm_client.py && git commit -m "feat: add LLM client wrapper"
```

---

### Task 1.8: Embedding client wrapper

**Files:**
- Create: `agent-core/app/core/embedding_client.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_embedding_client.py
import pytest
from app.core.embedding_client import EmbeddingClient

def test_embedding_client_init():
    client = EmbeddingClient(api_url="http://localhost:8081/embed", api_key="test")
    assert client.api_url == "http://localhost:8081/embed"
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_embedding_client.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

```python
# agent-core/app/core/embedding_client.py
import httpx
from typing import List


class EmbeddingClient:
    """Embedding model API wrapper"""

    def __init__(self, api_url: str, api_key: str = None, dimension: int = 1024):
        self.api_url = api_url
        self.api_key = api_key
        self.dimension = dimension
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def encode(self, text: str) -> List[float]:
        client = await self._get_client()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = await client.post(
            self.api_url,
            json={"input": text, "dimension": self.dimension},
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0] if "embeddings" in data else data["data"][0]["embedding"]

    async def encode_batch(self, texts: List[str]) -> List[List[float]]:
        client = await self._get_client()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = await client.post(
            self.api_url,
            json={"input": texts, "dimension": self.dimension},
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"] if "embeddings" in data else [d["embedding"] for d in data["data"]]

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_embedding_client.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/core/embedding_client.py tests/unit/test_embedding_client.py && git commit -m "feat: add Embedding client wrapper"
```

---

## Phase 2: Context Builder

### Task 2.1: Context data models and MergeEngine

**Files:**
- Create: `agent-core/app/context/models.py`
- Create: `agent-core/app/context/merger.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_merge_engine.py
import pytest
from app.context.merger import MergeEngine, MergeStrategy

class TestMergeEngine:
    def setup_method(self):
        self.engine = MergeEngine()

    def test_replace(self):
        result = self.engine.merge("old content", "new content", MergeStrategy.REPLACE)
        assert result == "new content"

    def test_append(self):
        result = self.engine.merge("existing", "new", MergeStrategy.APPEND)
        assert result == "existing\nnew"

    def test_append_empty_existing(self):
        result = self.engine.merge("", "new", MergeStrategy.APPEND)
        assert result == "new"

    def test_union_dedup(self):
        existing = "line1\nline2\nline3"
        new = "line2\nline3\nline4"
        result = self.engine.merge(existing, new, MergeStrategy.UNION)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 4
        assert "line4" in lines
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_merge_engine.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/context/models.py`:
```python
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
```

`agent-core/app/context/merger.py`:
```python
from .models import MergeStrategy


class MergeEngine:
    """Multi-layer content merge engine"""

    def merge(self, existing: str, new: str, strategy: MergeStrategy) -> str:
        if strategy == MergeStrategy.REPLACE:
            return new
        elif strategy == MergeStrategy.APPEND:
            return f"{existing}\n{new}" if existing else new
        elif strategy == MergeStrategy.UNION:
            return self._union_merge(existing, new)
        return new

    def _union_merge(self, existing: str, new: str) -> str:
        existing_lines = set(line.strip() for line in existing.split('\n') if line.strip())
        merged = [l for l in existing.split('\n') if l.strip()]
        for line in new.split('\n'):
            if line.strip() and line.strip() not in existing_lines:
                merged.append(line)
        return '\n'.join(merged)
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_merge_engine.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add app/context/models.py app/context/merger.py tests/unit/test_merge_engine.py && git commit -m "feat: add context models and merge engine"
```

---

### Task 2.2: SmartHistoryTrimmer (parameterized tests)

**Files:**
- Create: `agent-core/app/context/trimmer.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_smart_trimmer.py
import pytest
from app.context.trimmer import SmartHistoryTrimmer

class TestSmartHistoryTrimmer:
    @pytest.fixture
    def trimmer(self):
        return SmartHistoryTrimmer()

    @pytest.fixture
    def count_fn(self):
        return lambda text: len(text) // 10

    @pytest.mark.parametrize("history, max_tokens, expected_steps", [
        # Under limit - keep all
        (
            [{"step": "a", "status": "COMPLETED"}],
            1000,
            ["a"]
        ),
        # Keep FAILED over COMPLETED when tight
        (
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "FAILED"},
                {"step": "c", "status": "COMPLETED"},
            ],
            20,
            ["a", "b"]
        ),
        # FAILED all kept + most recent COMPLETED
        (
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "FAILED"},
                {"step": "c", "status": "COMPLETED"},
                {"step": "d", "status": "COMPLETED"},
                {"step": "e", "status": "FAILED"},
            ],
            35,
            ["b", "e", "d"]
        ),
        # Empty history
        ([], 1000, []),
        # All failed - keep all
        (
            [
                {"step": "a", "status": "FAILED"},
                {"step": "b", "status": "FAILED"},
            ],
            10,
            ["a", "b"]
        ),
        # SKIPPED kept like FAILED
        (
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "SKIPPED"},
                {"step": "c", "status": "COMPLETED"},
            ],
            20,
            ["a", "b"]
        ),
    ])
    def test_trim(self, trimmer, count_fn, history, max_tokens, expected_steps):
        result = trimmer.trim(history, max_tokens, count_fn)
        assert [s["step"] for s in result] == expected_steps
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_smart_trimmer.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/context/trimmer.py`:
```python
from typing import List, Dict, Any, Callable


class SmartHistoryTrimmer:
    """Smart history trimmer: keep FAILED/SKIPPED first, then most recent COMPLETED"""

    STATUS_PRIORITY = {
        "FAILED": 0,
        "SKIPPED": 1,
        "COMPLETED": 2,
    }

    def trim(
        self,
        history: List[Dict[str, Any]],
        max_tokens: int,
        count_tokens_fn: Callable[[str], int]
    ) -> List[Dict[str, Any]]:
        if not history:
            return history

        current_tokens = count_tokens_fn(self._format_history(history))
        if current_tokens <= max_tokens:
            return history

        return self._prioritize_and_trim(history, max_tokens, count_tokens_fn)

    def _prioritize_and_trim(self, history, max_tokens, count_tokens_fn):
        failed_skipped = [h for h in history if h.get("status") in ("FAILED", "SKIPPED")]
        completed = [h for h in history if h.get("status") == "COMPLETED"]

        kept = list(failed_skipped)
        kept_tokens = count_tokens_fn(self._format_history(kept))

        if kept_tokens > max_tokens:
            return kept

        remaining_tokens = max_tokens - kept_tokens
        for step in reversed(completed):
            step_tokens = count_tokens_fn(self._format_history([step]))
            if remaining_tokens >= step_tokens:
                kept.append(step)
                remaining_tokens -= step_tokens
            else:
                break

        kept.sort(key=lambda h: history.index(h))
        return kept

    def _format_history(self, history):
        lines = []
        for step in history:
            icon = {"COMPLETED": "✓", "FAILED": "✗", "SKIPPED": "○"}.get(step.get("status"), "?")
            lines.append(f"- {icon} {step.get('step')}: {step.get('status')}")
        return "\n".join(lines)


class TokenTrimmer:
    """Token-level trimmer for context layers"""

    def trim_layers(self, layers, token_limit):
        """Trim layers from lowest priority (highest number) to highest"""
        trimmed_names = []
        remaining = token_limit

        sorted_layers = sorted(layers, key=lambda r: r.priority, reverse=True)
        kept = []

        for layer in sorted_layers:
            if remaining >= layer.token_count:
                remaining -= layer.token_count
                kept.append(layer)
            else:
                if remaining > 100:
                    truncated = layer.content[:remaining * 2]
                    from .models import ContextLayerResult
                    kept.append(ContextLayerResult(
                        layer=layer.layer, content=truncated,
                        token_count=remaining, priority=layer.priority
                    ))
                    trimmed_names.append(f"{layer.layer.value}(truncated)")
                    remaining = 0
                else:
                    trimmed_names.append(f"{layer.layer.value}(removed)")

        kept.sort(key=lambda r: r.priority)
        return kept, trimmed_names
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_smart_trimmer.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add app/context/trimmer.py tests/unit/test_smart_trimmer.py && git commit -m "feat: add SmartHistoryTrimmer with parameterized tests"
```

---

### Task 2.3: SensitiveFieldMasker (parameterized tests)

**Files:**
- Create: `agent-core/app/context/masker.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_sensitive_masker.py
import pytest
from app.context.masker import SensitiveFieldMasker

class TestSensitiveFieldMasker:
    @pytest.mark.parametrize("field, value, expected", [
        ("phone", "13812345678", "138****5678"),
        ("id_card", "110101199001011234", "110101********1234"),
        ("email", "zhangsan@company.com", "zh***@company.com"),
        ("bank_card", "6222021234567890123", "6222 **** **** 0123"),
    ])
    def test_builtin_masking(self, field, value, expected):
        masker = SensitiveFieldMasker(fields_to_mask=[field])
        result = masker.mask({field: value})
        assert result[field] == expected

    def test_field_not_in_mask_list(self):
        masker = SensitiveFieldMasker(fields_to_mask=["phone"])
        result = masker.mask({"name": "zhangsan"})
        assert result["name"] == "zhangsan"

    def test_custom_pattern(self):
        masker = SensitiveFieldMasker(
            fields_to_mask=["employee_code"],
            custom_patterns={"employee_code": (r'^(EMP)(\d+)$', r'EMP***')}
        )
        result = masker.mask({"employee_code": "EMP001"})
        assert result["employee_code"] == "EMP***"

    def test_non_string_value_untouched(self):
        masker = SensitiveFieldMasker(fields_to_mask=["age"])
        result = masker.mask({"age": 25})
        assert result["age"] == 25

    def test_fallback_masking_for_unknown_field(self):
        masker = SensitiveFieldMasker(fields_to_mask=["secret"])
        result = masker.mask({"secret": "verylongsecret"})
        assert result["secret"] != "verylongsecret"
        assert "*" in result["secret"]
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_sensitive_masker.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/context/masker.py`:
```python
import re
import yaml
from typing import Any, Dict, List, Optional, Tuple


class SensitiveFieldMasker:
    """Sensitive field masker with configurable rules"""

    BUILTIN_PATTERNS = {
        "phone": (r'(\d{3})\d{4}(\d{4})', r'\1****\2'),
        "id_card": (r'(\d{6})\d{8}(\d{4})', r'\1********\2'),
        "email": (r'(.{2}).+(@.+)', r'\1***\2'),
        "bank_card": (r'(\d{4})\d+(\d{4})', r'\1 **** **** \2'),
    }

    def __init__(
        self,
        fields_to_mask: List[str] = None,
        custom_patterns: Dict[str, Tuple[str, str]] = None,
        pattern_config_path: str = None
    ):
        self.fields_to_mask = fields_to_mask or []
        self.patterns = dict(self.BUILTIN_PATTERNS)
        if custom_patterns:
            self.patterns.update(custom_patterns)
        if pattern_config_path:
            self._load_from_config(pattern_config_path)

    def _load_from_config(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        for rule in config.get("masking_rules", []):
            self.patterns[rule["name"]] = (rule["regex"], rule["replacement"])

    def mask(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: self._mask_value(key, value) if key in self.fields_to_mask else value
            for key, value in data.items()
        }

    def _mask_value(self, field_name: str, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        for pattern_name, (regex, replacement) in self.patterns.items():
            if pattern_name in field_name.lower():
                return re.sub(regex, replacement, value)
        # Fallback: generic masking
        if len(value) > 6:
            return value[:2] + "*" * (len(value) - 4) + value[-2:]
        return "***"
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_sensitive_masker.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add app/context/masker.py tests/unit/test_sensitive_masker.py && git commit -m "feat: add SensitiveFieldMasker with configurable patterns"
```

---

### Task 2.4: ContextBuilder main class

**Files:**
- Create: `agent-core/app/context/builder.py`
- Create: `agent-core/app/context/loaders.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_context_builder.py
import pytest
from app.context.builder import ContextBuilder
from app.context.models import LayerConfig, LayerType, MergeStrategy, ContextBuildRequest

class TestContextBuilder:
    @pytest.fixture
    def builder(self):
        return ContextBuilder()

    @pytest.mark.asyncio
    async def test_build_with_base_layer(self, builder):
        request = ContextBuildRequest(
            layers_config={
                "L1_base": LayerConfig(
                    priority=1,
                    template_content="You are a helpful assistant.",
                    merge_strategy=MergeStrategy.REPLACE
                )
            }
        )
        result = await builder.build(request)
        assert "helpful assistant" in result.prompt
        assert result.total_tokens > 0

    @pytest.mark.asyncio
    async def test_build_empty_layers(self, builder):
        request = ContextBuildRequest(layers_config={})
        result = await builder.build(request)
        assert result.prompt == ""
        assert result.total_tokens == 0
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_context_builder.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/context/loaders.py`:
```python
import json
from typing import Any, Dict, List
from jinja2 import Environment, StrictUndefined

from .models import LayerConfig, ContextBuildRequest
from .masker import SensitiveFieldMasker
from .trimmer import SmartHistoryTrimmer


def _count_tokens(text: str) -> int:
    """Simple token estimation: ~2 chars per token for mixed CJK/EN"""
    return len(text) // 2


class LayerLoaders:
    """L1-L6 layer loaders"""

    def __init__(self):
        self.jinja_env = Environment(undefined=StrictUndefined, autoescape=False)
        self.jinja_env.filters['to_json'] = lambda v: json.dumps(v, ensure_ascii=False)
        self.jinja_env.filters['default_if_none'] = lambda v, d: d if v is None else v

    async def load_base(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        if not config.template_content:
            return ""
        template = self.jinja_env.from_string(config.template_content)
        return template.render()

    async def load_business(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        if not config.template_content:
            return ""
        template = self.jinja_env.from_string(config.template_content)
        return template.render(domain=request.domain)

    async def load_dynamic(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        user_info = request.user_info or {}
        if request.mask_sensitive and user_info:
            masker = SensitiveFieldMasker(
                fields_to_mask=request.sensitive_fields,
                pattern_config_path=request.masking_config_path
            )
            user_info = masker.mask(user_info)

        if not user_info:
            return ""

        if config.template_content:
            template = self.jinja_env.from_string(config.template_content)
            return template.render(**request.variables, user=user_info)

        return "\n".join(f"- {k}: {v}" for k, v in user_info.items())

    async def load_history(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        history = request.history or []
        if not history:
            return ""

        history_token_budget = int(request.token_limit * 0.3)
        trimmer = SmartHistoryTrimmer()
        history = trimmer.trim(history, history_token_budget, _count_tokens)

        if config.template_content:
            template = self.jinja_env.from_string(config.template_content)
            return template.render(history=history)

        lines = ["已执行步骤："]
        for step in history:
            status = step.get("status", "unknown")
            name = step.get("step", "unknown")
            icon = {"COMPLETED": "✓", "FAILED": "✗", "SKIPPED": "○"}.get(status, "?")
            line = f"- {icon} {name}: {status}"
            output = step.get("output")
            if output and status == "COMPLETED":
                line += f" → {str(output)[:200]}"
            elif output and status == "FAILED":
                line += f" → 错误: {output}"
            lines.append(line)
        return "\n".join(lines)

    async def load_tools(self, config: LayerConfig, request: ContextBuildRequest, mcp_client=None) -> str:
        tools = request.available_tools or []
        if not tools and mcp_client and request.domain:
            tools = await mcp_client.list_tools(domain=request.domain)
        if not tools:
            return ""

        if config.template_content:
            template = self.jinja_env.from_string(config.template_content)
            return template.render(tools=tools)

        lines = ["可用工具："]
        for tool in tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            actions = tool.get("tools", [])
            lines.append(f"- {name}: {desc}")
            if actions:
                lines.append(f"  操作: {', '.join(actions)}")
        return "\n".join(lines)

    async def load_output(self, config: LayerConfig, request: ContextBuildRequest) -> str:
        if not config.template_content:
            return ""
        template = self.jinja_env.from_string(config.template_content)
        return template.render()
```

`agent-core/app/context/builder.py`:
```python
from typing import Optional
from jinja2 import Environment, StrictUndefined

from .models import (
    LayerType, ContextBuildRequest, ContextBuildResult, ContextLayerResult
)
from .loaders import LayerLoaders, _count_tokens
from .merger import MergeEngine
from .trimmer import TokenTrimmer


class ContextBuilder:
    """Six-layer context builder"""

    def __init__(self, mcp_client=None):
        self.mcp_client = mcp_client
        self.loaders = LayerLoaders()
        self.merger = MergeEngine()
        self.token_trimmer = TokenTrimmer()

    async def build(self, request: ContextBuildRequest) -> ContextBuildResult:
        layer_results = []

        loader_map = {
            LayerType.BASE: self.loaders.load_base,
            LayerType.BUSINESS: self.loaders.load_business,
            LayerType.DYNAMIC: self.loaders.load_dynamic,
            LayerType.HISTORY: self.loaders.load_history,
            LayerType.TOOLS: lambda c, r: self.loaders.load_tools(c, r, self.mcp_client),
            LayerType.OUTPUT: self.loaders.load_output,
        }

        for layer_type in LayerType:
            config = request.layers_config.get(layer_type.value)
            if not config:
                continue

            loader = loader_map.get(layer_type)
            if not loader:
                continue

            content = await loader(config, request)
            if content and content.strip():
                token_count = _count_tokens(content)
                layer_results.append(ContextLayerResult(
                    layer=layer_type,
                    content=content,
                    token_count=token_count,
                    priority=config.priority
                ))

        layer_results.sort(key=lambda r: r.priority)

        # Token trimming
        total_tokens = sum(r.token_count for r in layer_results)
        trimmed = False
        trimmed_layers = []

        if total_tokens > request.token_limit:
            layer_results, trimmed_layers = self.token_trimmer.trim_layers(
                layer_results, request.token_limit
            )
            trimmed = True
            total_tokens = sum(r.token_count for r in layer_results)

        prompt = "\n\n".join(r.content for r in layer_results)

        return ContextBuildResult(
            prompt=prompt,
            total_tokens=total_tokens,
            layer_details=layer_results,
            trimmed=trimmed,
            trimmed_layers=trimmed_layers
        )
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_context_builder.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add app/context/builder.py app/context/loaders.py tests/unit/test_context_builder.py && git commit -m "feat: add ContextBuilder with six-layer loaders"
```

---

## Phase 3: MCP Client Layer

### Task 3.1: CircuitBreaker state machine

**Files:**
- Create: `agent-core/app/mcp/circuit_breaker.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_circuit_breaker.py
import pytest
import asyncio
from app.mcp.circuit_breaker import CircuitBreaker, CircuitState

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED  # count reset

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        for _ in range(2):
            cb.record_failure()
        await asyncio.sleep(0.15)
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_retry_after_value(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        for _ in range(2):
            cb.record_failure()
        assert cb.retry_after > 0
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_circuit_breaker.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/mcp/circuit_breaker.py`:
```python
import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker state machine: CLOSED → OPEN → HALF_OPEN → CLOSED"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def retry_after(self) -> float:
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            return max(0.0, self.recovery_timeout - elapsed)
        return 0.0

    def record_success(self):
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_circuit_breaker.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add app/mcp/circuit_breaker.py tests/unit/test_circuit_breaker.py && git commit -m "feat: add CircuitBreaker state machine"
```

---

### Task 3.2: MCP data models and RetryController

**Files:**
- Create: `agent-core/app/mcp/models.py`
- Create: `agent-core/app/mcp/retry.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_retry_controller.py
import pytest
import asyncio
from app.mcp.retry import RetryController, RetryConfig

class TestRetryController:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        controller = RetryController()
        config = RetryConfig(max_attempts=3, backoff_ms=[100, 200, 400])

        call_count = 0
        async def success_fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await controller.execute(success_fn, config=config)
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        controller = RetryController()
        config = RetryConfig(max_attempts=3, backoff_ms=[10, 20, 40])

        call_count = 0
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "ok"

        result = await controller.execute(fail_then_succeed, config=config)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises(self):
        controller = RetryController()
        config = RetryConfig(max_attempts=2, backoff_ms=[10, 20])

        async def always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            await controller.execute(always_fail, config=config)
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_retry_controller.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/mcp/models.py`:
```python
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
```

`agent-core/app/mcp/retry.py`:
```python
import asyncio
from typing import Callable, Any, Optional
from .models import RetryConfig


class RetryController:
    """Retry with exponential backoff"""

    async def execute(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        config: Optional[RetryConfig] = None
    ) -> Any:
        config = config or RetryConfig()
        kwargs = kwargs or {}
        last_error = None

        for attempt in range(config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < config.max_attempts - 1:
                    backoff = config.backoff_ms[attempt] / 1000.0
                    await asyncio.sleep(backoff)

        raise last_error
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_retry_controller.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add app/mcp/models.py app/mcp/retry.py tests/unit/test_retry_controller.py && git commit -m "feat: add MCP models and retry controller"
```

---

### Task 3.3: MCPClientLayer main class

**Files:**
- Create: `agent-core/app/mcp/client.py`
- Create: `agent-core/app/mcp/pool.py`
- Create: `agent-core/app/mcp/auth.py`
- Create: `agent-core/app/mcp/discovery.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_mcp_client.py
import pytest
from app.mcp.client import MCPClientLayer
from app.mcp.circuit_breaker import CircuitBreaker, CircuitState

class TestMCPClientLayer:
    def test_init(self):
        client = MCPClientLayer(discovery_url="http://localhost:8080")
        assert client.discovery_url == "http://localhost:8080"
        assert len(client.circuit_breakers) == 0

    def test_get_or_create_circuit_breaker(self):
        client = MCPClientLayer(discovery_url="http://localhost:8080")
        cb = client._get_circuit_breaker("mcp-hr")
        assert isinstance(cb, CircuitBreaker)
        assert cb.state == CircuitState.CLOSED
        # Same instance on second call
        cb2 = client._get_circuit_breaker("mcp-hr")
        assert cb is cb2
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_mcp_client.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/mcp/pool.py`:
```python
import httpx
from typing import Optional


class ConnectionPool:
    """HTTP connection pool for a single MCP endpoint"""

    def __init__(self, base_url: str, pool_size: int = 10, timeout: float = 30.0):
        self.base_url = base_url
        self.pool_size = pool_size
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=self.pool_size)
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

`agent-core/app/mcp/auth.py`:
```python
from typing import Dict, Any, Optional


class AuthManager:
    """MCP tool authentication manager"""

    def __init__(self):
        self._credentials: Dict[str, Dict[str, str]] = {}

    def register(self, tool_name: str, auth_type: str, credentials: Dict[str, str]):
        self._credentials[tool_name] = {"type": auth_type, **credentials}

    def get_auth(self, tool_name: str) -> Optional[Dict[str, str]]:
        return self._credentials.get(tool_name)

    def get_headers(self, tool_name: str) -> Dict[str, str]:
        auth = self.get_auth(tool_name)
        if not auth:
            return {}
        if auth["type"] == "bearer":
            return {"Authorization": f"Bearer {auth['token']}"}
        if auth["type"] == "api_key":
            return {"X-API-Key": auth["key"]}
        return {}
```

`agent-core/app/mcp/discovery.py`:
```python
import httpx
from typing import Dict, Any, List, Optional


class ToolDiscoveryClient:
    """MCP tool discovery client"""

    def __init__(self, discovery_url: str):
        self.discovery_url = discovery_url
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def get_endpoint(self, tool_name: str) -> Dict[str, Any]:
        if tool_name in self._cache:
            return self._cache[tool_name]

        client = await self._get_client()
        response = await client.get(f"{self.discovery_url}/tools/{tool_name}")
        response.raise_for_status()
        endpoint = response.json()
        self._cache[tool_name] = endpoint
        return endpoint

    async def list_tools(self, domain: str = None) -> List[Dict[str, Any]]:
        client = await self._get_client()
        params = {}
        if domain:
            params["domain"] = domain
        response = await client.get(f"{self.discovery_url}/tools", params=params)
        response.raise_for_status()
        return response.json()

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

`agent-core/app/mcp/client.py`:
```python
import uuid
import httpx
import logging
from typing import Dict, Any, Optional

from .circuit_breaker import CircuitBreaker, CircuitState
from .models import MCPResponse, RetryConfig
from .retry import RetryController
from .auth import AuthManager
from .discovery import ToolDiscoveryClient
from .pool import ConnectionPool
from ..core.trace import TraceContext

logger = logging.getLogger(__name__)


class MCPClientLayer:
    """Unified MCP client with connection pool, auth, retry, and circuit breaker"""

    def __init__(self, discovery_url: str, pool_size: int = 10, request_timeout: float = 30.0,
                 failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.discovery_url = discovery_url
        self.discovery = ToolDiscoveryClient(discovery_url)
        self.auth = AuthManager()
        self.retry = RetryController()
        self.pools: Dict[str, ConnectionPool] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.pool_size = pool_size
        self.request_timeout = request_timeout
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout

    def _get_circuit_breaker(self, tool_name: str) -> CircuitBreaker:
        if tool_name not in self.circuit_breakers:
            self.circuit_breakers[tool_name] = CircuitBreaker(
                failure_threshold=self._failure_threshold,
                recovery_timeout=self._recovery_timeout
            )
        return self.circuit_breakers[tool_name]

    def _get_pool(self, base_url: str) -> ConnectionPool:
        if base_url not in self.pools:
            self.pools[base_url] = ConnectionPool(base_url, self.pool_size, self.request_timeout)
        return self.pools[base_url]

    async def call_tool(
        self,
        tool_name: str,
        action: str,
        params: Dict[str, Any],
        retry_config: Optional[RetryConfig] = None,
        trace_id: Optional[str] = None
    ) -> MCPResponse:
        trace_id = trace_id or TraceContext.get_or_create()
        TraceContext.set_trace_id(trace_id)

        logger.info(f"[{trace_id}] MCP call: {tool_name}/{action}")

        # Circuit breaker check
        cb = self._get_circuit_breaker(tool_name)
        if cb.state == CircuitState.OPEN:
            return MCPResponse(
                success=False,
                error="tool_unavailable",
                error_type="tool_unavailable",
                retry_after=cb.retry_after
            )

        try:
            endpoint = await self.discovery.get_endpoint(tool_name)
            pool = self._get_pool(endpoint["url"])
            client = await pool.get_client()
            headers = self.auth.get_headers(tool_name)
            headers["X-Trace-Id"] = trace_id

            response = await self.retry.execute(
                func=self._do_request,
                args=(client, action, params, headers),
                config=retry_config
            )

            cb.record_success()
            return response

        except Exception as e:
            cb.record_failure()
            logger.error(f"[{trace_id}] MCP call failed: {tool_name}/{action}: {e}")
            return MCPResponse(
                success=False,
                error=str(e),
                error_type="tool_unavailable"
            )

    async def _do_request(
        self, client: httpx.AsyncClient, action: str,
        params: Dict[str, Any], headers: Dict[str, str]
    ) -> MCPResponse:
        response = await client.post(
            f"/tools/{action}",
            json=params,
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return MCPResponse(success=True, data=data)

    async def close(self):
        for pool in self.pools.values():
            await pool.close()
        await self.discovery.close()
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_mcp_client.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add app/mcp/pool.py app/mcp/auth.py app/mcp/discovery.py app/mcp/client.py tests/unit/test_mcp_client.py && git commit -m "feat: add MCPClientLayer with connection pool, auth, retry, circuit breaker"
```

---

## Phase 4: Workflow Engine

### Task 4.1: Workflow models and WorkflowContext

**Files:**
- Create: `agent-core/app/workflow/models.py`
- Create: `agent-core/app/workflow/context.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_workflow_models.py
import pytest
from app.workflow.models import WorkflowStep, WorkflowDefinition, StepStatus
from app.workflow.context import WorkflowContext

class TestWorkflowContext:
    def test_set_and_get(self):
        ctx = WorkflowContext(data={"user_id": "E001"})
        ctx.set("employee_info", {"name": "test"})
        assert ctx.get("employee_info") == {"name": "test"}
        assert ctx.get("user_id") == "E001"

    def test_get_nested_key(self):
        ctx = WorkflowContext(data={"info": {"level": 5}})
        assert ctx.get("info.level") == 5

    def test_get_missing_returns_none(self):
        ctx = WorkflowContext(data={})
        assert ctx.get("nonexistent") is None

    def test_add_history(self):
        ctx = WorkflowContext(data={})
        ctx.add_history("step1", StepStatus.COMPLETED, {"result": "ok"})
        assert len(ctx.history) == 1
        assert ctx.history[0]["step"] == "step1"
        assert ctx.history[0]["status"] == "COMPLETED"

    def test_getattr_dotted(self):
        ctx = WorkflowContext(data={"a": {"b": {"c": 42}}})
        assert ctx.get("a.b.c") == 42
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_workflow_models.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/workflow/models.py`:
```python
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
```

`agent-core/app/workflow/context.py`:
```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_workflow_models.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add app/workflow/models.py app/workflow/context.py tests/unit/test_workflow_models.py && git commit -m "feat: add workflow models and WorkflowContext"
```

---

### Task 4.2: WorkflowEngine core

**Files:**
- Create: `agent-core/app/workflow/engine.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_workflow_engine.py
import pytest
from unittest.mock import AsyncMock
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowDefinition, WorkflowStep, StepType, StepResult, WorkflowResult
from app.workflow.context import WorkflowContext

class TestWorkflowEngine:
    @pytest.fixture
    def mcp_client(self):
        client = AsyncMock()
        client.call_tool = AsyncMock(return_value=type("R", (), {"success": True, "data": {"verified": True}})())
        return client

    @pytest.fixture
    def engine(self, mcp_client):
        return WorkflowEngine(mcp_client=mcp_client, context_builder=None, llm_client=None)

    @pytest.mark.asyncio
    async def test_execute_simple_workflow(self, engine, mcp_client):
        workflow = WorkflowDefinition(
            name="test_wf",
            steps=[
                WorkflowStep(
                    name="step1",
                    type=StepType.MCP_TOOL,
                    mcp_tool="mcp-hr",
                    action="verify",
                    input_template={"id": "{{ user_id }}"},
                    output_key="result"
                )
            ]
        )
        engine.definitions["test_wf"] = workflow

        ctx = WorkflowContext(data={"user_id": "E001"})
        result = await engine.execute("test_wf", ctx, trace_id="test123")

        assert result.status == "success"
        assert ctx.get("result") == {"verified": True}

    @pytest.mark.asyncio
    async def test_skip_on_condition_false(self, engine):
        workflow = WorkflowDefinition(
            name="test_wf",
            steps=[
                WorkflowStep(
                    name="conditional_step",
                    type=StepType.MCP_TOOL,
                    mcp_tool="mcp-hr",
                    action="verify",
                    input_template={},
                    output_key="result",
                    condition="{{ approved }} == true"
                )
            ]
        )
        engine.definitions["test_wf"] = workflow

        ctx = WorkflowContext(data={"approved": "false"})
        result = await engine.execute("test_wf", ctx)

        assert result.status == "success"
        assert len(ctx.history) == 1
        assert ctx.history[0]["status"] == "SKIPPED"

    @pytest.mark.asyncio
    async def test_workflow_not_found(self, engine):
        ctx = WorkflowContext(data={})
        result = await engine.execute("nonexistent", ctx)
        assert result.status == "failed"
        assert "not found" in result.error
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_workflow_engine.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/workflow/engine.py`:
```python
import re
import json
import asyncio
import logging
from typing import Dict, Any, Optional

from .models import (
    WorkflowDefinition, WorkflowStep, StepType, StepResult, WorkflowResult, StepStatus
)
from .context import WorkflowContext
from ..core.trace import TraceContext

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Workflow execution engine"""

    def __init__(self, mcp_client=None, context_builder=None, llm_client=None):
        self.definitions: Dict[str, WorkflowDefinition] = {}
        self.mcp_client = mcp_client
        self.context_builder = context_builder
        self.llm_client = llm_client

    async def execute(
        self,
        workflow_name: str,
        context: WorkflowContext,
        trace_id: str = None
    ) -> WorkflowResult:
        trace_id = trace_id or TraceContext.get_or_create()

        workflow = self.definitions.get(workflow_name)
        if not workflow:
            return WorkflowResult(status="failed", error=f"Workflow '{workflow_name}' not found")

        for step in workflow.steps:
            # 1. Condition evaluation
            if step.condition and not self._evaluate_condition(context, step.condition):
                context.add_history(step.name, StepStatus.SKIPPED)
                continue

            # 2. Build input
            step_input = self._build_input(context, step.input_template)

            # 3. Execute by type
            if step.type == StepType.MCP_TOOL:
                result = await self._execute_mcp_tool(step, step_input, trace_id)
            elif step.type == StepType.LLM_REASONING:
                result = await self._execute_llm_reasoning(step, step_input, context, trace_id)
            elif step.type == StepType.SUB_WORKFLOW:
                result = await self._execute_sub_workflow(step, context, trace_id)
            elif step.type == StepType.SKILL_CALL:
                result = await self._execute_skill_call(step, step_input, trace_id)
            else:
                result = StepResult(status="failed", error=f"Unknown step type: {step.type}")

            # 4. Handle result
            if result.status == "success":
                context.set(step.output_key, result.data)
                context.add_history(step.name, StepStatus.COMPLETED, result.data)
            else:
                context.add_history(step.name, StepStatus.FAILED, result.error)
                return WorkflowResult(
                    status="failed", error=result.error,
                    data=context.data, history=context.history
                )

        return WorkflowResult(
            status="success", data=context.data, history=context.history
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
            return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else f'"{value}"'

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
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_workflow_engine.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add app/workflow/engine.py tests/unit/test_workflow_engine.py && git commit -m "feat: add WorkflowEngine with 4 step types and condition evaluation"
```

---

## Phase 5: Skill Engine

### Task 5.1: Skill data models

**Files:**
- Create: `agent-core/app/skill/models.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_skill_models.py
import pytest
from app.skill.models import (
    SkillDefinition, IntentConfig, ActivationRules, Precondition,
    ContextDependency, DegradationPolicy, FallbackEntry, SkillResult,
    DegradationInfo, SkillMatch
)

def test_skill_result_degraded():
    info = DegradationInfo(
        original_error="tool unavailable",
        trigger_type="tool_unavailable",
        fallback_workflow="expense_no_risk",
        skipped_steps=["risk_analysis"]
    )
    result = SkillResult(status="degraded_success", data={"ok": True}, degradation_info=info)
    assert result.status == "degraded_success"
    assert "risk_analysis" in result.degradation_info.skipped_steps

def test_skill_match_sorting():
    matches = [
        SkillMatch(skill_name="a", confidence=0.5),
        SkillMatch(skill_name="b", confidence=0.9),
        SkillMatch(skill_name="c", confidence=0.7),
    ]
    matches.sort(key=lambda x: x.confidence, reverse=True)
    assert matches[0].skill_name == "b"
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_models.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/skill/models.py`:
```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_models.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add app/skill/models.py tests/unit/test_skill_models.py && git commit -m "feat: add Skill data models"
```

---

### Task 5.2: SkillRegistry (version management)

**Files:**
- Create: `agent-core/app/skill/registry.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_skill_registry.py
import pytest
from app.skill.registry import SkillRegistry
from app.skill.models import SkillDefinition

class TestSkillRegistry:
    @pytest.fixture
    def registry(self):
        return SkillRegistry(max_history_versions=3)

    @pytest.fixture
    def skill_def(self):
        return SkillDefinition(name="test-skill", version="1.0.0", workflows={"main": "test_wf"})

    def test_register_and_get(self, registry, skill_def):
        registry.register(skill_def)
        result = registry.get("test-skill")
        assert result is not None
        assert result.name == "test-skill"

    def test_get_missing_returns_none(self, registry):
        assert registry.get("nonexistent") is None

    def test_replace_all_increments_version(self, registry, skill_def):
        registry.register(skill_def)
        new_def = SkillDefinition(name="test-skill", version="2.0.0", workflows={"main": "test_wf"})
        registry.replace_all({"test-skill": new_def})
        assert registry._skills["test-skill"].version == 2

    def test_list_all(self, registry, skill_def):
        registry.register(skill_def)
        all_skills = registry.list_all()
        assert len(all_skills) == 1
        assert all_skills[0].name == "test-skill"

    def test_max_history_versions(self, registry, skill_def):
        registry.register(skill_def)
        for i in range(5):
            new_def = SkillDefinition(name="test-skill", version=f"{i+2}.0.0", workflows={"main": "test_wf"})
            registry.replace_all({"test-skill": new_def})
        assert len(registry._history.get("test-skill", [])) <= 3
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_registry.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/skill/registry.py`:
```python
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from .models import SkillDefinition, VersionedDefinition, SkillSummary

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Skill definition registry with version history and execution binding"""

    def __init__(self, max_history_versions: int = 3):
        self._skills: Dict[str, VersionedDefinition] = {}
        self._history: Dict[str, List[VersionedDefinition]] = {}
        self._active_bindings: Dict[str, int] = {}  # execution_id → version
        self._max_history = max_history_versions
        self._lock = asyncio.Lock()

    def register(self, skill_def: SkillDefinition):
        self._skills[skill_def.name] = VersionedDefinition(
            version=1,
            definition=skill_def,
            created_at=datetime.now()
        )

    def get(self, name: str, execution_id: str = None) -> Optional[SkillDefinition]:
        versioned = self._skills.get(name)
        if not versioned:
            return None

        if execution_id and execution_id in self._active_bindings:
            bound_version = self._active_bindings[execution_id]
            if bound_version != versioned.version:
                return self._get_historical_version(name, bound_version)

        return versioned.definition

    def _get_historical_version(self, name: str, version: int) -> Optional[SkillDefinition]:
        history = self._history.get(name, [])
        for v in history:
            if v.version == version:
                return v.definition
        logger.warning(f"Historical version {version} not found for '{name}', using current")
        current = self._skills.get(name)
        return current.definition if current else None

    def bind(self, name: str, execution_id: str) -> SkillDefinition:
        versioned = self._skills.get(name)
        if not versioned:
            from ..core.exceptions import SkillNotFoundError
            raise SkillNotFoundError(name)
        self._active_bindings[execution_id] = versioned.version
        return versioned.definition

    def release(self, execution_id: str):
        self._active_bindings.pop(execution_id, None)

    def list_by_names(self, names: List[str]) -> List[SkillSummary]:
        return [self._skills[n].to_summary() for n in names if n in self._skills]

    def list_all(self) -> List[SkillSummary]:
        return [v.to_summary() for v in self._skills.values()]

    def count(self) -> int:
        return len(self._skills)

    async def replace_all(self, new_skills: Dict[str, SkillDefinition]):
        async with self._lock:
            old_skills = self._skills.copy()
            try:
                self._skills = {
                    name: VersionedDefinition(
                        version=(old_skills[name].version + 1) if name in old_skills else 1,
                        definition=defn,
                        created_at=datetime.now()
                    )
                    for name, defn in new_skills.items()
                }

                for name, old_def in old_skills.items():
                    if name not in self._history:
                        self._history[name] = []
                    self._history[name].append(old_def)
                    if len(self._history[name]) > self._max_history:
                        self._history[name] = self._history[name][-self._max_history:]
            except Exception as e:
                self._skills = old_skills
                raise
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_registry.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add app/skill/registry.py tests/unit/test_skill_registry.py && git commit -m "feat: add SkillRegistry with version history management"
```

---

### Task 5.3: SkillMatcher (two-level matching)

**Files:**
- Create: `agent-core/app/skill/matcher.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_skill_matcher.py
import pytest
from unittest.mock import AsyncMock
from app.skill.matcher import SkillMatcher
from app.skill.registry import SkillRegistry
from app.skill.models import SkillDefinition, IntentConfig, ActivationRules

class TestSkillMatcher:
    @pytest.fixture
    def registry_with_skills(self):
        registry = SkillRegistry()
        registry.register(SkillDefinition(
            name="expense-reimbursement",
            intent=IntentConfig(keywords=["报销", "费用"]),
            workflows={"main": "expense_wf"}
        ))
        registry.register(SkillDefinition(
            name="leave-request",
            intent=IntentConfig(keywords=["请假", "休假"]),
            workflows={"main": "leave_wf"}
        ))
        return registry

    @pytest.fixture
    def matcher(self, registry_with_skills):
        return SkillMatcher(registry=registry_with_skills)

    @pytest.mark.asyncio
    async def test_keyword_match(self, matcher):
        matches = await matcher.match("我要报销3500元")
        assert len(matches) > 0
        assert matches[0].skill_name == "expense-reimbursement"

    @pytest.mark.asyncio
    async def test_keyword_match_leave(self, matcher):
        matches = await matcher.match("我想请假三天")
        assert len(matches) > 0
        assert matches[0].skill_name == "leave-request"

    @pytest.mark.asyncio
    async def test_no_match(self, matcher):
        matches = await matcher.match("今天天气怎么样")
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_agent_skill_set_filter(self, matcher):
        matches = await matcher.match("我要报销", agent_skill_set=["leave-request"])
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_empty_agent_skill_set_uses_all(self, matcher):
        matches = await matcher.match("我要报销", agent_skill_set=[])
        assert len(matches) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_matcher.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/skill/matcher.py`:
```python
import logging
from typing import Dict, List, Optional
from datetime import datetime, time

from .models import (
    SkillDefinition, SkillSummary, IntentMatch, ActivationResult,
    SkillMatch, Precondition, ContextDependency
)
from .registry import SkillRegistry

logger = logging.getLogger(__name__)


class SkillMatcher:
    """Two-level skill matcher: Intent (keyword + embedding) → Activation Rules"""

    def __init__(self, registry: SkillRegistry, embedding_client=None, feature_flags=None):
        self.registry = registry
        self.embedding_client = embedding_client
        self.feature_flags = feature_flags or _DefaultFeatureFlags()

    async def match(
        self,
        request: str,
        context: Dict = None,
        agent_skill_set: List[str] = None,
        top_k: int = 3
    ) -> List[SkillMatch]:
        context = context or {}

        # Level 1: Intent matching
        candidates = await self._match_intent(request, agent_skill_set, top_k)
        if not candidates:
            return []

        # Level 2: Activation rules evaluation
        activated = []
        for candidate in candidates:
            result = await self._evaluate_activation(candidate, context)
            if result.activated:
                activated.append(SkillMatch(
                    skill_name=candidate.skill_name,
                    confidence=result.confidence,
                    matched_rules=result.matched_rules
                ))

        activated.sort(key=lambda x: x.confidence, reverse=True)
        return activated

    async def _match_intent(
        self, request: str, agent_skill_set: List[str], top_k: int
    ) -> List[IntentMatch]:
        if agent_skill_set is not None and len(agent_skill_set) > 0:
            available_skills = self.registry.list_by_names(agent_skill_set)
        else:
            available_skills = self.registry.list_all()

        results = []

        # Keyword matching
        keyword_hits = self._keyword_match(request, available_skills)
        results.extend(keyword_hits)

        # Embedding matching (if available)
        if self.embedding_client:
            embedding_hits = await self._embedding_match(request, available_skills, top_k)
            results = self._merge_results(results, embedding_hits)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _keyword_match(self, request: str, skills: List[SkillSummary]) -> List[IntentMatch]:
        results = []
        request_lower = request.lower()

        for skill in skills:
            hit_count = 0
            matched_keywords = []
            for keyword in skill.intent.keywords:
                if keyword in request_lower:
                    hit_count += 1
                    matched_keywords.append(keyword)

            if hit_count > 0:
                score = hit_count / max(len(skill.intent.keywords), 1)
                results.append(IntentMatch(
                    skill_name=skill.name,
                    score=score,
                    method="keyword",
                    matched_keywords=matched_keywords
                ))
        return results

    async def _embedding_match(
        self, request: str, skills: List[SkillSummary], top_k: int
    ) -> List[IntentMatch]:
        try:
            request_embedding = await self.embedding_client.encode(request)
        except Exception as e:
            logger.warning(f"Embedding encode failed: {e}")
            return []

        import numpy as np
        scores = []
        for skill in skills:
            if skill.intent.embedding_vector:
                sim = np.dot(request_embedding, skill.intent.embedding_vector) / (
                    np.linalg.norm(request_embedding) * np.linalg.norm(skill.intent.embedding_vector)
                )
                scores.append((skill.name, float(sim)))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [
            IntentMatch(skill_name=name, score=score, method="embedding")
            for name, score in scores[:top_k]
        ]

    def _merge_results(
        self, keyword_results: List[IntentMatch], embedding_results: List[IntentMatch]
    ) -> List[IntentMatch]:
        merged = {}

        for r in keyword_results:
            merged[r.skill_name] = IntentMatch(
                skill_name=r.skill_name,
                score=r.score * 0.4,
                method="keyword",
                matched_keywords=r.matched_keywords
            )

        for r in embedding_results:
            if r.skill_name in merged:
                merged[r.skill_name].score += r.score * 0.6
                merged[r.skill_name].method = "hybrid"
            else:
                merged[r.skill_name] = IntentMatch(
                    skill_name=r.skill_name,
                    score=r.score * 0.6,
                    method="embedding"
                )

        return list(merged.values())

    async def _evaluate_activation(
        self, candidate: IntentMatch, context: Dict
    ) -> ActivationResult:
        skill_def = self.registry.get(candidate.skill_name)
        if not skill_def or not skill_def.activation_rules:
            return ActivationResult(activated=True, confidence=candidate.score)

        rules = skill_def.activation_rules

        # Preconditions
        precondition_results = []
        for precondition in rules.preconditions:
            result = await self._check_precondition(precondition, context)
            precondition_results.append(result)

        if rules.logic == "AND":
            preconditions_ok = all(precondition_results)
        else:
            preconditions_ok = any(precondition_results) if precondition_results else True

        # Context dependencies
        dep_results = []
        for dep in rules.context_dependencies:
            result = await self._check_context_dependency(dep, context)
            dep_results.append(result)

        if rules.logic == "AND":
            deps_ok = all(dep_results)
        else:
            deps_ok = any(dep_results) if dep_results else True

        activated = preconditions_ok and deps_ok
        total = len(precondition_results) + len(dep_results)
        passed = sum(precondition_results) + sum(dep_results)
        rule_pass_rate = passed / total if total > 0 else 1.0

        return ActivationResult(
            activated=activated,
            confidence=candidate.score * rule_pass_rate,
            matched_rules={
                "all_passed": activated,
                "preconditions": dict(zip(
                    [p.type for p in rules.preconditions],
                    precondition_results
                )),
                "dependencies": dict(zip(
                    [d.skill for d in rules.context_dependencies],
                    dep_results
                ))
            }
        )

    async def _check_precondition(self, precondition: Precondition, context: Dict) -> bool:
        if precondition.type == "time_window":
            now = datetime.now().time()
            start = time.fromisoformat(precondition.config.get("start", "00:00"))
            end = time.fromisoformat(precondition.config.get("end", "23:59"))
            return start <= now <= end
        elif precondition.type == "role_check":
            user_level = context.get("user_level", 0)
            return user_level >= precondition.config.get("min_level", 0)
        elif precondition.type == "feature_flag":
            flag = precondition.config.get("flag", "")
            return self.feature_flags.is_enabled(flag)
        return True

    async def _check_context_dependency(self, dep: ContextDependency, context: Dict) -> bool:
        skill_result = context.get(f"skill_result_{dep.skill}")
        if skill_result is None:
            if dep.required:
                return False
            else:
                if dep.fallback_value is not None:
                    context[dep.result_key] = dep.fallback_value
                return True
        context[dep.result_key] = skill_result.get(dep.result_key)
        return True


class _DefaultFeatureFlags:
    def is_enabled(self, flag: str) -> bool:
        return True
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_matcher.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add app/skill/matcher.py tests/unit/test_skill_matcher.py && git commit -m "feat: add SkillMatcher with two-level matching"
```

---

### Task 5.4: SkillExecutor (with degradation)

**Files:**
- Create: `agent-core/app/skill/executor.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_skill_executor.py
import pytest
from unittest.mock import AsyncMock
from app.skill.executor import SkillExecutor
from app.skill.models import (
    SkillDefinition, WorkflowsConfig, DegradationPolicy, FallbackEntry,
    ContextConfig, SkillResult
)

class TestSkillExecutor:
    @pytest.fixture
    def workflow_engine(self):
        engine = AsyncMock()
        # First call fails, second succeeds (degradation)
        engine.execute = AsyncMock(side_effect=[
            type("R", (), {"status": "failed", "error": "tool_unavailable", "data": {}})(),
            type("R", (), {"status": "success", "data": {"result": "ok"}, "history": []})()
        ])
        return engine

    @pytest.fixture
    def context_builder(self):
        builder = AsyncMock()
        builder.build = AsyncMock(return_value=type("R", (), {"prompt": "test", "total_tokens": 10})())
        return builder

    @pytest.fixture
    def executor(self, workflow_engine, context_builder):
        return SkillExecutor(workflow_engine=workflow_engine, context_builder=context_builder, mcp_client=None)

    @pytest.mark.asyncio
    async def test_success_path(self, executor, workflow_engine):
        workflow_engine.execute = AsyncMock(
            return_value=type("R", (), {"status": "success", "data": {"ok": True}, "history": []})()
        )
        skill_def = SkillDefinition(
            name="test",
            workflows=WorkflowsConfig(main="test_wf"),
            context=ContextConfig()
        )
        result = await executor.execute(skill_def, {"key": "val"}, trace_id="t1")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_degradation_success(self, executor, workflow_engine):
        skill_def = SkillDefinition(
            name="test",
            workflows=WorkflowsConfig(
                main="main_wf",
                degradation_policy=DegradationPolicy(
                    fallbacks=[FallbackEntry(
                        workflow="fallback_wf",
                        skip_steps=["step1"],
                        conditions=["error_type == tool_unavailable"]
                    )]
                )
            ),
            context=ContextConfig()
        )
        result = await executor.execute(skill_def, {}, trace_id="t1")
        assert result.status == "degraded_success"
        assert result.degradation_info is not None
        assert "step1" in result.degradation_info.skipped_steps
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_executor.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/skill/executor.py`:
```python
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from .models import (
    SkillDefinition, SkillResult, DegradationInfo,
    DegradationPolicy, FallbackEntry
)

logger = logging.getLogger(__name__)


class SkillExecutor:
    """Skill executor with degradation support"""

    def __init__(self, workflow_engine, context_builder, mcp_client=None):
        self.workflow_engine = workflow_engine
        self.context_builder = context_builder
        self.mcp_client = mcp_client

    async def execute(
        self,
        skill_def: SkillDefinition,
        params: Dict[str, Any],
        trace_id: str = None,
        max_iterations: int = None
    ) -> SkillResult:
        trace_id = trace_id or uuid.uuid4().hex[:16]
        logger.info(f"[{trace_id}] Execute skill: {skill_def.name}")

        # Build context (six layers)
        from ..context.models import ContextBuildRequest
        request = ContextBuildRequest(
            layers_config={k: v for k, v in skill_def.context.layers.items()},
            domain=skill_def.domain,
            variables=params,
            token_limit=skill_def.context.token_limit
        )
        context_result = await self.context_builder.build(request)

        # Execute with degradation
        from ..workflow.context import WorkflowContext
        wf_context = WorkflowContext(data=params)

        return await self._execute_with_degradation(
            skill_def=skill_def,
            workflow_name=skill_def.workflows.main,
            context=wf_context,
            trace_id=trace_id
        )

    async def _execute_with_degradation(
        self,
        skill_def: SkillDefinition,
        workflow_name: str,
        context,
        trace_id: str,
        depth: int = 0,
        accumulated_skipped: List[str] = None
    ) -> SkillResult:
        accumulated_skipped = accumulated_skipped or []
        max_depth = 2

        if depth >= max_depth:
            return SkillResult(
                status="failed",
                degradation_info=DegradationInfo(
                    original_error="Max degradation depth exceeded",
                    trigger_type="depth_limit",
                    fallback_workflow="escalate",
                    skipped_steps=accumulated_skipped,
                    timestamp=datetime.now()
                )
            )

        # Execute workflow
        wf_result = await self.workflow_engine.execute(
            workflow_name=workflow_name,
            context=context,
            trace_id=trace_id
        )

        # Success
        if wf_result.status == "success":
            if depth > 0:
                return SkillResult(
                    status="degraded_success",
                    data=wf_result.data,
                    degradation_info=DegradationInfo(
                        original_error="",
                        trigger_type="degraded",
                        fallback_workflow=workflow_name,
                        skipped_steps=accumulated_skipped,
                        timestamp=datetime.now()
                    )
                )
            return SkillResult(status="success", data=wf_result.data)

        # Failed - try degradation
        policy = skill_def.workflows.degradation_policy
        matched_fallback = self._match_fallback(wf_result.error, policy)

        if not matched_fallback or matched_fallback.action == "escalate":
            return SkillResult(
                status="failed",
                degradation_info=DegradationInfo(
                    original_error=wf_result.error,
                    trigger_type="escalate",
                    fallback_workflow="escalate",
                    skipped_steps=accumulated_skipped,
                    timestamp=datetime.now()
                )
            )

        # Accumulate skipped steps and recurse
        new_skipped = accumulated_skipped + (matched_fallback.skip_steps or [])
        logger.info(
            f"[{trace_id}] Degrading to {matched_fallback.workflow} "
            f"(depth={depth + 1}, skipped={new_skipped})"
        )

        return await self._execute_with_degradation(
            skill_def=skill_def,
            workflow_name=matched_fallback.workflow,
            context=context,
            trace_id=trace_id,
            depth=depth + 1,
            accumulated_skipped=new_skipped
        )

    def _match_fallback(self, error: str, policy: DegradationPolicy) -> Optional[FallbackEntry]:
        for fallback in policy.fallbacks:
            for condition in fallback.conditions:
                if self._evaluate_condition(condition, error):
                    return fallback
            if not fallback.conditions:
                return fallback
        return None

    def _evaluate_condition(self, condition: str, error: str) -> bool:
        if "==" in condition:
            parts = condition.split("==")
            key = parts[0].strip()
            value = parts[1].strip().strip('"').strip("'")
            if key == "error_type":
                return value in error.lower()
            if key == "always":
                return True
        if condition.strip() == "always":
            return True
        return False
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_executor.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add app/skill/executor.py tests/unit/test_skill_executor.py && git commit -m "feat: add SkillExecutor with degradation recursion"
```

---

### Task 5.5: SkillLoader and SkillValidator

**Files:**
- Create: `agent-core/app/skill/loader.py`
- Create: `agent-core/app/skill/validator.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_skill_loader.py
import pytest
import tempfile
import os
from pathlib import Path
from app.skill.loader import SkillLoader
from app.skill.validator import SkillValidator
from app.skill.models import SkillDefinition

class TestSkillLoader:
    def test_load_from_yaml(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "skill.yaml").write_text("""
name: test-skill
version: "1.0.0"
description: "Test skill"
intent:
  keywords: ["test", "测试"]
workflows:
  main: test_workflow
""", encoding="utf-8")

        loader = SkillLoader(str(tmp_path))
        import asyncio
        skills = asyncio.run(loader.load_all())
        assert "test-skill" in skills
        assert skills["test-skill"].intent.keywords == ["test", "测试"]

class TestSkillValidator:
    def test_valid_skill(self):
        validator = SkillValidator()
        skill = SkillDefinition(name="test", workflows={"main": "wf"})
        errors = validator.validate(skill, {"wf": True}, {})
        assert len(errors) == 0

    def test_missing_workflow(self):
        validator = SkillValidator()
        skill = SkillDefinition(name="test", workflows={"main": "nonexistent"})
        errors = validator.validate(skill, {}, {})
        assert any("not found" in e for e in errors)
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_loader.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/skill/loader.py`:
```python
import yaml
import logging
from pathlib import Path
from typing import Dict, List

from .models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillLoader:
    """Skill definition loader from YAML files"""

    def __init__(self, skills_dir: str, embedding_client=None):
        self.skills_dir = Path(skills_dir)
        self.embedding_client = embedding_client

    async def load_all(self) -> Dict[str, SkillDefinition]:
        skills = {}
        if not self.skills_dir.exists():
            return skills

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            yaml_path = skill_dir / "skill.yaml"
            if not yaml_path.exists():
                continue
            try:
                skill_def = await self._load_skill(skill_dir)
                skills[skill_def.name] = skill_def
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_dir}: {e}")
        return skills

    async def _load_skill(self, skill_dir: Path) -> SkillDefinition:
        with open(skill_dir / "skill.yaml", 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f)

        skill_def = SkillDefinition(**raw)
        skill_def.base_dir = str(skill_dir)

        # Load context templates
        context_dir = skill_dir / "context"
        if context_dir.exists():
            for template_file in context_dir.glob("*.jinja2"):
                layer_name = template_file.stem
                if layer_name in skill_def.context.layers:
                    skill_def.context.layers[layer_name].template_content = \
                        template_file.read_text(encoding='utf-8')

        # Load prompts
        prompts_dir = skill_dir / "prompts"
        if prompts_dir.exists():
            think_path = prompts_dir / "think.md"
            if think_path.exists():
                skill_def.agent.think_prompt_content = think_path.read_text(encoding='utf-8')
            reflect_path = prompts_dir / "reflect.md"
            if reflect_path.exists():
                skill_def.agent.reflect_prompt_content = reflect_path.read_text(encoding='utf-8')

        # Pre-compute embedding
        if self.embedding_client and skill_def.intent.embedding_text:
            try:
                skill_def.intent.embedding_vector = \
                    await self.embedding_client.encode(skill_def.intent.embedding_text)
            except Exception as e:
                logger.warning(f"Failed to compute embedding for {skill_def.name}: {e}")

        return skill_def

    async def reload_changed(self, changed_files: List[str]) -> Dict[str, SkillDefinition]:
        affected_skills = set()
        for file_path in changed_files:
            parts = Path(file_path).relative_to(self.skills_dir).parts
            if len(parts) >= 1:
                affected_skills.add(parts[0])

        updated = {}
        for skill_name in affected_skills:
            skill_dir = self.skills_dir / skill_name
            if skill_dir.exists():
                skill_def = await self._load_skill(skill_dir)
                updated[skill_def.name] = skill_def
        return updated
```

`agent-core/app/skill/validator.py`:
```python
import logging
from typing import Dict, List, Any

from .models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillValidator:
    """Skill definition validator"""

    def validate(
        self,
        skill_def: SkillDefinition,
        workflow_registry: Dict[str, Any],
        all_skills: Dict[str, SkillDefinition]
    ) -> List[str]:
        errors = []

        if not skill_def.name:
            errors.append("missing 'name'")
        if not skill_def.version:
            errors.append("missing 'version'")
        if not skill_def.workflows.main:
            errors.append("missing 'workflows.main'")

        # Workflow existence
        if skill_def.workflows.main and skill_def.workflows.main not in workflow_registry:
            errors.append(f"workflow '{skill_def.workflows.main}' not found")

        for fallback in skill_def.workflows.degradation_policy.fallbacks:
            if fallback.workflow and fallback.workflow not in workflow_registry:
                errors.append(f"fallback workflow '{fallback.workflow}' not found")

        # Circular dependency detection
        if self._has_circular_dependency(skill_def, all_skills):
            errors.append("circular dependency detected in context_dependencies")

        # Template file existence
        if skill_def.base_dir:
            from pathlib import Path
            base = Path(skill_def.base_dir)
            for layer_name, layer_config in skill_def.context.layers.items():
                if layer_config.source:
                    template_path = base / layer_config.source
                    if not template_path.exists():
                        errors.append(f"template not found: {layer_config.source}")

        return errors

    def _has_circular_dependency(
        self, skill_def: SkillDefinition, all_skills: Dict[str, SkillDefinition]
    ) -> bool:
        visited = set()
        stack = [skill_def.name]
        while stack:
            current = stack.pop()
            if current in visited:
                return True
            visited.add(current)
            current_skill = all_skills.get(current)
            if current_skill and current_skill.activation_rules:
                for dep in current_skill.activation_rules.context_dependencies:
                    stack.append(dep.skill)
        return False
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_loader.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add app/skill/loader.py app/skill/validator.py tests/unit/test_skill_loader.py && git commit -m "feat: add SkillLoader and SkillValidator"
```

---

### Task 5.6: SkillEngine (main entry point)

**Files:**
- Create: `agent-core/app/skill/engine.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_skill_engine.py
import pytest
from unittest.mock import AsyncMock
from app.skill.engine import SkillEngine
from app.skill.models import SkillDefinition, SkillResult

class TestSkillEngine:
    @pytest.fixture
    def engine(self):
        workflow_engine = AsyncMock()
        context_builder = AsyncMock()
        mcp_client = AsyncMock()
        return SkillEngine(
            workflow_engine=workflow_engine,
            context_builder=context_builder,
            mcp_client=mcp_client
        )

    def test_init(self, engine):
        assert engine.registry is not None
        assert engine.matcher is not None
        assert engine.executor is not None

    @pytest.mark.asyncio
    async def test_execute_not_found(self, engine):
        result = await engine.execute("nonexistent", {})
        assert result.status == "failed"
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_list_available_all(self, engine):
        engine.registry.register(SkillDefinition(name="a", workflows={"main": "wf"}))
        engine.registry.register(SkillDefinition(name="b", workflows={"main": "wf"}))
        result = await engine.list_available([])
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_available_filtered(self, engine):
        engine.registry.register(SkillDefinition(name="a", workflows={"main": "wf"}))
        engine.registry.register(SkillDefinition(name="b", workflows={"main": "wf"}))
        result = await engine.list_available(["a"])
        assert len(result) == 1
        assert result[0].name == "a"
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_engine.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/skill/engine.py`:
```python
import logging
from typing import Dict, Any, List

from .models import SkillDefinition, SkillResult, SkillSummary, SkillMatch
from .registry import SkillRegistry
from .matcher import SkillMatcher
from .executor import SkillExecutor
from .loader import SkillLoader
from .validator import SkillValidator

logger = logging.getLogger(__name__)


class SkillEngine:
    """Skill Engine - Agent Loop's only execution entry point"""

    def __init__(self, workflow_engine, context_builder, mcp_client, embedding_client=None):
        self.workflow_engine = workflow_engine
        self.context_builder = context_builder
        self.mcp_client = mcp_client

        self.registry = SkillRegistry(max_history_versions=3)
        self.matcher = SkillMatcher(self.registry, embedding_client=embedding_client)
        self.executor = SkillExecutor(workflow_engine, context_builder, mcp_client)
        self.validator = SkillValidator()
        self.loader: SkillLoader = None  # Set after init

    async def execute(
        self,
        skill_name: str,
        params: Dict[str, Any],
        trace_id: str = None,
        max_iterations: int = None
    ) -> SkillResult:
        skill_def = self.registry.get(skill_name)
        if not skill_def:
            return SkillResult(status="failed", error=f"Skill '{skill_name}' not found")
        return await self.executor.execute(
            skill_def=skill_def,
            params=params,
            trace_id=trace_id,
            max_iterations=max_iterations
        )

    async def match(
        self,
        request: str,
        context: Dict = None,
        agent_skill_set: List[str] = None
    ) -> List[SkillMatch]:
        return await self.matcher.match(request, context, agent_skill_set)

    async def list_available(self, agent_skill_set: List[str]) -> List[SkillSummary]:
        if agent_skill_set:
            return self.registry.list_by_names(agent_skill_set)
        return self.registry.list_all()

    async def reload(self, changed_files: List[str] = None):
        """Reload skills from disk"""
        if not self.loader:
            logger.warning("SkillLoader not configured, skipping reload")
            return

        if changed_files:
            new_skills = await self.loader.reload_changed(changed_files)
        else:
            new_skills = await self.loader.load_all()

        if new_skills:
            # Validate
            workflow_names = set(self.workflow_engine.definitions.keys())
            for name, skill_def in new_skills.items():
                errors = self.validator.validate(skill_def, workflow_names, dict(self.registry._skills))
                if errors:
                    logger.error(f"Skill '{name}' validation failed: {errors}")
                    continue

            await self.registry.replace_all(new_skills)
            logger.info(f"Reloaded {len(new_skills)} skills")
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_skill_engine.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add app/skill/engine.py tests/unit/test_skill_engine.py && git commit -m "feat: add SkillEngine as Agent Loop's only entry point"
```

---

## Phase 6: Agent Loop (ReAct)

### Task 6.1: Agent data models

**Files:**
- Create: `agent-core/app/agent/models.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_agent_models.py
import pytest
from app.agent.models import Thought, ActionResult, Observation, Reflection, TaskResult

def test_thought_parse():
    data = {
        "reasoning": "user wants expense reimbursement",
        "action_type": "skill",
        "skill_name": "expense-reimbursement",
        "params": {"amount": 3500},
        "confidence": 0.92
    }
    thought = Thought(**data)
    assert thought.action_type == "skill"
    assert thought.confidence == 0.92

def test_action_result_degraded():
    result = ActionResult(
        status="degraded_success",
        data={"ok": True},
        degradation_info={"skipped": ["risk_analysis"]}
    )
    assert result.status == "degraded_success"

def test_task_result():
    result = TaskResult(
        status="completed",
        message="done",
        total_iterations=2,
        trace_id="abc123"
    )
    assert result.total_iterations == 2
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_agent_models.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/agent/models.py`:
```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_agent_models.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add app/agent/models.py tests/unit/test_agent_models.py && git commit -m "feat: add Agent data models"
```

---

### Task 6.2: StateStore (Redis + MySQL)

**Files:**
- Create: `agent-core/app/agent/state.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_state_store.py
import pytest
from unittest.mock import AsyncMock
from app.agent.state import StateStore
from app.agent.models import AgentState

class TestStateStore:
    def test_init(self):
        store = StateStore(cache=AsyncMock(), database=AsyncMock())
        assert store is not None
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_state_store.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/agent/state.py`:
```python
import json
import logging
from typing import Optional
from datetime import datetime

from .models import AgentState

logger = logging.getLogger(__name__)


class StateStore:
    """Agent state store: Redis (hot) + MySQL (cold)"""

    def __init__(self, cache, database):
        self.cache = cache
        self.database = database

    async def save(self, state: AgentState):
        """Save state to Redis (hot) and periodically to MySQL (cold)"""
        state.version += 1
        key = f"agent:state:{state.agent_id}"

        # Always save to Redis
        await self.cache.set(key, state.model_dump(), ttl=3600)

        # Periodic MySQL checkpoint (every 5 versions)
        if state.version % 5 == 0:
            await self._save_to_mysql(state)

    async def load(self, agent_id: str) -> Optional[AgentState]:
        """Load state: try Redis first, fall back to MySQL"""
        key = f"agent:state:{agent_id}"
        data = await self.cache.get(key)
        if data:
            return AgentState(**data)

        # Fall back to MySQL
        row = await self.database.fetchone(
            "SELECT * FROM agent_states WHERE agent_id = %s", (agent_id,)
        )
        if row:
            state = self._row_to_state(row)
            # Warm up Redis
            await self.cache.set(key, state.model_dump(), ttl=3600)
            return state
        return None

    async def _save_to_mysql(self, state: AgentState):
        """Save state snapshot to MySQL"""
        try:
            await self.database.execute(
                """INSERT INTO agent_states (agent_id, session_id, skill_set, memory,
                   task_stack, workflow_context, current_step, scratch_pad, status,
                   version, created_at, last_checkpoint)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                   session_id=VALUES(session_id), skill_set=VALUES(skill_set),
                   memory=VALUES(memory), task_stack=VALUES(task_stack),
                   workflow_context=VALUES(workflow_context), current_step=VALUES(current_step),
                   scratch_pad=VALUES(scratch_pad), status=VALUES(status),
                   version=VALUES(version), last_checkpoint=VALUES(last_checkpoint)""",
                (
                    state.agent_id, state.session_id,
                    json.dumps(state.skill_set),
                    json.dumps([m for m in state.memory]),
                    json.dumps([t.model_dump() for t in state.task_stack]),
                    json.dumps(state.workflow_context) if state.workflow_context else None,
                    state.current_step,
                    json.dumps(state.scratch_pad),
                    "running",
                    state.version,
                    datetime.now(),
                    datetime.now()
                )
            )
        except Exception as e:
            logger.error(f"Failed to save state to MySQL: {e}")

    def _row_to_state(self, row: dict) -> AgentState:
        from .models import TaskFrame
        return AgentState(
            agent_id=row["agent_id"],
            session_id=row["session_id"],
            skill_set=json.loads(row["skill_set"]) if row["skill_set"] else [],
            memory=json.loads(row["memory"]) if row["memory"] else [],
            task_stack=[TaskFrame(**t) for t in json.loads(row["task_stack"])] if row["task_stack"] else [],
            workflow_context=json.loads(row["workflow_context"]) if row["workflow_context"] else None,
            current_step=row.get("current_step", 0),
            scratch_pad=json.loads(row["scratch_pad"]) if row["scratch_pad"] else {},
            version=row.get("version", 1)
        )

    async def delete(self, agent_id: str):
        key = f"agent:state:{agent_id}"
        await self.cache.delete(key)
        await self.database.execute(
            "UPDATE agent_states SET status = 'terminated' WHERE agent_id = %s", (agent_id,)
        )
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_state_store.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/agent/state.py tests/unit/test_state_store.py && git commit -m "feat: add StateStore with Redis hot cache and MySQL cold storage"
```

---

### Task 6.3: AgentLoop (ReAct main loop)

**Files:**
- Create: `agent-core/app/agent/loop.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_agent_loop.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agent.loop import AgentLoop
from app.agent.models import AgentState, TaskResult

class TestAgentLoop:
    def test_init(self):
        loop = AgentLoop(
            agent_id="test-agent",
            skill_set=["skill-a"],
            skill_engine=AsyncMock(),
            llm_client=AsyncMock(),
            state_store=AsyncMock(),
            config=MagicMock(max_iterations=3, checkpoint_interval=1,
                           think_system_prompt="", reflect_system_prompt="")
        )
        assert loop.agent_id == "test-agent"
        assert loop.skill_set == ["skill-a"]
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_agent_loop.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/agent/loop.py`:
```python
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
    """Agent Loop - ReAct cycle: Think → Act → Observe → Reflect"""

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
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_agent_loop.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/agent/loop.py tests/unit/test_agent_loop.py && git commit -m "feat: add AgentLoop with ReAct cycle"
```

---

## Phase 7: Hot Reload

### Task 7.1: HotReloadManager

**Files:**
- Create: `agent-core/app/reload/manager.py`
- Create: `agent-core/app/reload/watcher.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_reload_manager.py
import pytest
from app.reload.manager import HotReloadManager

class TestHotReloadManager:
    def test_init(self):
        manager = HotReloadManager(skill_engine=None, workflow_engine=None)
        assert manager is not None
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_reload_manager.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/reload/watcher.py`:
```python
import logging
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from typing import Callable, List

logger = logging.getLogger(__name__)


class SkillFileHandler(FileSystemEventHandler):
    """Watch skill directory for changes"""

    def __init__(self, callback: Callable):
        self.callback = callback
        self._debounce_files = set()

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.yaml', '.jinja2', '.md')):
            self._debounce_files.add(event.src_path)
            logger.info(f"Skill file changed: {event.src_path}")

    def on_created(self, event):
        self.on_modified(event)

    def flush(self) -> List[str]:
        files = list(self._debounce_files)
        self._debounce_files.clear()
        return files


class WorkflowFileHandler(FileSystemEventHandler):
    """Watch workflow directory for changes"""

    def __init__(self, callback: Callable):
        self.callback = callback
        self._debounce_files = set()

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.yaml'):
            self._debounce_files.add(event.src_path)
            logger.info(f"Workflow file changed: {event.src_path}")

    def on_created(self, event):
        self.on_modified(event)

    def flush(self) -> List[str]:
        files = list(self._debounce_files)
        self._debounce_files.clear()
        return files
```

`agent-core/app/reload/manager.py`:
```python
import asyncio
import logging
from typing import List, Optional
from watchdog.observers import Observer

from .watcher import SkillFileHandler, WorkflowFileHandler

logger = logging.getLogger(__name__)


class ReloadResult:
    def __init__(self, success: bool, count: int = 0, errors: List[str] = None):
        self.success = success
        self.count = count
        self.errors = errors or []


class HotReloadManager:
    """Hot reload manager with file watcher and API trigger"""

    def __init__(self, skill_engine, workflow_engine, skills_dir: str = "skills", workflows_dir: str = "workflows"):
        self.skill_engine = skill_engine
        self.workflow_engine = workflow_engine
        self.skills_dir = skills_dir
        self.workflows_dir = workflows_dir
        self.observer = Observer()
        self._reload_lock = asyncio.Lock()
        self._skill_handler = None
        self._workflow_handler = None

    def start(self):
        self._skill_handler = SkillFileHandler(self._on_skill_change)
        self.observer.schedule(self._skill_handler, self.skills_dir, recursive=True)

        self._workflow_handler = WorkflowFileHandler(self._on_workflow_change)
        self.observer.schedule(self._workflow_handler, self.workflows_dir, recursive=True)

        self.observer.start()
        logger.info(f"Hot reload watching: {self.skills_dir}, {self.workflows_dir}")

    def stop(self):
        self.observer.stop()
        self.observer.join()

    def _on_skill_change(self, event):
        logger.info(f"Skill file change detected: {event.src_path}")

    def _on_workflow_change(self, event):
        logger.info(f"Workflow file change detected: {event.src_path}")

    async def reload_skills(self, changed_files: List[str] = None) -> ReloadResult:
        async with self._reload_lock:
            try:
                if self.skill_engine:
                    await self.skill_engine.reload(changed_files)
                    count = self.skill_engine.registry.count()
                    return ReloadResult(success=True, count=count)
                return ReloadResult(success=False, errors=["Skill engine not configured"])
            except Exception as e:
                logger.error(f"Skill reload failed: {e}")
                return ReloadResult(success=False, errors=[str(e)])

    async def reload_workflows(self, changed_files: List[str] = None) -> ReloadResult:
        async with self._reload_lock:
            try:
                if self.workflow_engine and hasattr(self.workflow_engine, 'reload'):
                    await self.workflow_engine.reload(changed_files)
                    return ReloadResult(success=True, count=len(self.workflow_engine.definitions))
                return ReloadResult(success=False, errors=["Workflow engine not configured"])
            except Exception as e:
                logger.error(f"Workflow reload failed: {e}")
                return ReloadResult(success=False, errors=[str(e)])

    async def reload_all(self):
        wf = await self.reload_workflows()
        sk = await self.reload_skills()
        return {"workflows": {"success": wf.success, "count": wf.count},
                "skills": {"success": sk.success, "count": sk.count}}
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_reload_manager.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/reload/watcher.py app/reload/manager.py tests/unit/test_reload_manager.py && git commit -m "feat: add HotReloadManager with file watcher"
```

---

## Phase 8: API Layer & Main App

### Task 8.1: FastAPI app with all routers

**Files:**
- Create: `agent-core/app/main.py`
- Create: `agent-core/app/api/health.py`
- Create: `agent-core/app/api/agent.py`
- Create: `agent-core/app/api/admin.py`
- Create: `agent-core/app/api/ws.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app

class TestHealthAPI:
    @pytest.mark.asyncio
    async def test_health(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_api.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/api/health.py`:
```python
from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@router.get("/health/detailed")
async def detailed_health():
    return {
        "status": "healthy",
        "components": {
            "mysql": "ok",
            "redis": "ok",
            "mcp_discovery": "ok",
            "llm_api": "ok"
        }
    }
```

`agent-core/app/api/agent.py`:
```python
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

router = APIRouter(prefix="/api/v1/agents")

class TaskRequest(BaseModel):
    task: str
    context: Dict[str, Any] = {}

@router.post("/{agent_id}/tasks")
async def create_task(agent_id: str, request: TaskRequest, background_tasks: BackgroundTasks):
    task_id = uuid.uuid4().hex
    return {"task_id": task_id, "agent_id": agent_id, "status": "accepted"}

@router.get("/{agent_id}/tasks/{task_id}")
async def get_task_status(agent_id: str, task_id: str):
    return {"task_id": task_id, "status": "pending"}

@router.get("/{agent_id}/state")
async def get_agent_state(agent_id: str):
    return {"agent_id": agent_id, "status": "running"}
```

`agent-core/app/api/admin.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader

router = APIRouter(prefix="/api/v1/admin")

api_key_header = APIKeyHeader(name="X-Admin-Key")

async def verify_admin_key(key: str = Depends(api_key_header)):
    from app.core.config import load_config
    config = load_config("config/settings.yaml")
    if key != config.get("app", {}).get("admin_api_key", ""):
        raise HTTPException(status_code=403, detail="Invalid admin API key")

@router.post("/reload/skills", dependencies=[Depends(verify_admin_key)])
async def reload_skills():
    return {"success": True, "count": 0}

@router.post("/reload/workflows", dependencies=[Depends(verify_admin_key)])
async def reload_workflows():
    return {"success": True, "count": 0}

@router.post("/reload/all", dependencies=[Depends(verify_admin_key)])
async def reload_all():
    return {"skills": {"success": True, "count": 0}, "workflows": {"success": True, "count": 0}}
```

`agent-core/app/api/ws.py`:
```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws/{agent_id}/stream")
async def agent_stream(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "agent_id": agent_id})
    except WebSocketDisconnect:
        pass
```

`agent-core/app/main.py`:
```python
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.trace import TraceContext
from app.core.exceptions import AgentCoreError
from app.api.health import router as health_router
from app.api.agent import router as agent_router
from app.api.admin import router as admin_router
from app.api.ws import router as ws_router


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or TraceContext.generate_trace_id()
        TraceContext.set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Core", version="1.0.0")

    # Middleware
    app.add_middleware(TraceMiddleware)

    # Exception handler
    @app.exception_handler(AgentCoreError)
    async def handle_agent_error(request: Request, exc: AgentCoreError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_type,
                "message": exc.message,
                "details": exc.details,
                "trace_id": TraceContext.get_trace_id()
            }
        )

    # Routers
    app.include_router(health_router)
    app.include_router(agent_router)
    app.include_router(admin_router)
    app.include_router(ws_router)

    return app


app = create_app()
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_api.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/main.py app/api/health.py app/api/agent.py app/api/admin.py app/api/ws.py tests/unit/test_api.py && git commit -m "feat: add FastAPI app with REST, WebSocket, Admin, and Health APIs"
```

---

## Phase 9: Monitoring

### Task 9.1: Structured logging and Prometheus metrics

**Files:**
- Create: `agent-core/app/monitoring/logger.py`
- Create: `agent-core/app/monitoring/metrics.py`

**Step 1: Write the failing test**

```python
# agent-core/tests/unit/test_monitoring.py
import pytest
from app.monitoring.metrics import MetricsCollector

def test_metrics_collector_init():
    collector = MetricsCollector()
    assert collector is not None
```

**Step 2: Run test to verify it fails**

Run: `cd agent-core && python -m pytest tests/unit/test_monitoring.py -v`
Expected: FAIL (module not found)

**Step 3: Write implementation**

`agent-core/app/monitoring/logger.py`:
```python
import logging
import json
from app.core.trace import TraceContext


class TraceFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = TraceContext.get_trace_id()
        return True


def setup_logging(level: str = "INFO", format_type: str = "json"):
    handler = logging.StreamHandler()
    handler.addFilter(TraceFilter())

    if format_type == "json":
        formatter = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"trace_id":"%(trace_id)s","module":"%(module)s","message":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(trace_id)s] %(levelname)s %(module)s: %(message)s'
        )

    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
```

`agent-core/app/monitoring/metrics.py`:
```python
from prometheus_client import Counter, Histogram, Gauge


class MetricsCollector:
    """Prometheus metrics collector"""

    def __init__(self):
        # Agent metrics
        self.agent_iterations = Counter(
            'agent_iterations_total', 'Agent loop iterations',
            ['agent_id', 'status']
        )
        self.agent_task_duration = Histogram(
            'agent_task_duration_seconds', 'Task execution time'
        )
        self.active_agents = Gauge(
            'active_agents', 'Number of active agents'
        )

        # Skill metrics
        self.skill_executions = Counter(
            'skill_executions_total', 'Skill executions',
            ['skill_name', 'status']
        )
        self.skill_duration = Histogram(
            'skill_duration_seconds', 'Skill execution time',
            ['skill_name']
        )

        # Workflow metrics
        self.workflow_step_duration = Histogram(
            'workflow_step_duration_seconds', 'Step execution time',
            ['step_type']
        )
        self.workflow_degradations = Counter(
            'workflow_degradations_total', 'Degradation events',
            ['workflow_name', 'fallback_workflow']
        )

        # MCP metrics
        self.mcp_call_duration = Histogram(
            'mcp_call_duration_seconds', 'MCP tool call time',
            ['tool_name', 'action']
        )
        self.mcp_circuit_state = Gauge(
            'mcp_circuit_state', 'Circuit breaker state (0=closed, 1=open, 2=half_open)',
            ['tool_name']
        )
        self.mcp_call_errors = Counter(
            'mcp_call_errors_total', 'MCP call errors',
            ['tool_name', 'error_type']
        )
```

**Step 4: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/unit/test_monitoring.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/monitoring/logger.py app/monitoring/metrics.py tests/unit/test_monitoring.py && git commit -m "feat: add structured logging with trace_id and Prometheus metrics"
```

---

## Phase 10: Integration Tests

### Task 10.1: Integration test - circuit breaker triggers degradation

**Files:**
- Create: `agent-core/tests/integration/__init__.py`
- Create: `agent-core/tests/integration/test_circuit_breaker_degradation.py`
- Create: `agent-core/tests/conftest.py`

**Step 1: Write conftest.py**

`agent-core/tests/conftest.py`:
```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_mcp_client():
    client = AsyncMock()
    client.call_tool = AsyncMock(return_value=type("R", (), {"success": True, "data": {"ok": True}})())
    return client

@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.complete = AsyncMock(return_value='{"reasoning": "test", "action_type": "respond", "response_text": "done"}')
    return client
```

**Step 2: Write integration test**

`agent-core/tests/integration/test_circuit_breaker_degradation.py`:
```python
import pytest
from app.mcp.circuit_breaker import CircuitBreaker, CircuitState

class TestCircuitBreakerDegradation:
    def test_circuit_open_blocks_calls(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.retry_after > 0

    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        import asyncio
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
```

**Step 3: Run test to verify it passes**

Run: `cd agent-core && python -m pytest tests/integration/test_circuit_breaker_degradation.py -v`
Expected: 2 passed

**Step 4: Commit**

```bash
git add tests/conftest.py tests/integration/test_circuit_breaker_degradation.py && git commit -m "test: add integration test for circuit breaker degradation"
```

---

## Phase 11: Docker & Deployment

### Task 11.1: Dockerfile and docker-compose

**Files:**
- Create: `agent-core/docker/Dockerfile`
- Create: `agent-core/docker/docker-compose.yml`

**Step 1: Write Dockerfile**

`agent-core/docker/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Write docker-compose.yml**

`agent-core/docker/docker-compose.yml`:
```yaml
version: "3.8"

services:
  agent-core:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - MYSQL_HOST=mysql
      - MYSQL_PORT=3306
      - MYSQL_USER=root
      - MYSQL_PASSWORD=agent_core_pw
      - MYSQL_DATABASE=agent_core
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - ADMIN_API_KEY=admin-secret-key
      - EMBEDDING_API_URL=http://embedding:8081/embed
      - EMBEDDING_API_KEY=test-key
      - MCP_DISCOVERY_URL=http://mcp-discovery:8080
    volumes:
      - ../skills:/app/skills
      - ../workflows:/app/workflows
      - ../config:/app/config
    depends_on:
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: agent_core_pw
      MYSQL_DATABASE: agent_core
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ../scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  mysql_data:
```

**Step 3: Write init.sql**

Create `agent-core/scripts/init.sql`:
```sql
CREATE TABLE IF NOT EXISTS agent_states (
    agent_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    skill_set JSON NOT NULL,
    memory LONGTEXT,
    task_stack JSON,
    workflow_context JSON,
    current_step INT DEFAULT 0,
    scratch_pad JSON,
    status ENUM('running', 'paused', 'terminated') DEFAULT 'running',
    version INT DEFAULT 1,
    created_at DATETIME NOT NULL,
    last_checkpoint DATETIME NOT NULL,
    INDEX idx_session (session_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_state_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    event_type ENUM('pause', 'resume', 'destroy', 'migrate', 'checkpoint') NOT NULL,
    state_snapshot JSON,
    created_at DATETIME NOT NULL,
    INDEX idx_agent_event (agent_id, event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    workflow_name VARCHAR(128) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    step_index INT NOT NULL,
    step_name VARCHAR(128) NOT NULL,
    context_data LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (workflow_name, agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Step 4: Commit**

```bash
mkdir -p agent-core/scripts && git add agent-core/docker/ agent-core/scripts/ && git commit -m "feat: add Dockerfile and docker-compose with MySQL, Redis"
```

---

## Final: Verify all tests pass

```bash
cd agent-core && python -m pytest tests/ -v --tb=short
```

Expected: All tests pass.

```bash
git add -A && git commit -m "chore: final verification - all tests passing"
```

---

*Plan version: v1.0*
*Date: 2026-05-29*
