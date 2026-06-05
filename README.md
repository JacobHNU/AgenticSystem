# AgenticSystem

Production-grade intelligent agent framework combining 6-layer context engineering, MCP tool orchestration, and Workflow Lifecycle Mode agent loop.

**版本**: 2.0.0

## Architecture (V2.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Gateway                           │
│                  REST + WebSocket + Admin API                    │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Agent Loop (Workflow Lifecycle)                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  _resolve_skill() → SkillMatcher (no LLM)               │    │
│  └─────┬──────────────────┬──────────────────┬─────────────┘    │
│        ↓                  ↓                  ↓                   │
│  ┌───────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ Fast Path │    │  Build Path  │    │  ReAct Path  │          │
│  │ 0 LLM     │    │ 1-2 LLM      │    │ 2+ LLM/轮    │          │
│  │ 直接执行   │    │ 构建+执行+保存 │    │ Think→Reflect │          │
│  └─────┬─────┘    └──────┬───────┘    └──────┬───────┘          │
│        └─────────────────┼───────────────────┘                  │
│                          ↓                                       │
│              ┌───────────────────────┐                          │
│              │     Skill Engine       │                          │
│              │  Match → Execute       │                          │
│              │  Promote → Persist     │                          │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────────┐
│                     Workflow Engine                               │
│  4 step types · Parallel execution · Conditional branching        │
│  Disk persistence (save/load YAML) · Checkpoint & resume         │
└────────────────────────────┬─────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────┐
│                  Context Builder (L1-L6)                          │
│  L1 Base → L2 Business → L3 Dynamic → L4 History → L5 Tools     │
│  Smart trimming · Sensitive masking · Token management            │
└────────────────────────────┬─────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────┐
│                     MCP Client Layer                              │
│  Connection pool · Circuit breaker · Retry · Auth                 │
│  Tool discovery · Health monitoring                               │
└──────────────────────────────────────────────────────────────────┘
```

## Features

- **Workflow Lifecycle Mode (V2.0)** - Three-path execution model: Fast Path (0 LLM calls), Build Path (auto-construct workflow from description), ReAct Path (full Think→Act→Observe→Reflect cycle). Automatic skill promotion from flexible to fixed.
- **6-Layer Context Engineering** - Structured context assembly with priority-based token trimming and configurable merge strategies (replace/append/union)
- **Skill Engine** - Two-level matching (keyword 40% + embedding 60%), activation rules, version binding, hot reload, degradation with recursive fallback
- **Workflow Engine** - 4 step types (MCP tool, LLM reasoning, sub-workflow, skill call), conditional branching, template variable substitution, checkpoint/resume, disk persistence
- **Agent Loop (ReAct)** - Think → Act → Observe → Reflect cycle with LLM-driven planning, memory management, and scratch pad
- **MCP Client** - Connection pooling, exponential backoff retry, circuit breaker (CLOSED→OPEN→HALF_OPEN), endpoint discovery, auth management
- **Sensitive Data Masking** - Built-in patterns for phone, ID card, email, bank card + custom YAML rules
- **Hot Reload** - File watcher (watchdog) + API trigger for skills and workflows with atomic replace
- **Observability** - Structured JSON logging with trace_id propagation, Prometheus metrics (agent, skill, workflow, MCP dimensions)
- **Deployment** - Docker Compose with MySQL 8.0 + Redis 7 + health checks

## Performance (V2.0)

| 场景 | V1.0 (ReAct) | V2.0 (Fast Path) | 提升 |
|------|-------------|-------------------|------|
| 固定 workflow 执行 | ~4.5s (2 LLM calls) | ~250ms (0 LLM calls) | **~18x** |
| 首次构建 workflow | ~4.5s (需人工预定义) | ~4s (自动构建) | 自动化 |
| 已构建 workflow 再次执行 | ~4.5s | ~250ms | **~18x** |
| 无匹配任务 | ~4.5s | ~4.5s (不变) | — |

## Execution Mode Comparison

| 维度 | Fast Path | Build Path | ReAct Path |
|------|-----------|------------|------------|
| **触发条件** | fixed skill + workflow 存在 | flexible skill + 首次调用 | 无 skill 匹配 |
| **LLM 调用（路由）** | 0 次 | 0 次 | 2 次/轮 |
| **LLM 调用（workflow 内）** | 仅 llm_reasoning 步骤 | 1 次（构建）+ llm_reasoning 步骤 | 2 次/轮 + llm_reasoning 步骤 |
| **Post-eval（可选）** | 1 次 | 1 次 | 无（内含在 Reflect 中） |
| **预期延迟** | ~250ms | ~4s（首次） | ~4.5s+/轮 |

## Skill Lifecycle

```
阶段 1: 定义（Flexible Skill）
  type: flexible, process_description: "业务流程描述", workflows.main: ""
        │ 首次调用
        ▼
阶段 2: 构建（Build Path）
  DynamicWorkflowBuilder.build_workflow → 生成 WorkflowDefinition → 执行 → 评估
        │ 成功后
        ▼
阶段 3: 固化（Promote + Persist）
  type: flexible → fixed, workflows.main: "skill_dynamic", 版本号 +1, 持久化到磁盘
        │ 后续调用
        ▼
阶段 4: 快速执行（Fast Path）
  跳过 Think/Reflect, 直接执行 Workflow, 0 LLM 调用（路由层）
```

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Start server
uvicorn app.main:app --reload --port 8000
```

### Docker Deployment

```bash
cd docker
docker-compose up -d
```

Services:
- **Agent Core API**: http://localhost:8000
- **MySQL**: localhost:3306
- **Redis**: localhost:6379

## Configuration

All config in `config/settings.yaml` with `${ENV_VAR}` and `${ENV_VAR:default}` syntax:

```yaml
app:
  name: agent-core
  port: 8000
  admin_api_key: "${ADMIN_API_KEY}"

agent:
  max_iterations: 10
  checkpoint_interval: 3

mcp:
  discovery_url: "${MCP_DISCOVERY_URL:http://mcp-discovery:8080}"
  circuit_breaker:
    failure_threshold: 5
    recovery_timeout: 60

context:
  token_limit: 4000
  sensitive_fields: [phone, id_card, email, bank_card]

# V2.0: Workflow Lifecycle
workflow_lifecycle:
  enable_post_evaluation: false
  fast_path_confidence_threshold: 0.6
  auto_persist_workflows: true
```

### Agent Loop Runtime Config

```python
config.enable_workflow_lifecycle = True        # 总开关，默认 True
config.fast_path_confidence_threshold = 0.6    # 置信度阈值，默认 0.6
config.enable_post_evaluation = False          # Fast Path 默认关闭，Build Path 默认开启
config.max_iterations = 10                     # ReAct Path 最大迭代次数
config.checkpoint_interval = 3                 # ReAct Path checkpoint 间隔
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/health/detailed` | Component health (MySQL, Redis, MCP, LLM) |
| POST | `/api/v1/agents/{id}/tasks` | Create agent task |
| GET | `/api/v1/agents/{id}/tasks/{task_id}` | Get task status |
| GET | `/api/v1/agents/{id}/state` | Get agent state |
| WS | `/ws/{agent_id}/stream` | WebSocket event stream |
| POST | `/api/v1/admin/reload/skills` | Reload skills (admin) |
| POST | `/api/v1/admin/reload/workflows` | Reload workflows (admin) |
| POST | `/api/v1/admin/reload/all` | Reload all (admin) |

### TaskResult (V2.0)

`execution_mode` 字段标识执行路径：

```json
{
  "status": "completed",
  "data": {"result": "verified"},
  "execution_report": {
    "metrics": {"tool_calls": 2, "llm_calls": 0, "total_duration_ms": 180}
  },
  "total_iterations": 1,
  "execution_mode": "fast_path"
}
```

`execution_mode` 取值：`"fast_path"` / `"build_path"` / `"react"`

## Project Structure

```
agent-core/
├── app/
│   ├── agent/           # Agent Loop (Workflow Lifecycle)
│   │   ├── loop.py      # Three-path routing: Fast/Build/ReAct
│   │   ├── models.py    # ExecutionMode, Thought, TaskResult
│   │   └── state.py     # Redis hot + MySQL cold state store
│   ├── api/             # FastAPI routers
│   │   ├── health.py    # Health endpoints
│   │   ├── agent.py     # Agent task endpoints
│   │   ├── admin.py     # Admin reload endpoints
│   │   └── ws.py        # WebSocket stream
│   ├── context/         # 6-Layer Context Engineering
│   │   ├── builder.py   # Context assembly orchestrator
│   │   ├── loaders.py   # L1-L6 layer loaders
│   │   ├── merger.py    # Merge strategies (replace/append/union)
│   │   ├── trimmer.py   # Smart history + token trimming
│   │   └── masker.py    # Sensitive data masking
│   ├── core/            # Shared infrastructure
│   │   ├── cache.py     # Redis client
│   │   ├── config.py    # YAML config loader
│   │   ├── database.py  # MySQL connection pool
│   │   ├── exceptions.py # Exception hierarchy
│   │   └── trace.py     # TraceContext (ContextVar)
│   ├── mcp/             # MCP Client Layer
│   │   ├── client.py    # Unified MCP client
│   │   ├── circuit_breaker.py # CLOSED→OPEN→HALF_OPEN
│   │   ├── retry.py     # Exponential backoff
│   │   ├── pool.py      # Connection pool
│   │   ├── auth.py      # Auth manager
│   │   └── discovery.py # Tool discovery
│   ├── monitoring/      # Observability
│   │   ├── logger.py    # Structured JSON logging
│   │   └── metrics.py   # Prometheus metrics
│   ├── reload/          # Hot Reload
│   │   ├── manager.py   # Reload orchestrator
│   │   └── watcher.py   # File system watcher
│   ├── skill/           # Skill Engine
│   │   ├── engine.py    # Main entry + persist_workflow()
│   │   ├── matcher.py   # Two-level matching
│   │   ├── executor.py  # Execution + degradation
│   │   ├── registry.py  # Version management + promote
│   │   ├── loader.py    # YAML loader
│   │   └── validator.py # Flexible/fixed validation
│   ├── workflow/         # Workflow Engine
│   │   ├── engine.py    # Step executor + disk persistence
│   │   ├── context.py   # Workflow context
│   │   └── models.py    # Step/Workflow models
│   └── main.py          # FastAPI app factory
├── config/
│   ├── settings.yaml    # Main config
│   └── masking_rules.yaml # Custom masking rules
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
│   ├── AgenticSystem-V2.0.md
│   └── workflow-lifecycle-plan.md
├── scripts/
│   └── init.sql         # Database schema
├── tests/
│   ├── unit/            # 102 unit tests
│   └── integration/     # Integration tests
└── requirements.txt
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=term-missing

# Run specific module
python -m pytest tests/unit/test_agent_loop.py -v

# Run integration tests only
python -m pytest tests/integration/ -v
```

### Test Coverage (V2.0)

| 模块 | 测试数 | 状态 |
|------|--------|------|
| `test_agent_loop.py` | 12 (1 原有 + 11 新增) | ✅ 全部通过 |
| `test_skill_validator.py` | 6 (新建) | ✅ 全部通过 |
| `test_skill_executor.py` | 2 (修复 mock) | ✅ 全部通过 |
| `test_skill_engine.py` | 4 | ✅ 全部通过 |
| `test_workflow_engine.py` | 3 | ✅ 全部通过 |
| 其他模块 | 75 | ✅ 全部通过 |
| **总计** | **102** | **✅ 102 passed, 0 failed** |

## Key Design Decisions

- **Three-path execution model** - Fast Path (0 LLM, direct workflow execution), Build Path (auto-construct from description), ReAct Path (full reasoning loop). Dynamically selected based on skill type and confidence.
- **Skill lifecycle: flexible → fixed** - Skills start as flexible (description-only), auto-build workflow on first call, then promote to fixed for Fast Path reuse. Survives restarts via disk persistence.
- **Skill as MCP upper-layer abstraction** - Skills encapsulate workflow + context + activation rules, providing richer semantics than raw MCP tools
- **Agent Loop as top-level controller** - ReAct pattern drives all task execution; Skills and Workflows are invoked through it
- **Dual storage** - Redis for hot state (fast read/write), MySQL for cold persistence (checkpoint every 5 versions)
- **Circuit breaker** - Prevents cascading failures from MCP tool timeouts; supports automatic recovery
- **Hot reload with version binding** - Running agents bind to the skill version at execution start; new executions use updated versions

## Backward Compatibility

- **现有 Fixed Skill 无需改动**：`type: "fixed"` + `workflows.main` 已存在的 Skill 自动走 Fast Path
- **ReAct 行为不变**：`_think()`、`_act()`、`_observe()`、`_reflect()` 方法完全保留
- **TaskResult 默认值**：`execution_mode` 默认为 `"react"`，不影响现有消费者
- **配置可选**：`workflow_lifecycle` 配置段不设置时使用默认值
- **无新增外部依赖**：所有改动基于已有的 PyYAML、Pydantic、标准库

如需禁用 Workflow Lifecycle Mode，回退到 V1.0 纯 ReAct 模式：

```yaml
workflow_lifecycle:
  enable_post_evaluation: false
```

或在 AgentLoop config 中设置 `enable_workflow_lifecycle = False`。

## License

MIT
