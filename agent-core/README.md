# Agent Core

Production-grade intelligent agent framework combining 6-layer context engineering, MCP tool orchestration, and ReAct agent loop.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Gateway                         │
│              REST + WebSocket + Admin API                    │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    Agent Loop (ReAct)                         │
│            Think → Act → Observe → Reflect                   │
└──────────┬──────────────────────────────┬───────────────────┘
           ↓                              ↓
┌─────────────────────┐      ┌────────────────────────┐
│   Skill Engine       │      │   Workflow Engine        │
│  Two-level matching  │      │  4 step types            │
│  Degradation policy  │      │  Checkpoint & resume     │
└──────────┬──────────┘      └──────────┬─────────────┘
           ↓                             ↓
┌─────────────────────────────────────────────────────────────┐
│                  Context Builder (L1-L6)                      │
│  L1 Base → L2 Business → L3 Dynamic → L4 History → L5 Tools │
│  Smart trimming · Sensitive masking · Token management       │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client Layer                           │
│  Connection pool · Circuit breaker · Retry · Auth            │
│  Tool discovery · Health monitoring                          │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **6-Layer Context Engineering** - Structured context assembly with priority-based token trimming and configurable merge strategies (replace/append/union)
- **Skill Engine** - Two-level matching (keyword 40% + embedding 60%), activation rules, version binding, hot reload, degradation with recursive fallback
- **Workflow Engine** - 4 step types (MCP tool, LLM reasoning, sub-workflow, skill call), conditional branching, template variable substitution, checkpoint/resume
- **Agent Loop (ReAct)** - Think → Act → Observe → Reflect cycle with LLM-driven planning, memory management, and scratch pad
- **MCP Client** - Connection pooling, exponential backoff retry, circuit breaker (CLOSED→OPEN→HALF_OPEN), endpoint discovery, auth management
- **Sensitive Data Masking** - Built-in patterns for phone, ID card, email, bank card + custom YAML rules
- **Hot Reload** - File watcher (watchdog) + API trigger for skills and workflows with atomic replace
- **Observability** - Structured JSON logging with trace_id propagation, Prometheus metrics (agent, skill, workflow, MCP dimensions)
- **Deployment** - Docker Compose with MySQL 8.0 + Redis 7 + health checks

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

## Project Structure

```
agent-core/
├── app/
│   ├── agent/           # Agent Loop (ReAct)
│   │   ├── loop.py      # Think→Act→Observe→Reflect cycle
│   │   ├── models.py    # Thought, ActionResult, Observation, Reflection
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
│   │   ├── engine.py    # Main entry point
│   │   ├── matcher.py   # Two-level matching
│   │   ├── executor.py  # Execution + degradation
│   │   ├── registry.py  # Version management
│   │   ├── loader.py    # YAML loader
│   │   └── validator.py # Validation
│   ├── workflow/         # Workflow Engine
│   │   ├── engine.py    # Step executor
│   │   ├── context.py   # Workflow context
│   │   └── models.py    # Step/Workflow models
│   └── main.py          # FastAPI app factory
├── config/
│   ├── settings.yaml    # Main config
│   └── masking_rules.yaml # Custom masking rules
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── scripts/
│   └── init.sql         # Database schema
├── tests/
│   ├── unit/            # 86 unit tests
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
python -m pytest tests/unit/test_skill_engine.py -v

# Run integration tests only
python -m pytest tests/integration/ -v
```

## Key Design Decisions

- **Skill as MCP upper-layer abstraction** - Skills encapsulate workflow + context + activation rules, providing richer semantics than raw MCP tools
- **Agent Loop as top-level controller** - ReAct pattern drives all task execution; Skills and Workflows are invoked through it
- **Dual storage** - Redis for hot state (fast read/write), MySQL for cold persistence (checkpoint every 5 versions)
- **Circuit breaker** - Prevents cascading failures from MCP tool timeouts; supports automatic recovery
- **Hot reload with version binding** - Running agents bind to the skill version at execution start; new executions use updated versions

## License

MIT
