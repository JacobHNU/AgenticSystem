# AgenticSystem V2.0

## Workflow Lifecycle Mode — 生产级 Agent Loop 升级

**版本**: 2.0.0
**日期**: 2026-06-05
**基于**: AgenticSystem V1.0 (ReAct Agent Loop)

---

## 一、升级背景

V1.0 的 Agent Loop 采用纯 ReAct 模式（Think → Act → Observe → Reflect），每轮迭代调用 LLM **2 次**（Think + Reflect）。对于软件业务场景中大量存在的**固定流程工具调度**任务，这种模式存在明显浪费：

- 每次调用都经过 LLM 推理，即使 workflow 已经完全确定
- 反思步骤对确定性流程无价值，但仍然消耗 token 和延迟
- 无法从"首次构建"到"后续快速执行"自动演进

V2.0 引入 **Workflow Lifecycle Mode**，根据 Skill 类型和 Workflow 是否存在，动态选择最优执行路径。

---

## 二、核心架构变更

### 2.1 三路径执行模型

```
AgentLoop.run(task, context)
  │
  ├─ _resolve_skill() → SkillMatcher（关键词 + 语义匹配，无 LLM 调用）
  │
  ├─ 匹配成功 + 置信度 ≥ 阈值
  │   │
  │   ├─ Skill.type == "fixed" 且 workflows.main 存在
  │   │   └─ ★ Fast Path（快速路径）
  │   │       跳过 Think/Reflect，直接执行预定义 Workflow
  │   │       LLM 调用: 0 次（路由），0-1 次（可选 post-eval）
  │   │
  │   └─ Skill.type == "flexible" 且 process_description 存在
  │       └─ ★ Build Path（构建路径）
  │           LLM 构建 Workflow → 执行 → 评估 → 持久化
  │           下次调用自动走 Fast Path
  │
  └─ 无匹配 / 低置信度 / lifecycle 禁用
      └─ ReAct Path（完整 ReAct 循环，V1.0 行为不变）
```

### 2.2 执行模式对比

| 维度 | Fast Path | Build Path | ReAct Path |
|------|-----------|------------|------------|
| **触发条件** | fixed skill + workflow 存在 | flexible skill + 首次调用 | 无 skill 匹配 |
| **LLM 调用（路由）** | 0 次 | 0 次 | 2 次/轮 |
| **LLM 调用（workflow 内）** | 仅 llm_reasoning 步骤 | 1 次（构建）+ llm_reasoning 步骤 | 2 次/轮 + llm_reasoning 步骤 |
| **Post-eval（可选）** | 1 次 | 1 次 | 无（内含在 Reflect 中） |
| **预期延迟** | ~250ms | ~4s（首次） | ~4.5s+/轮 |
| **重用已有组件** | SkillExecutor + WorkflowEngine | DynamicWorkflowBuilder + SkillExecutor | 全部原路径 |

---

## 三、Skill 生命周期

V2.0 定义了 Skill 从"描述"到"固化"的完整生命周期：

```
阶段 1: 定义（Flexible Skill）
  ┌─────────────────────────────────────┐
  │ skill.yaml:                          │
  │   type: flexible                     │
  │   process_description: "业务流程描述" │
  │   workflows.main: ""  (空)           │
  └──────────────┬──────────────────────┘
                 │ 首次调用
                 ▼
阶段 2: 构建（Build Path）
  ┌─────────────────────────────────────┐
  │ DynamicWorkflowBuilder.build_workflow│
  │   → LLM 解析业务流程 + 可用工具      │
  │   → 生成 WorkflowDefinition          │
  │   → 注册到 WorkflowEngine            │
  │   → 执行 Workflow                    │
  │   → 评估执行结果                     │
  └──────────────┬──────────────────────┘
                 │ 成功后
                 ▼
阶段 3: 固化（Promote + Persist）
  ┌─────────────────────────────────────┐
  │ SkillRegistry.promote_skill()        │
  │   → type: flexible → fixed           │
  │   → workflows.main: "skill_dynamic"  │
  │   → 版本号 +1                        │
  │                                      │
  │ SkillEngine.persist_workflow()       │
  │   → 保存 WorkflowDefinition 到磁盘   │
  │   → workflows/skill_dynamic.yaml     │
  └──────────────┬──────────────────────┘
                 │ 后续调用
                 ▼
阶段 4: 快速执行（Fast Path）
  ┌─────────────────────────────────────┐
  │ type: fixed, workflows.main 已存在   │
  │ → 跳过 Think/Reflect                 │
  │ → 直接执行 Workflow                  │
  │ → 0 LLM 调用（路由层）              │
  └─────────────────────────────────────┘
```

**重启恢复**：系统启动时，`WorkflowEngine.load_definitions_from_disk()` 自动加载 `workflows/` 目录下的所有 YAML 文件，无需重新构建。

---

## 四、修改文件清单

### 4.1 核心改动

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `app/agent/loop.py` | **重构** | `run()` 增加生命周期路由；新增 `_resolve_skill`、`_fast_path`、`_build_path`、`_react_loop`、`_post_evaluate` 5 个方法 |
| `app/agent/models.py` | 扩展 | 新增 `ExecutionMode` 枚举（FAST_PATH / BUILD_PATH / REACT）；`TaskResult` 增加 `execution_mode` 字段 |
| `app/skill/validator.py` | 修改 | 放宽验证：flexible skill 不再强制要求 `workflows.main`，改为要求 `process_description` |
| `app/skill/engine.py` | 扩展 | 新增 `persist_workflow()` 方法；在 `execute()` 的 solidification 流程中自动持久化到磁盘 |
| `app/workflow/engine.py` | 扩展 | 新增 `save_definition()`（YAML 磁盘持久化）和 `load_definitions_from_disk()`（启动恢复）；`__init__` 增加 `workflows_dir` 参数 |
| `config/settings.yaml` | 扩展 | 新增 `workflow_lifecycle` 配置段 |

### 4.2 测试文件

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `tests/unit/test_agent_loop.py` | 扩展 | 新增 `TestWorkflowLifecycle` 类，10 个测试用例 |
| `tests/unit/test_skill_validator.py` | **新建** | 6 个测试用例覆盖 flexible/fixed 验证逻辑 |
| `tests/unit/test_skill_executor.py` | 修复 | Mock 对象补充 `metrics` 属性（预存问题修复） |

### 4.3 文档

| 文件 | 说明 |
|------|------|
| `docs/AgenticSystem-V2.0.md` | 本文档 |
| `docs/workflow-lifecycle-plan.md` | 实施计划详细文档 |

---

## 五、配置说明

### 5.1 新增配置项

```yaml
# config/settings.yaml

workflow_lifecycle:
  # 是否启用 post-execution 评估（每次 Fast/Build Path 完成后调用 1 次 LLM 评估质量）
  enable_post_evaluation: false

  # Skill 匹配置信度阈值，低于此值走 ReAct Path
  fast_path_confidence_threshold: 0.6

  # 是否自动将构建的 Workflow 持久化到磁盘
  auto_persist_workflows: true
```

### 5.2 Agent Loop 运行时配置

```python
# AgentLoop config 对象支持的属性（均通过 getattr 读取，有默认值）
config.enable_workflow_lifecycle = True        # 总开关，默认 True
config.fast_path_confidence_threshold = 0.6    # 置信度阈值，默认 0.6
config.enable_post_evaluation = False          # Fast Path 默认关闭，Build Path 默认开启
config.max_iterations = 10                     # ReAct Path 最大迭代次数
config.checkpoint_interval = 3                 # ReAct Path checkpoint 间隔
```

---

## 六、API 变更

### 6.1 TaskResult 新增字段

```python
class TaskResult(BaseModel):
    # ... 原有字段不变 ...
    execution_mode: ExecutionMode = ExecutionMode.REACT  # 新增
```

`execution_mode` 取值：
- `"fast_path"` — 快速路径执行
- `"build_path"` — 构建路径执行
- `"react"` — 完整 ReAct 循环

### 6.2 API 响应示例

**Fast Path 响应**:
```json
{
  "status": "completed",
  "message": "Workflow executed successfully",
  "data": {"result": "verified", "employee_id": "E001"},
  "execution_report": {
    "metrics": {"tool_calls": 2, "llm_calls": 0, "total_duration_ms": 180}
  },
  "total_iterations": 1,
  "execution_mode": "fast_path"
}
```

**Build Path 响应**:
```json
{
  "status": "completed",
  "message": "Workflow built and executed successfully",
  "data": {"result": "processed"},
  "execution_report": {
    "metrics": {"tool_calls": 3, "llm_calls": 1},
    "evaluation": {"quality": "good", "message": "Task completed adequately"},
    "workflow_persisted": true,
    "promoted_to_fixed": true
  },
  "total_iterations": 1,
  "execution_mode": "build_path"
}
```

---

## 七、测试覆盖

### 7.1 测试统计

| 模块 | 测试数 | 状态 |
|------|--------|------|
| `test_agent_loop.py` | 12 (1 原有 + 11 新增) | ✅ 全部通过 |
| `test_skill_validator.py` | 6 (新建) | ✅ 全部通过 |
| `test_skill_executor.py` | 2 (修复 mock) | ✅ 全部通过 |
| `test_skill_engine.py` | 4 | ✅ 全部通过 |
| `test_workflow_engine.py` | 3 | ✅ 全部通过 |
| 其他模块 | 75 | ✅ 全部通过 |
| **总计** | **102** | **✅ 102 passed, 0 failed** |

### 7.2 关键测试场景

| 测试 | 验证内容 |
|------|---------|
| `test_fast_path_skips_think_and_reflect` | Fast Path 不调用 LLM（0 次） |
| `test_fast_path_calls_skill_engine_execute` | Fast Path 正确委托给 SkillEngine |
| `test_build_path_for_flexible_skill` | Build Path 执行 + 持久化 + promote |
| `test_fallback_to_react_when_no_match` | 无匹配时回退到 ReAct |
| `test_fallback_to_react_when_low_confidence` | 低置信度时回退到 ReAct |
| `test_fallback_to_react_when_lifecycle_disabled` | 禁用 lifecycle 时走 ReAct |
| `test_post_evaluation_on_fast_path` | Post-eval 开启时调用 1 次 LLM |
| `test_fast_path_handles_degraded_success` | 降级执行返回 partial 状态 |
| `test_fast_path_handles_failure` | 执行失败返回 failed 状态 |
| `test_build_path_persistence_failure_is_non_fatal` | 持久化失败不影响任务完成 |
| `test_fixed_skill_requires_workflows_main` | Fixed skill 必须有 workflows.main |
| `test_flexible_skill_without_workflows_main_passes` | Flexible skill 允许无 workflows.main |

---

## 八、兼容性

### 8.1 向后兼容

- **现有 Fixed Skill 无需改动**：`type: "fixed"` + `workflows.main` 已存在的 Skill 自动走 Fast Path
- **ReAct 行为不变**：`_think()`、`_act()`、`_observe()`、`_reflect()` 方法完全保留
- **TaskResult 默认值**：`execution_mode` 默认为 `"react"`，不影响现有消费者
- **配置可选**：`workflow_lifecycle` 配置段不设置时使用默认值

### 8.2 升级步骤

1. 更新代码（拉取 V2.0 变更）
2. `config/settings.yaml` 中添加 `workflow_lifecycle` 配置段（可选）
3. 运行测试：`python -m pytest tests/ -v`
4. 对现有 Flexible Skill，首次调用会自动触发 Build Path 构建 workflow

### 8.3 回退方案

如需禁用 Workflow Lifecycle Mode，在配置中设置：

```yaml
workflow_lifecycle:
  enable_post_evaluation: false
```

或在 AgentLoop config 中设置 `enable_workflow_lifecycle = False`，所有请求将回退到 V1.0 的纯 ReAct 模式。

---

## 九、性能基准

| 场景 | V1.0 (ReAct) | V2.0 (Fast Path) | 提升 |
|------|-------------|-------------------|------|
| 固定 workflow 执行 | ~4.5s (2 LLM calls) | ~250ms (0 LLM calls) | **~18x** |
| 首次构建 workflow | ~4.5s (需人工预定义) | ~4s (自动构建) | 自动化 |
| 已构建 workflow 再次执行 | ~4.5s | ~250ms | **~18x** |
| 无匹配任务 | ~4.5s | ~4.5s (不变) | — |

> 注：延迟为估算值，实际取决于 LLM 响应速度、工具调用延迟和网络条件。

---

## 十、架构图（V2.0）

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

---

## 十一、依赖关系

### 11.1 模块依赖图（V2.0 新增部分）

```
app/agent/loop.py
  → app/agent/models.py (ExecutionMode, TaskResult)
  → app/skill/engine.py (SkillEngine.match, execute, persist_workflow)

app/skill/engine.py
  → app/workflow/engine.py (WorkflowEngine.save_definition)

app/workflow/engine.py
  → yaml (PyYAML, 已在 requirements.txt 中)
  → pathlib (标准库)
```

### 11.2 外部依赖

无新增外部依赖。所有改动基于已有的 PyYAML、Pydantic、标准库。

---

## 十二、未来演进

| 方向 | 说明 |
|------|------|
| **Workflow 版本管理** | 对已固化的 workflow 支持版本回滚和 A/B 测试 |
| **并行 Build Path** | 多个 flexible skill 并行构建 workflow |
| **Workflow 优化** | 根据执行 metrics 自动优化 workflow 步骤顺序 |
| **跨 Agent Workflow 共享** | 不同 Agent 实例共享已构建的 workflow |
| **实时 Workflow 编辑** | Admin API 支持在线修改已固化的 workflow |
