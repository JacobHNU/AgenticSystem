# Agent Core 架构设计文档

**日期**: 2026-05-29
**版本**: v1.0
**状态**: 设计完成

---

## 1. 概述

### 1.1 设计目标

构建一个生产级 Agent 基座服务，承载 Agent Loop 的持续运行、会话状态管理、Skill 与 Workflow 的生命周期管理。核心特性：

- Agent Loop 作为最高层控制循环（ReAct 模式），调用 Skill Engine 和 Workflow Engine
- Skill 作为 MCP 工具的上层抽象，内嵌上下文工程和触发条件
- Workflow 由 Skill 编排，步骤类型支持 mcp_tool、llm_reasoning、sub_workflow、skill_call
- 统一的 MCP Client Layer，连接池、鉴权、重试、熔断四层保护
- Hot Reload 支持不停机更新 Skill 和 Workflow 定义

### 1.2 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Core Service                         │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Agent Loop Pool                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │ Agent Loop  │  │ Agent Loop  │  │ Agent Loop  │  ...   │  │
│  │  │ (Research)  │  │ (Review)    │  │ (Custom)    │       │  │
│  │  │ SkillSet: A │  │ SkillSet: B │  │ SkillSet: C │       │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │  │
│  └─────────┼────────────────┼────────────────┼───────────────┘  │
│            └────────────────┼────────────────┘                  │
│                             ↓ 统一接口                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Skill Engine                            │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │ Skill: 报销  │  │ Skill: 请假 │  │ Skill: 采购 │  ...   │  │
│  │  │ → WF: expense│  │ → WF: leave │  │ → WF: purch │       │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │  │
│  └─────────┼────────────────┼────────────────┼───────────────┘  │
│            └────────────────┼────────────────┘                  │
│                             ↓ 编排调用                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Workflow Engine                          │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  步骤执行器：解析模板 → 评估条件 → 调用 MCP Client   │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                             ↓ 复用                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   MCP Client Layer                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │连接池管理    │  │ 重试策略     │  │ 鉴权管理    │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  │  ┌─────────────┐  ┌─────────────┐                         │  │
│  │  │ 熔断器      │  │ trace_id    │                         │  │
│  │  └─────────────┘  └─────────────┘                         │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                             │                                    │
│  ┌──────────────────────────┴────────────────────────────────┐  │
│  │                   Hot Reload Manager                       │  │
│  │  监听 skills/ workflows/ 目录 → 触发重新扫描               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   State Store                              │  │
│  │  ┌─────────────┐  ┌─────────────┐                         │  │
│  │  │ Redis (热)   │  │ MySQL (冷)   │                         │  │
│  │  └─────────────┘  └─────────────┘                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/gRPC
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │  mcp-hr    │  │ mcp-finance│  │mcp-discovery│
   └────────────┘  └────────────┘  └────────────┘
```

### 1.3 核心调用链

```
Agent Loop (ReAct)
    │
    ├── Think: 理解意图，决定激活哪个 Skill
    │
    ├── Act: 调用 Skill Engine.execute(skill_name, params)
    │           │
    │           ├── Skill 加载自身定义（含引用的 Workflow）
    │           │
    │           └── 调用 Workflow Engine.execute(workflow_name, context)
    │                   │
    │                   ├── 解析步骤模板，评估条件
    │                   │
    │                   └── 调用 MCP Client.call_tool(tool, action, params)
    │
    ├── Observe: 收集执行结果
    │
    └── Reflect: 判断是否需要迭代修正
```

---

## 2. Agent Loop 与状态管理

### 2.1 Agent Loop 定义

Agent Loop 是最高层控制循环，遵循 ReAct（Think → Act → Observe → Reflect）模式。

```python
class AgentLoop:
    """Agent Loop 实例"""

    def __init__(self, agent_id: str, skill_set: List[str], config: AgentConfig):
        self.agent_id = agent_id
        self.skill_set = skill_set
        self.config = config
        self.state = AgentState(agent_id=agent_id, skill_set=skill_set)
        self.skill_engine = config.skill_engine
        self.state_store = config.state_store

    async def run(self, task: Task) -> TaskResult:
        """主循环"""
        for iteration in range(self.config.max_iterations):
            # Think
            thought = await self._think(task)

            # Act
            action_result = await self._act(thought)

            # Observe
            observation = await self._observe(action_result)

            # Reflect
            reflection = await self._reflect(observation)

            if reflection.should_stop:
                return reflection.result

            # 定期 checkpoint
            if iteration % self.config.checkpoint_interval == 0:
                await self._checkpoint()

        return TaskResult(status="max_iterations_reached")

    async def _think(self, task: Task) -> Thought:
        """理解意图，决定激活哪个 Skill"""
        prompt = self._build_think_prompt(task)
        response = await self.config.llm.complete(prompt)
        return Thought.parse(response)

    async def _act(self, thought: Thought) -> ActionResult:
        """执行动作：调用 Skill 或直接调用工具"""
        if thought.action_type == "skill":
            return await self.skill_engine.execute(
                skill_name=thought.skill_name,
                params=thought.params,
                trace_id=self.state.trace_id
            )
        elif thought.action_type == "tool":
            return await self.config.mcp_client.call_tool(
                tool_name=thought.tool_name,
                action=thought.action,
                params=thought.params,
                trace_id=self.state.trace_id
            )

    async def _observe(self, result: ActionResult) -> Observation:
        """收集执行结果"""
        return Observation(
            status=result.status,
            data=result.data,
            error=result.error,
            degradation_info=result.degradation_info
        )

    async def _reflect(self, observation: Observation) -> Reflection:
        """判断是否需要迭代修正"""
        prompt = self._build_reflect_prompt(observation)
        response = await self.config.llm.complete(prompt)
        return Reflection.parse(response)

    async def _checkpoint(self):
        """将状态写入 State Store"""
        await self.state_store.save(self.state)
```

### 2.2 状态结构

```python
class AgentState(BaseModel):
    """Agent Loop 持久化状态"""
    agent_id: str
    session_id: str
    skill_set: List[str]
    trace_id: str                         # 当前调用链追踪 ID

    # 推理状态
    memory: List[Message]                 # 对话历史（压缩后）
    task_stack: List[TaskFrame]           # 任务栈（支持嵌套任务）
    current_step: int
    scratch_pad: Dict[str, Any]           # 临时推理数据

    # 工作流状态
    workflow_context: Optional[WorkflowContext]

    # 元数据
    created_at: datetime
    last_checkpoint: datetime
    version: int                          # 乐观锁版本号
```

### 2.3 State Store

**存储层级**：

| 层级 | 方案 | 用途 |
|------|------|------|
| 热缓存 | Redis | Agent Loop 运行时的快速读写，TTL 1h |
| 持久存储 | MySQL | 状态快照、会话恢复、历史审计 |

**MySQL 表结构**：

```sql
CREATE TABLE agent_states (
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

CREATE TABLE agent_state_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    event_type ENUM('pause', 'resume', 'destroy', 'migrate', 'checkpoint') NOT NULL,
    state_snapshot JSON,
    created_at DATETIME NOT NULL,
    INDEX idx_agent_event (agent_id, event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2.4 生命周期事件

| 事件 | 触发条件 | 行为 |
|------|----------|------|
| `on_pause` | 空闲超时 / 手动暂停 | 序列化状态 → 写入 MySQL |
| `on_resume` | 收到新任务 / 手动恢复 | 从 Redis/MySQL 读取 → 恢复执行 |
| `on_destroy` | 服务下线 / 强制终止 | 强制快照 → 标记 `terminated` |
| `on_migrate` | 负载均衡 / 节点故障 | 序列化 → 传输到目标节点 → 恢复 |
| `on_checkpoint` | 每 N 步 / 定时器 | 增量快照 → 写入 MySQL |

---

## 3. Skill 定义与 Skill Engine

### 3.1 Skill 目录结构

```
skills/
├── expense-reimbursement/
│   ├── skill.yaml              # Skill 元数据与配置
│   ├── context/                # 上下文工程模板（六层结构）
│   │   ├── L1-base.jinja2
│   │   ├── L2-business.jinja2
│   │   ├── L3-dynamic.jinja2
│   │   └── L6-output.jinja2
│   └── prompts/                # Agent Loop 推理提示词
│       ├── think.md
│       └── reflect.md
├── leave-request/
│   ├── skill.yaml
│   ├── context/
│   └── prompts/
```

### 3.2 skill.yaml 完整定义

```yaml
name: expense-reimbursement
version: "1.0.0"
description: "员工差旅报销申请"
domain: finance
tags: [报销, 费用, 差旅]

# ──────────────────────────────────────────────
# 第一级触发：意图匹配
# ──────────────────────────────────────────────
intent:
  keywords: ["报销", "费用申请", "出差报销"]
  embedding_text: "员工差旅报销申请流程"

# ──────────────────────────────────────────────
# 第二级触发：激活规则
# ──────────────────────────────────────────────
activation_rules:
  preconditions:
    - type: time_window
      config:
        start: "09:00"
        end: "18:00"
        timezone: "Asia/Shanghai"
    - type: role_check
      config:
        min_level: 3
    - type: feature_flag
      config:
        flag: "expense_v2_enabled"

  context_dependencies:
    - skill: data-fetch
      required: true
      result_key: employee_data
    - skill: budget-check
      required: false
      result_key: budget_info
      fallback_value:                    # 可选依赖失败时的默认值
        status: unknown
        remaining: null
        message: "预算信息暂不可用，将跳过预算校验"

  logic: AND

# ──────────────────────────────────────────────
# Skill 编排的工作流
# ──────────────────────────────────────────────
workflows:
  main: expense_reimbursement

  degradation_policy:
    triggers:
      - error_type: tool_unavailable
        affected_tools: [mcp-finance]
      - error_type: timeout
        threshold_ms: 5000
      - error_type: rate_limited
      - error_type: llm_confidence_low
        threshold: 0.5

    fallbacks:
      - workflow: expense_no_risk
        skip_steps: [risk_analysis]
        conditions:
          - error_type == tool_unavailable
      - workflow: expense_simple
        skip_steps: [risk_analysis, create_document]
        conditions:
          - error_type == timeout
      - workflow: expense_manual
        action: escalate
        conditions:
          - always

# ──────────────────────────────────────────────
# 上下文工程配置
# ──────────────────────────────────────────────
context:
  template_dir: ./context
  token_limit: 4000

  layers:
    L1_base:
      priority: 1
      source: ./context/L1-base.jinja2
      merge_strategy: replace
    L2_business:
      priority: 2
      source: ./context/L2-business.jinja2
      domain_filter: true
      merge_strategy: replace
    L3_dynamic:
      priority: 3
      source: ./context/L3-dynamic.jinja2
      merge_strategy: append
    L4_history:
      priority: 4
      source: ./context/L4-history.jinja2
      merge_strategy: append
    L5_tools:
      priority: 5
      source: null
      merge_strategy: union
    L6_output:
      priority: 6
      source: ./context/L6-output.jinja2
      merge_strategy: replace

# ──────────────────────────────────────────────
# Agent Loop 推理配置
# ──────────────────────────────────────────────
agent:
  think_prompt: ./prompts/think.md
  reflect_prompt: ./prompts/reflect.md
  max_iterations: 5
  confidence_threshold: 0.85

# ──────────────────────────────────────────────
# 权限与限流
# ──────────────────────────────────────────────
permissions:
  required_tools: [mcp-hr, mcp-finance]
  rate_limit: 100
```

### 3.3 Merge Strategy 说明

| 策略 | 行为 | 适用层级 |
|------|------|----------|
| `replace` | 覆盖该层已有内容 | L1, L2, L6 |
| `append` | 追加到该层末尾 | L3, L4 |
| `union` | 合并并去重 | L5 |

### 3.4 Skill Engine 核心实现

```python
class SkillEngine:
    """Skill 引擎"""

    def __init__(self, workflow_engine, context_builder, mcp_client):
        self.definitions: Dict[str, VersionedDefinition] = {}
        self.workflow_engine = workflow_engine
        self.context_builder = context_builder
        self.mcp_client = mcp_client

    async def execute(
        self,
        skill_name: str,
        params: Dict[str, Any],
        trace_id: str = None
    ) -> SkillResult:
        """执行 Skill"""

        # 1. 加载定义（绑定版本）
        skill_def = self.definitions.get(skill_name)
        if not skill_def:
            return SkillResult(status="failed", error=f"Skill '{skill_name}' not found")

        # 2. 检查激活规则
        if not self._check_activation(skill_def, params):
            return SkillResult(status="failed", error="Activation rules not met")

        # 3. 构建上下文（六层）
        context = await self.context_builder.build(
            layers=skill_def.context.layers,
            domain=skill_def.domain,
            variables=params
        )

        # 4. 调用主工作流
        result = await self._execute_with_degradation(
            workflow=skill_def.workflows.main,
            context=context,
            policy=skill_def.workflows.degradation_policy,
            trace_id=trace_id
        )

        return result

    async def _execute_with_degradation(
        self,
        workflow: str,
        context: WorkflowContext,
        policy: DegradationPolicy,
        trace_id: str,
        depth: int = 0
    ) -> SkillResult:
        """带降级的工作流执行"""

        max_depth = 2

        if depth >= max_depth:
            return SkillResult(
                status="failed",
                degradation_info=DegradationInfo(
                    original_error="Max degradation depth exceeded",
                    trigger_type="depth_limit",
                    fallback_workflow="escalate"
                )
            )

        result = await self.workflow_engine.execute(workflow, context, trace_id)

        if result.status == "success":
            return SkillResult(status="success", data=result.data)

        # 匹配降级触发条件
        matched = self._match_fallback(result.error, policy)
        if not matched or matched.action == "escalate":
            return SkillResult(
                status="failed",
                degradation_info=DegradationInfo(
                    original_error=result.error,
                    trigger_type="escalate"
                )
            )

        # 递归执行降级工作流
        return await self._execute_with_degradation(
            workflow=matched.workflow,
            context=context,
            policy=policy,
            trace_id=trace_id,
            depth=depth + 1
        )
```

### 3.5 SkillResult 与降级状态

```python
class SkillResult(BaseModel):
    status: Literal["success", "failed", "degraded_success"]
    data: Dict[str, Any] = {}
    degradation_info: Optional[DegradationInfo] = None

class DegradationInfo(BaseModel):
    original_error: str
    trigger_type: str
    fallback_workflow: str
    skipped_steps: List[str] = []
    timestamp: datetime
```

---

## 4. Workflow Engine

### 4.1 Workflow 目录结构

```
workflows/
├── expense-reimbursement.yaml
├── expense-no-risk.yaml
├── leave-request.yaml
└── common/
    ├── verify-employee.yaml
    └── budget-check.yaml
```

### 4.2 workflow.yaml 定义

```yaml
name: expense_reimbursement
version: "1.0.0"
description: "差旅报销完整流程"

steps:
  - name: verify_employee
    type: mcp_tool
    mcp_tool: mcp-hr
    action: verify_employee
    input_template:
      employee_id: "{{ user_id }}"
    output_key: employee_info
    condition: null
    retry:
      max_attempts: 3
      backoff_ms: [1000, 2000, 4000]

  - name: validate_budget
    type: mcp_tool
    mcp_tool: mcp-finance
    action: validate_expense
    input_template:
      amount: "{{ amount }}"
      category: "{{ category }}"
      employee_level: "{{ employee_info.level }}"
    output_key: budget_validation
    condition: "{{ employee_info.valid }} == true"
    retry:
      max_attempts: 3
      backoff_ms: [1000, 2000, 4000]

  - name: risk_analysis
    type: llm_reasoning
    domain: finance
    prompt_template: domains/finance/risk_analysis.jinja2
    input_template:
      employee: "{{ employee_info }}"
      budget: "{{ budget_validation }}"
      amount: "{{ amount }}"
    output_key: risk_result
    output_schema:
      risk_level: "string"
      reasoning: "string"
    condition: "{{ budget_validation.approved }} == true"
    retry:
      max_attempts: 2

  - name: data_analysis
    type: skill_call
    skill: data-analyzer
    input_template:
      data: "{{ raw_data }}"
    output_key: analysis_result
    timeout_ms: 30000
    max_iterations: 3

  - name: sub_process
    type: sub_workflow
    workflow: common/verify-and-check
    input_template:
      user_id: "{{ user_id }}"
    output_key: verification
```

### 4.3 步骤类型

| 类型 | 说明 | 执行方式 |
|------|------|----------|
| `mcp_tool` | 调用 MCP 工具 | MCP Client Layer |
| `llm_reasoning` | LLM 推理 | Context Builder → LLM API |
| `sub_workflow` | 子工作流 | 递归调用 Workflow Engine |
| `skill_call` | 调用其他 Skill | 调用 Skill Engine（带 timeout 和 max_iterations） |

### 4.4 Workflow Engine 核心实现

```python
class WorkflowEngine:
    """工作流引擎"""

    def __init__(self, mcp_client, context_builder, llm_client):
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
        """执行工作流"""

        workflow = self.definitions.get(workflow_name)
        if not workflow:
            return WorkflowResult(status="failed", error=f"Workflow '{workflow_name}' not found")

        for step in workflow.steps:
            # 1. 条件评估
            if step.condition and not self._evaluate_condition(context, step.condition):
                context.add_history(step.name, "SKIPPED")
                continue

            # 2. 构建输入
            step_input = self._build_input(context, step.input_template)

            # 3. 根据类型执行
            if step.type == "mcp_tool":
                result = await self._execute_mcp_tool(step, step_input, trace_id)
            elif step.type == "llm_reasoning":
                result = await self._execute_llm_reasoning(step, step_input, context, trace_id)
            elif step.type == "sub_workflow":
                result = await self.execute(step.workflow, context, trace_id)
            elif step.type == "skill_call":
                result = await self._execute_skill_call(step, step_input, trace_id)
            else:
                result = StepResult(status="failed", error=f"Unknown step type: {step.type}")

            # 4. 处理结果
            if result.status == "success":
                context.set(step.output_key, result.data)
                context.add_history(step.name, "COMPLETED", result.data)
            else:
                context.add_history(step.name, "FAILED", result.error)
                return WorkflowResult(status="failed", error=result.error, context=context)

            # 5. checkpoint
            await self._checkpoint(context, workflow_name)

        return WorkflowResult(status="success", data=context.data, history=context.history)

    async def _execute_mcp_tool(self, step, step_input, trace_id):
        """执行 MCP 工具步骤"""
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

    async def _execute_skill_call(self, step, step_input, trace_id):
        """执行 skill_call 步骤（带超时和迭代限制）"""
        try:
            result = await asyncio.wait_for(
                self.skill_engine.execute(
                    skill_name=step.skill,
                    params=step_input,
                    trace_id=trace_id,
                    max_iterations=step.max_iterations
                ),
                timeout=step.timeout_ms / 1000
            )
            return StepResult(status=result.status, data=result.data)
        except asyncio.TimeoutError:
            return StepResult(status="failed", error="Skill call timeout")
```

### 4.5 Workflow Context Checkpoint

```sql
CREATE TABLE workflow_checkpoints (
    workflow_name VARCHAR(128) NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    step_index INT NOT NULL,
    step_name VARCHAR(128) NOT NULL,
    context_data LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (workflow_name, agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**恢复时的二次校验**：通过 `step_name` 确认步骤未被热更新移位，若移位则按 `step_name` 查找新位置。

---

## 5. MCP Client Layer

### 5.1 组件结构

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │连接池管理    │  │ 鉴权管理     │  │ 重试控制器   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 熔断器      │  │ trace_id    │  │ 工具发现     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 核心接口

```python
class MCPClientLayer:
    """MCP 统一客户端层"""

    async def call_tool(
        self,
        tool_name: str,
        action: str,
        params: Dict[str, Any],
        retry_config: Optional[RetryConfig] = None,
        trace_id: Optional[str] = None
    ) -> MCPResponse:

        # 继承或生成 trace_id
        trace_id = trace_id or current_trace_id.get() or uuid.uuid4().hex[:16]
        current_trace_id.set(trace_id)

        logger.info(f"[{trace_id}] MCP call: {tool_name}/{action}")

        # 1. 熔断检查
        cb = self.circuit_breakers.get(tool_name)
        if cb and cb.state == "open":
            return MCPResponse(
                success=False,
                error="tool_unavailable",
                error_type="tool_unavailable",
                retry_after=cb.retry_after
            )

        # 2. 获取工具端点
        endpoint = await self.discovery_client.get_endpoint(tool_name)

        # 3. 获取认证信息
        auth = self.auth_manager.get_auth(tool_name)

        # 4. 获取连接
        pool = self.pools.get(endpoint)
        conn = await pool.acquire()

        try:
            # 5. 带重试的调用
            response = await self.retry_controller.execute(
                func=self._do_request,
                args=(conn, endpoint, action, params, auth, trace_id),
                config=retry_config
            )

            if cb:
                cb.record_success()
            return response

        except Exception as e:
            if cb:
                cb.record_failure()
            raise
        finally:
            await pool.release(conn)
```

### 5.3 熔断器

**状态机**：

```
CLOSED ──(连续失败 N 次)──→ OPEN
  ↑                            │
  │                    (超时后探测)
  │                            ↓
  └──(探测成功)── HALF_OPEN ──(探测失败)──→ OPEN
```

**错误响应**：

```python
class MCPResponse(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None
    retry_after: Optional[float] = None    # 秒，仅 tool_unavailable 时有值
    error_type: Optional[str] = None       # tool_unavailable | timeout | rate_limited
```

### 5.4 trace_id 调用链追踪

```
Agent Loop (trace_id=abc123)
    │
    ├── Skill Engine.execute("expense", trace_id="abc123")
    │
    │   └── Workflow Engine.execute("expense_reimbursement", trace_id="abc123")
    │
    │       ├── Step 1: MCP Client.call_tool("mcp-hr", "verify_employee", trace_id="abc123")
    │       │           → HTTP Header: X-Trace-Id: abc123
    │       │
    │       ├── Step 2: MCP Client.call_tool("mcp-finance", "validate_expense", trace_id="abc123")
    │       │
    │       └── Step 3: LLM Reasoning (trace_id 写入 prompt metadata)
    │
    └── Reflect: 日志归集 [abc123] 全链路追踪
```

---

## 6. Hot Reload Manager

### 6.1 组件结构

```
┌─────────────────────────────────────────────────────────────┐
│                   Hot Reload Manager                         │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ File Watcher │  │ API Trigger │  │ Validator   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐                          │
│  │ Reload      │  │ Graceful    │                          │
│  │ Strategy    │  │ Reload      │                          │
│  └─────────────┘  └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 文件监听

```python
class HotReloadManager:
    """热加载管理器"""

    def __init__(self, skill_engine, workflow_engine):
        self.skill_engine = skill_engine
        self.workflow_engine = workflow_engine
        self.observer = Observer()
        self._reload_lock = asyncio.Lock()

    def start(self):
        skill_handler = SkillFileHandler(self)
        self.observer.schedule(skill_handler, "skills/", recursive=True)
        workflow_handler = WorkflowFileHandler(self)
        self.observer.schedule(workflow_handler, "workflows/", recursive=True)
        self.observer.start()

    async def reload_skills(self, changed_files: List[str] = None):
        async with self._reload_lock:
            new_definitions = await self._scan_skills(changed_files)
            errors = self._validate_skills(new_definitions)
            if errors:
                return ReloadResult(success=False, errors=errors)

            old_definitions = self.skill_engine.definitions.copy()
            try:
                self.skill_engine.definitions = new_definitions
                return ReloadResult(success=True, count=len(new_definitions))
            except Exception as e:
                self.skill_engine.definitions = old_definitions
                raise
```

### 6.3 API 触发

```
POST /admin/reload/skills       → 重新扫描 skills/
POST /admin/reload/workflows    → 重新扫描 workflows/
POST /admin/reload/all          → 全量重载
```

### 6.4 优雅重载

- 正在执行的 Workflow 不中断（绑定旧版本）
- 新请求使用新版本
- 旧版本实例全部完成后清理

---

## 7. 降级策略执行流程

```
Workflow Engine 执行步骤
    │
    ├── 步骤成功 → 继续下一步
    │
    └── 步骤失败
         │
         ├── 匹配 degradation_policy.triggers
         │
         ├── 按优先级遍历 fallbacks
         │
         └── 执行降级工作流（depth + 1）
              │
              ├── 降级成功 → 返回 degraded_success
              │
              ├── 降级失败 → 递归降级（depth < max_depth）
              │
              └── 达到 max_degradation_depth → escalate 转人工
```

---

## 8. Agent Loop Reflect 阶段处理

```
Agent Loop: Reflect
    │
    ├── result.status == "success"
    │      → 正常流程，记录到 memory
    │
    ├── result.status == "degraded_success"
    │      → 记录降级信息到 scratch_pad
    │      → 决策：
    │         ├── 跳过关键步骤 → 标记"部分完成"，通知用户
    │         ├── 降级路径完整 → 标记完成，附带降级说明
    │         └── 质量不达标 → 触发重试或升级处理
    │
    └── result.status == "failed"
           │
           ├── result.error_type == "tool_unavailable"
           │      result.retry_after = 45.2s
           │      ├── retry_after < 10s → 等待后重试
           │      ├── 10s < retry_after < 60s → 尝试降级
           │      └── retry_after > 60s → escalate
           │
           └── 其他错误 → 错误处理逻辑
```

---

## 9. Skill Engine 详细设计

### 9.1 Skill Engine 作为 Agent Loop 唯一入口

Agent Loop 不直接调用 Workflow Engine 或 MCP Client，所有执行都通过 Skill Engine 中转：

```
Agent Loop
    │
    │  唯一入口
    ↓
┌─────────────────────────────────────────────────────────────┐
│                    Skill Engine                              │
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │ Skill Registry │  │ Skill Matcher │  │ Skill Executor│   │
│  │ (定义存储)     │  │ (两级匹配)    │  │ (执行编排)    │   │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘   │
│          │                  │                  │            │
│          └──────────────────┼──────────────────┘            │
│                             ↓                               │
│                    Workflow Engine                           │
│                    Context Builder                           │
│                    MCP Client Layer                          │
└─────────────────────────────────────────────────────────────┘
```

**为什么是唯一入口**：

1. Agent Loop 只需要知道 Skill 名称，不需要了解 Workflow 细节
2. Skill Engine 统一处理匹配、校验、上下文构建、降级
3. Agent Loop 的 `skill_set` 限制了它能调用的 Skill 范围

```python
class SkillEngine:
    """Skill 引擎 - Agent Loop 的唯一执行入口"""

    def __init__(self, workflow_engine, context_builder, mcp_client):
        self.workflow_engine = workflow_engine
        self.context_builder = context_builder
        self.mcp_client = mcp_client

        self.registry = SkillRegistry(max_history_versions=3)
        self.matcher = SkillMatcher(self.registry)
        self.executor = SkillExecutor(
            self.workflow_engine,
            self.context_builder,
            self.mcp_client
        )
        self.reload_manager = SkillReloadManager(self)

    async def execute(
        self,
        skill_name: str,
        params: Dict[str, Any],
        trace_id: str = None,
        max_iterations: int = None
    ) -> SkillResult:
        """执行 Skill - Agent Loop 的唯一调用接口"""
        skill_def = self.registry.get(skill_name)
        if not skill_def:
            return SkillResult(status="failed", error=f"Skill '{skill_name}' not found")
        return await self.executor.execute(
            skill_def=skill_def,
            params=params,
            trace_id=trace_id,
            max_iterations=max_iterations
        )

    async def match(self, request: str, context: Dict = None) -> List[SkillMatch]:
        """匹配 Skill - 供 Agent Loop 的 Think 阶段调用"""
        return await self.matcher.match(request, context)

    async def list_available(self, agent_skill_set: List[str]) -> List[SkillSummary]:
        """列出 Agent 可用的 Skill"""
        if agent_skill_set:
            return self.registry.list_by_names(agent_skill_set)
        return self.registry.list_all()
```

### 9.2 两级匹配逻辑

```
用户请求 / Agent Loop Think 输出
            │
            ↓
┌─────────────────────────────────────────────────────────────┐
│  第一级：Intent 匹配（快速筛选）                              │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ Keyword Matcher  │    │ Embedding Matcher│                │
│  │ 关键词精确匹配   │    │ 语义向量相似度   │                │
│  └────────┬────────┘    └────────┬────────┘                │
│           │                      │                          │
│           └──────────┬───────────┘                          │
│                      ↓                                      │
│              候选集（Top-K）                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  第二级：Activation Rules 评估（精确筛选）                    │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ Preconditions    │    │ Context Deps    │                │
│  │ 前提条件检查     │    │ 上下文依赖检查   │                │
│  └────────┬────────┘    └────────┬────────┘                │
│           │                      │                          │
│           └──────────┬───────────┘                          │
│                      ↓                                      │
│              激活的 Skill 列表                               │
└──────────────────────┬──────────────────────────────────────┘
```

**SkillMatcher 实现**：

```python
class SkillMatcher:
    """两级 Skill 匹配器"""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self.keyword_index: Dict[str, List[str]] = {}
        self.embedding_index: EmbeddingIndex = None
        self.embedding_model = None

    async def match(
        self,
        request: str,
        context: Dict = None,
        agent_skill_set: List[str] = None,
        top_k: int = 3
    ) -> List[SkillMatch]:
        """两级匹配"""
        # 第一级：Intent 匹配
        candidates = await self._match_intent(request, agent_skill_set, top_k)
        if not candidates:
            return []

        # 第二级：Activation Rules 评估
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
        self,
        request: str,
        agent_skill_set: List[str],
        top_k: int
    ) -> List[IntentMatch]:
        """第一级：Intent 匹配"""

        # 未指定范围时，使用所有已注册 Skill（开发调试友好）
        if agent_skill_set:
            available_skills = self.registry.list_by_names(agent_skill_set)
        else:
            available_skills = self.registry.list_all()

        results = []

        # Keyword 匹配
        keyword_hits = self._keyword_match(request, available_skills)
        results.extend(keyword_hits)

        # Embedding 匹配
        if self.embedding_index:
            embedding_hits = await self._embedding_match(request, available_skills, top_k)
            results = self._merge_results(results, embedding_hits)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _keyword_match(self, request: str, skills: List[SkillSummary]) -> List[IntentMatch]:
        """关键词匹配"""
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
                score = hit_count / len(skill.intent.keywords)
                results.append(IntentMatch(
                    skill_name=skill.name,
                    score=score,
                    method="keyword",
                    matched_keywords=matched_keywords
                ))
        return results

    async def _embedding_match(
        self,
        request: str,
        skills: List[SkillSummary],
        top_k: int
    ) -> List[IntentMatch]:
        """Embedding 语义匹配"""
        request_embedding = await self.embedding_model.encode(request)

        scores = []
        for skill in skills:
            if skill.intent.embedding_vector is not None:
                sim = cosine_similarity(request_embedding, skill.intent.embedding_vector)
                scores.append((skill.name, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [
            IntentMatch(skill_name=name, score=score, method="embedding")
            for name, score in scores[:top_k]
        ]

    def _merge_results(
        self,
        keyword_results: List[IntentMatch],
        embedding_results: List[IntentMatch]
    ) -> List[IntentMatch]:
        """合并结果：Keyword 权重 0.4，Embedding 权重 0.6"""
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
        self,
        candidate: IntentMatch,
        context: Dict
    ) -> ActivationResult:
        """第二级：Activation Rules 评估"""
        skill_def = self.registry.get(candidate.skill_name)
        rules = skill_def.activation_rules

        if not rules:
            return ActivationResult(activated=True, confidence=candidate.score)

        # Preconditions
        precondition_results = []
        for precondition in rules.preconditions:
            result = await self._check_precondition(precondition, context)
            precondition_results.append(result)

        if rules.logic == "AND":
            preconditions_ok = all(precondition_results)
        else:
            preconditions_ok = any(precondition_results)

        # Context Dependencies
        dep_results = []
        for dep in rules.context_dependencies:
            result = await self._check_context_dependency(dep, context)
            dep_results.append(result)

        if rules.logic == "AND":
            deps_ok = all(dep_results)
        else:
            deps_ok = any(dep_results)

        activated = preconditions_ok and deps_ok
        rule_pass_rate = (sum(precondition_results) + sum(dep_results)) / \
                         (len(precondition_results) + len(dep_results)) \
                         if (precondition_results or dep_results) else 1.0

        return ActivationResult(
            activated=activated,
            confidence=candidate.score * rule_pass_rate,
            matched_rules={
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
        """检查前提条件"""
        if precondition.type == "time_window":
            now = datetime.now().time()
            start = time.fromisoformat(precondition.config["start"])
            end = time.fromisoformat(precondition.config["end"])
            return start <= now <= end
        elif precondition.type == "role_check":
            user_level = context.get("user_level", 0)
            return user_level >= precondition.config.get("min_level", 0)
        elif precondition.type == "feature_flag":
            return self.feature_flags.is_enabled(precondition.config["flag"])
        return True

    async def _check_context_dependency(self, dep: ContextDependency, context: Dict) -> bool:
        """检查上下文依赖"""
        skill_result = context.get(f"skill_result_{dep.skill}")

        if skill_result is None:
            if dep.required:
                return False
            else:
                # 可选依赖，注入 fallback_value
                if dep.fallback_value is not None:
                    context[dep.result_key] = dep.fallback_value
                return True

        context[dep.result_key] = skill_result.get(dep.result_key)
        return True
```

### 9.3 Skill Registry（版本管理与热加载）

```python
class SkillRegistry:
    """Skill 定义注册表（内置历史版本管理）"""

    def __init__(self, max_history_versions: int = 3):
        self._skills: Dict[str, VersionedDefinition] = {}
        self._history: Dict[str, List[VersionedDefinition]] = {}
        self._active_bindings: Dict[str, int] = {}  # execution_id → version
        self._max_history = max_history_versions
        self._lock = asyncio.Lock()

    def get(self, name: str, execution_id: str = None) -> Optional[SkillDefinition]:
        """获取 Skill 定义"""
        versioned = self._skills.get(name)
        if not versioned:
            return None

        # 如果有执行绑定，返回绑定的版本
        if execution_id and execution_id in self._active_bindings:
            bound_version = self._active_bindings[execution_id]
            if bound_version != versioned.version:
                return self._get_historical_version(name, bound_version)

        return versioned.definition

    def _get_historical_version(self, name: str, version: int) -> Optional[SkillDefinition]:
        """从历史记录中获取指定版本"""
        history = self._history.get(name, [])
        for v in history:
            if v.version == version:
                return v.definition
        logger.warning(f"Historical version {version} not found for '{name}', using current")
        return self._skills.get(name, VersionedDefinition()).definition

    def bind(self, name: str, execution_id: str) -> SkillDefinition:
        """绑定当前版本到执行实例"""
        versioned = self._skills.get(name)
        if not versioned:
            raise SkillNotFoundError(name)
        self._active_bindings[execution_id] = versioned.version
        return versioned.definition

    def release(self, execution_id: str):
        """释放绑定"""
        self._active_bindings.pop(execution_id, None)

    def list_by_names(self, names: List[str]) -> List[SkillSummary]:
        """按名称列表获取摘要"""
        return [self._skills[n].to_summary() for n in names if n in self._skills]

    def list_all(self) -> List[SkillSummary]:
        """获取所有已注册 Skill 摘要"""
        return [v.to_summary() for v in self._skills.values()]

    async def replace_all(self, new_skills: Dict[str, SkillDefinition]):
        """原子替换所有定义，保留历史版本"""
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

                # 将旧版本移入历史
                for name, old_def in old_skills.items():
                    if name not in self._history:
                        self._history[name] = []
                    self._history[name].append(old_def)

                    # 清理超出限制的历史版本
                    if len(self._history[name]) > self._max_history:
                        self._history[name] = self._history[name][-self._max_history:]

            except Exception as e:
                self._skills = old_skills
                raise
```

**历史版本流转**：

```
max_history_versions = 3

第一次替换：v1 → v2  历史: [v1]
第二次替换：v2 → v3  历史: [v1, v2]
第三次替换：v3 → v4  历史: [v1, v2, v3]
第四次替换：v4 → v5  历史: [v2, v3, v4]  ← v1 被清理
```

### 9.4 Skill Executor（带累积降级）

```python
class SkillExecutor:
    """Skill 执行器"""

    def __init__(self, workflow_engine, context_builder, mcp_client):
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

        # 构建上下文（六层）
        context = await self.context_builder.build(
            layers=skill_def.context.layers,
            domain=skill_def.domain,
            variables=params,
            token_limit=skill_def.context.token_limit
        )

        # 调用主工作流（带降级）
        return await self._execute_with_degradation(
            skill_def=skill_def,
            workflow_name=skill_def.workflows.main,
            context=context,
            trace_id=trace_id
        )

    async def _execute_with_degradation(
        self,
        skill_def: SkillDefinition,
        workflow_name: str,
        context: WorkflowContext,
        trace_id: str,
        depth: int = 0,
        accumulated_skipped: List[str] = None  # 累积的跳过步骤
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

        # 执行工作流
        wf_result = await self.workflow_engine.execute(
            workflow_name=workflow_name,
            context=context,
            trace_id=trace_id
        )

        # 成功
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

        # 失败，尝试降级
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

        # 累积当前降级跳过的步骤
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
        """匹配降级触发条件"""
        for fallback in policy.fallbacks:
            for condition in fallback.conditions:
                if self._evaluate_condition(condition, error):
                    return fallback
        return None
```

**累积 skipped_steps 示例**：

```
expense_reimbursement (depth=0)
    │ 失败：mcp-finance 不可用
    │ 降级跳过：[risk_analysis]
    ↓
expense_no_risk (depth=1)
    │ 失败：超时
    │ 降级跳过：[create_document]
    ↓
expense_simple (depth=2) → 成功

返回：
SkillResult(
    status="degraded_success",
    degradation_info=DegradationInfo(
        skipped_steps=["risk_analysis", "create_document"],
        fallback_workflow="expense_simple"
    )
)

Agent Loop Reflect：
"任务完成，但跳过了风险评估和单据生成，可能需要人工复核"
```

### 9.5 Skill Loader（加载与校验）

```python
class SkillLoader:
    """Skill 定义加载器"""

    def __init__(self, skills_dir: str, embedding_model):
        self.skills_dir = Path(skills_dir)
        self.embedding_model = embedding_model

    async def load_all(self) -> Dict[str, SkillDefinition]:
        """加载所有 Skill 定义"""
        skills = {}
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
        """加载单个 Skill"""
        # 读取 YAML
        with open(skill_dir / "skill.yaml", 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f)

        skill_def = SkillDefinition.parse(raw)
        skill_def.base_dir = skill_dir

        # 加载上下文模板
        context_dir = skill_dir / "context"
        if context_dir.exists():
            for template_file in context_dir.glob("*.jinja2"):
                layer_name = template_file.stem
                if layer_name in skill_def.context.layers:
                    skill_def.context.layers[layer_name].template_content = \
                        template_file.read_text(encoding='utf-8')

        # 加载提示词
        prompts_dir = skill_dir / "prompts"
        if prompts_dir.exists():
            think_path = prompts_dir / "think.md"
            if think_path.exists():
                skill_def.agent.think_prompt_content = think_path.read_text(encoding='utf-8')
            reflect_path = prompts_dir / "reflect.md"
            if reflect_path.exists():
                skill_def.agent.reflect_prompt_content = reflect_path.read_text(encoding='utf-8')

        # 预计算 Embedding
        if skill_def.intent.embedding_text:
            skill_def.intent.embedding_vector = \
                await self.embedding_model.encode(skill_def.intent.embedding_text)

        return skill_def

    async def reload_changed(self, changed_files: List[str]) -> Dict[str, SkillDefinition]:
        """增量加载变更的 Skill"""
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

**SkillValidator 实现**：

```python
class SkillValidator:
    """Skill 定义校验器"""

    def validate(
        self,
        skill_def: SkillDefinition,
        workflow_registry: Dict[str, Any],
        all_skills: Dict[str, SkillDefinition]
    ) -> List[str]:
        errors = []

        # 必填字段
        if not skill_def.name:
            errors.append("missing 'name'")
        if not skill_def.version:
            errors.append("missing 'version'")
        if not skill_def.workflows.main:
            errors.append("missing 'workflows.main'")

        # workflow 存在性
        if skill_def.workflows.main not in workflow_registry:
            errors.append(f"workflow '{skill_def.workflows.main}' not found")
        for fallback in skill_def.workflows.degradation_policy.fallbacks:
            if fallback.workflow not in workflow_registry:
                errors.append(f"fallback workflow '{fallback.workflow}' not found")

        # 循环依赖检测
        if self._has_circular_dependency(skill_def, all_skills):
            errors.append("circular dependency detected in context_dependencies")

        # 模板文件存在性
        for layer_name, layer_config in skill_def.context.layers.items():
            if layer_config.source:
                template_path = skill_def.base_dir / layer_config.source
                if not template_path.exists():
                    errors.append(f"template not found: {layer_config.source}")

        return errors

    def _has_circular_dependency(
        self,
        skill_def: SkillDefinition,
        all_skills: Dict[str, SkillDefinition]
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

### 9.6 完整调用序列图

```
User Request
    │
    ↓
Agent Loop: Think
    │
    ├── calls → Skill Engine.match(request, context)
    │               │
    │               ├── SkillMatcher._match_intent()
    │               │   ├── keyword_match() → hits
    │               │   └── embedding_match() → hits
    │               │   └── merge → candidates (Top-K)
    │               │
    │               ├── SkillMatcher._evaluate_activation()
    │               │   ├── check_precondition(time_window, role_check, ...)
    │               │   └── check_context_dependency(data-fetch, budget-check, ...)
    │               │
    │               └── returns → [SkillMatch(expense, 0.92), ...]
    │
    ├── decides → activate "expense-reimbursement"
    │
    ↓
Agent Loop: Act
    │
    ├── calls → Skill Engine.execute("expense-reimbursement", params)
    │               │
    │               ├── SkillRegistry.get("expense-reimbursement")
    │               │   └── bind(execution_id) → versioned definition
    │               │
    │               ├── SkillExecutor.execute()
    │               │   │
    │               │   ├── ContextBuilder.build(layers, domain, variables)
    │               │   │   ├── L1_base: system role
    │               │   │   ├── L2_business: expense rules (domain filtered)
    │               │   │   ├── L3_dynamic: user info (append)
    │               │   │   ├── L4_history: previous steps (append)
    │               │   │   ├── L5_tools: available tools (union)
    │               │   │   └── L6_output: JSON format
    │               │   │   └── Token裁剪 → assembled prompt
    │               │   │
    │               │   └── _execute_with_degradation()
    │               │       │
    │               │       ├── WorkflowEngine.execute("expense_reimbursement")
    │               │       │   ├── Step 1: MCP Client (trace_id=abc123)
    │               │       │   ├── Step 2: MCP Client
    │               │       │   ├── Step 3: LLM Reasoning
    │               │       │   └── Step 4-6: ...
    │               │       │
    │               │       └── if failed → match fallback → recursive
    │               │           (accumulated_skipped 累积)
    │               │
    │               └── SkillRegistry.release(execution_id)
    │
    └── returns → SkillResult
    │
    ↓
Agent Loop: Observe → Reflect
    │
    ├── degraded_success → skipped_steps 告知哪些步骤被跳过
    ├── failed + retry_after → 决定等待/降级/升级
    └── success → 记录到 memory
```

---

## 10. Context Builder 详细设计

### 10.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Context Builder                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Template Registry                      │    │
│  │  按 Skill + Layer 索引的 Jinja2 模板存储             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Layer Loaders                          │    │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐│   │
│  │  │  L1  │ │  L2  │ │  L3  │ │  L4  │ │  L5  │ │  L6  ││   │
│  │  │ Base │ │ Busi │ │ Dyna │ │ Hist │ │ Tool │ │ Out  ││   │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘│   │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Jinja2 Renderer                        │    │
│  │  变量解析 → 条件渲染 → 循环展开 → 过滤器              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Merge Engine                           │    │
│  │  按 merge_strategy 合并多层内容                       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Token Trimmer                          │    │
│  │  按优先级裁剪，确保总 Token ≤ limit                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Prompt Assembler                       │    │
│  │  按优先级顺序拼接各层，输出完整 Prompt                 │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 核心数据结构

```python
class LayerType(str, Enum):
    BASE = "L1_base"
    BUSINESS = "L2_business"
    DYNAMIC = "L3_dynamic"
    HISTORY = "L4_history"
    TOOLS = "L5_tools"
    OUTPUT = "L6_output"

class MergeStrategy(str, Enum):
    REPLACE = "replace"    # 覆盖
    APPEND = "append"      # 追加
    UNION = "union"        # 合并去重

class ContextBuildRequest(BaseModel):
    layers_config: Dict[str, LayerConfig]
    domain: str
    variables: Dict[str, Any]
    token_limit: int = 4000
    history: List[Dict[str, Any]] = []
    available_tools: List[Dict[str, Any]] = []
    user_info: Dict[str, Any] = {}
    workflow_context: Optional[Dict[str, Any]] = None
    # 敏感数据脱敏
    mask_sensitive: bool = False
    sensitive_fields: List[str] = ["phone", "id_card", "email", "bank_card"]

class ContextBuildResult(BaseModel):
    prompt: str
    total_tokens: int
    layer_details: List[ContextLayerResult]
    trimmed: bool
    trimmed_layers: List[str] = []
```

### 10.3 各层 Loader 实现

```python
class ContextBuilder:
    """六层上下文构建器"""

    def __init__(self, mcp_client=None):
        self.mcp_client = mcp_client
        self.jinja_env = Environment(undefined=StrictUndefined, autoescape=False)
        self.jinja_env.filters['to_json'] = lambda v: json.dumps(v, ensure_ascii=False)
        self.jinja_env.filters['default_if_none'] = lambda v, d: d if v is None else v

    async def build(self, request: ContextBuildRequest) -> ContextBuildResult:
        layer_results = []

        for layer_type in LayerType:
            config = request.layers_config.get(layer_type.value)
            if not config:
                continue
            result = await self._load_layer(layer_type, config, request)
            if result and result.content.strip():
                layer_results.append(result)

        layer_results.sort(key=lambda r: r.priority)

        # Token 裁剪
        total_tokens = sum(r.token_count for r in layer_results)
        trimmed = False
        trimmed_layers = []

        if total_tokens > request.token_limit:
            layer_results, trimmed_layers = self._trim_layers(
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

**各层加载逻辑**：

```python
async def _load_base(self, config, request) -> str:
    """ℒ₁ 基础层：系统角色、行为边界（静态模板）"""
    if not config.template_content:
        return ""
    template = self.jinja_env.from_string(config.template_content)
    return template.render()

async def _load_business(self, config, request) -> str:
    """ℒ₂ 业务层：业务域规则（域过滤）"""
    if not config.template_content:
        return ""
    template = self.jinja_env.from_string(config.template_content)
    return template.render(domain=request.domain)

async def _load_dynamic(self, config, request) -> str:
    """ℒ₃ 动态层：用户信息（支持敏感数据脱敏）"""
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

async def _load_history(self, config, request) -> str:
    """ℒ₄ 历史层：智能裁剪（保留失败 + 最近成功）"""
    history = request.history or []
    if not history:
        return ""

    # 智能裁剪
    history_token_budget = int(request.token_limit * 0.3)
    trimmer = SmartHistoryTrimmer()
    history = trimmer.trim(history, history_token_budget, self._count_tokens)

    if config.template_content:
        template = self.jinja_env.from_string(config.template_content)
        return template.render(history=history)

    # 自动组装
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

async def _load_tools(self, config, request) -> str:
    """ℒ₅ 工具层：可用工具描述（动态查询）"""
    tools = request.available_tools or []
    if not tools and self.mcp_client and request.domain:
        tools = await self.mcp_client.list_tools(domain=request.domain)
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

async def _load_output(self, config, request) -> str:
    """ℒ₆ 输出格式层：响应格式约束"""
    if not config.template_content:
        return ""
    template = self.jinja_env.from_string(config.template_content)
    return template.render()
```

### 10.4 敏感数据脱敏（可配置规则）

```python
class SensitiveFieldMasker:
    """敏感字段脱敏器（支持自定义规则）"""

    BUILTIN_PATTERNS = {
        "phone": (r'(\d{3})\d{4}(\d{4})', r'\1****\2'),
        "id_card": (r'(\d{6})\d{8}(\d{4})', r'\1********\2'),
        "email": (r'(.{2}).+(@.+)', r'\1***\2'),
        "bank_card": (r'(\d{4})\d+(\d{4})', r'\1 **** **** \2'),
    }

    def __init__(
        self,
        fields_to_mask: List[str] = None,
        custom_patterns: Dict[str, tuple] = None,
        pattern_config_path: str = None
    ):
        self.fields_to_mask = fields_to_mask or []
        self.patterns = dict(self.BUILTIN_PATTERNS)

        if custom_patterns:
            self.patterns.update(custom_patterns)

        if pattern_config_path:
            self._load_from_config(pattern_config_path)

    def _load_from_config(self, config_path: str):
        """从配置文件加载脱敏规则"""
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
        if len(value) > 6:
            return value[:2] + "*" * (len(value) - 4) + value[-2:]
        return "***"
```

**配置文件 `masking_rules.yaml`**：

```yaml
masking_rules:
  - name: phone
    regex: '(\d{3})\d{4}(\d{4})'
    replacement: '\1****\2'
  - name: salary
    regex: '(\d+).*'
    replacement: '***'
  - name: address
    regex: '(.{3}).+'
    replacement: '\1***'
```

**Skill 定义中引用**：

```yaml
context:
  masking:
    enabled: true
    fields: [phone, id_card, salary]
    config_path: ./config/masking_rules.yaml
    custom_patterns:
      employee_code:
        regex: '^(EMP)(\d+)$'
        replacement: 'EMP***'
```

### 10.5 智能历史裁剪

```python
class SmartHistoryTrimmer:
    """智能历史裁剪器"""

    STATUS_PRIORITY = {
        "FAILED": 0,     # 最高优先级：失败必须保留
        "SKIPPED": 1,    # 次优先：跳过（含条件判断信息）
        "COMPLETED": 2,  # 最低优先：成功可丢弃
    }

    def trim(
        self,
        history: List[Dict[str, Any]],
        max_tokens: int,
        count_tokens_fn: callable
    ) -> List[Dict[str, Any]]:
        current_tokens = count_tokens_fn(self._format_history(history))
        if current_tokens <= max_tokens:
            return history
        return self._prioritize_and_trim(history, max_tokens, count_tokens_fn)

    def _prioritize_and_trim(self, history, max_tokens, count_tokens_fn):
        # 分组
        failed_skipped = [h for h in history if h.get("status") in ("FAILED", "SKIPPED")]
        completed = [h for h in history if h.get("status") == "COMPLETED"]

        # 失败/跳过全部保留
        kept = list(failed_skipped)

        # 成功步骤从最近的开始保留
        remaining_tokens = max_tokens - count_tokens_fn(self._format_history(kept))
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
```

**裁剪示例**：

```
原始（10 步，token 超限）：
✓ verify_employee    ✓ validate_budget    ✗ risk_analysis (保留)
✓ create_document    ✓ submit_approval    ✓ send_notification
✓ update_records     ✓ sync_accounting    ✗ audit_check (保留)
✓ generate_report

裁剪后：
✓ verify_employee    ✗ risk_analysis     ✗ audit_check     ✓ generate_report
(最早的步骤)         (失败，必须保留)     (失败，必须保留)    (最近的成功)
```

### 10.6 Token 裁剪策略

```python
def _trim_layers(self, layers, token_limit):
    """按优先级从低到高裁剪"""
    trimmed_names = []
    remaining = token_limit

    # 从低优先级（priority 数字大）到高优先级排序
    sorted_layers = sorted(layers, key=lambda r: r.priority, reverse=True)

    kept = []
    for layer in sorted_layers:
        if remaining >= layer.token_count:
            remaining -= layer.token_count
            kept.append(layer)
        else:
            if remaining > 100:
                truncated = self._truncate_to_tokens(layer.content, remaining)
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

**裁剪顺序**：L6 → L5 → L4 → L3 → L2 → L1（优先级从低到高）

### 10.7 Merge Engine

```python
class MergeEngine:
    """多层内容合并引擎"""

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
        merged = list(existing_lines)
        for line in new.split('\n'):
            if line.strip() and line.strip() not in existing_lines:
                merged.append(line)
        return '\n'.join(merged)
```

---

## 11. Agent Loop ReAct 详细设计

### 11.1 ReAct 循环结构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Loop (ReAct)                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Think                             │    │
│  │  输入：用户请求 + memory + scratch_pad               │    │
│  │  输出：Thought（action_type, skill_name, params）    │    │
│  │  调用：SkillEngine.match() → 选择 Skill             │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↓                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Act                               │    │
│  │  输入：Thought                                      │    │
│  │  输出：ActionResult（status, data, degradation_info）│    │
│  │  调用：SkillEngine.execute()                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↓                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Observe                           │    │
│  │  输入：ActionResult                                  │    │
│  │  输出：Observation（结构化的执行结果）                │    │
│  │  处理：degraded_success → 标记降级信息               │    │
│  │        failed + retry_after → 记录等待时间           │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↓                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Reflect                           │    │
│  │  输入：Observation + memory                          │    │
│  │  输出：Reflection（should_stop, result, next_action）│    │
│  │  决策：完成 / 重试 / 降级 / 升级 / 继续              │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↓                                   │
│              ┌──────────┴──────────┐                        │
│              │ should_stop?         │                        │
│              └──────────┬──────────┘                        │
│                yes ↓          ↓ no                          │
│            ┌──────────┐  ┌──────────┐                       │
│            │ 返回结果  │  │ 继续循环  │                       │
│            └──────────┘  └────┬─────┘                       │
│                               └──→ Think (next iteration)   │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 核心数据结构

```python
class Thought(BaseModel):
    """Think 阶段输出"""
    reasoning: str
    action_type: Literal["skill", "tool", "respond", "clarify"]
    skill_name: Optional[str] = None
    tool_name: Optional[str] = None
    action: Optional[str] = None
    params: Dict[str, Any] = {}
    confidence: float = 0.0
    response_text: Optional[str] = None

class ActionResult(BaseModel):
    """Act 阶段输出"""
    status: Literal["success", "degraded_success", "failed"]
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    error_type: Optional[str] = None
    retry_after: Optional[float] = None
    degradation_info: Optional[DegradationInfo] = None

class Observation(BaseModel):
    """Observe 阶段输出"""
    status: str
    data_summary: str
    key_findings: List[str] = []
    is_degraded: bool = False
    degradation_summary: Optional[str] = None
    error_summary: Optional[str] = None

class Reflection(BaseModel):
    """Reflect 阶段输出"""
    should_stop: bool
    result: Optional[TaskResult] = None
    next_action: Optional[str] = None
    reason: str
    update_memory: List[str] = []
    update_scratch_pad: Dict[str, Any] = {}

class TaskResult(BaseModel):
    """任务最终结果"""
    status: Literal["completed", "partial", "failed", "escalated"]
    data: Dict[str, Any] = {}
    message: str = ""
    degradation_info: Optional[DegradationInfo] = None
    total_iterations: int = 0
    trace_id: str = ""
```

### 11.3 Agent Loop 核心实现

```python
class AgentLoop:
    """Agent Loop - ReAct 循环"""

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
        """主循环"""
        self.trace_id = uuid.uuid4().hex[:16]
        self.state.task_stack.append(TaskFrame(task=task, context=context or {}))

        for iteration in range(self.config.max_iterations):
            # Think
            thought = await self._think(task, context)

            if thought.action_type == "respond":
                return TaskResult(status="completed", message=thought.response_text,
                                  total_iterations=iteration + 1, trace_id=self.trace_id)

            if thought.action_type == "clarify":
                return TaskResult(status="completed", message=thought.response_text,
                                  data={"clarification_needed": True},
                                  total_iterations=iteration + 1, trace_id=self.trace_id)

            # Act
            action_result = await self._act(thought)

            # Observe
            observation = await self._observe(action_result)

            # Reflect
            reflection = await self._reflect(observation, thought)

            self._update_state(reflection)

            if reflection.should_stop:
                return reflection.result

            if iteration % self.config.checkpoint_interval == 0:
                await self._checkpoint()

        return TaskResult(status="failed", message="超过最大迭代次数",
                          total_iterations=self.config.max_iterations, trace_id=self.trace_id)
```

### 11.4 Think 阶段：调用 SkillEngine.match()

```python
async def _think(self, task: str, context: Dict[str, Any]) -> Thought:
    # 1. 获取候选 Skill
    matches = await self.skill_engine.match(
        request=task, context=context, agent_skill_set=self.skill_set
    )

    # 2. 构建提示词
    prompt = self._build_think_prompt(task, context, matches)

    # 3. 调用 LLM
    response = await self.llm_client.complete(
        system=self.config.think_system_prompt,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    thought = Thought.parse(response)

    # 4. 校验 Skill 选择
    if thought.action_type == "skill" and thought.skill_name:
        available = [m.skill_name for m in matches]
        if thought.skill_name not in available:
            if matches:
                thought.skill_name = matches[0].skill_name
            else:
                thought.action_type = "respond"
                thought.response_text = "抱歉，我无法处理这个请求。"

    return thought

def _build_think_prompt(self, task, context, matches) -> str:
    skill_list = ""
    if matches:
        for i, m in enumerate(matches, 1):
            skill_list += f"### {i}. {m.skill_name} (置信度: {m.confidence:.2f})\n"
            skill_list += self._format_activation_details(m) + "\n"
    else:
        skill_list = "无匹配的 Skill\n"

    return f"""
## 任务
{task}

## 可用 Skill 及激活状态
{skill_list}

## 上下文
{json.dumps(context, ensure_ascii=False, indent=2) if context else "无"}

## 历史记忆
{chr(10).join(f'- {m}' for m in self.state.memory[-5:]) or "无"}

## 指令
分析任务和 Skill 激活状态，选择最合适的行动。

**决策规则**：
1. 优先选择激活状态为 ✓ 的 Skill
2. 如果最佳 Skill 有未满足的依赖，先执行前置 Skill
3. 如果没有匹配的 Skill，直接回复或请求澄清

返回 JSON：
{{
    "reasoning": "推理过程",
    "action_type": "skill | tool | respond | clarify",
    "skill_name": "选择的 Skill 名称",
    "params": {{}},
    "confidence": 0.0~1.0
}}
"""

def _format_activation_details(self, match: SkillMatch) -> str:
    lines = []
    rules = match.matched_rules
    if not rules:
        lines.append("  激活状态: ✓ (无激活规则)")
        return "\n".join(lines)

    all_passed = rules.get("all_passed", True)
    lines.append(f"  激活状态: {'✓' if all_passed else '✗'}")

    # Preconditions
    preconditions = rules.get("preconditions", {})
    if preconditions:
        lines.append("  前提条件:")
        for cond_type, passed in preconditions.items():
            lines.append(f"    {'✓' if passed else '✗'} {cond_type}: {'通过' if passed else '未通过'}")

    # Dependencies
    dependencies = rules.get("dependencies", {})
    if dependencies:
        lines.append("  上下文依赖:")
        for dep_name, passed in dependencies.items():
            dep_info = rules.get("dependency_details", {}).get(dep_name, {})
            required = dep_info.get("required", True)
            fallback = dep_info.get("fallback_value")

            detail = "已满足" if passed else "未满足"
            if not passed:
                if required:
                    detail += " (必需 → 必须先执行此依赖)"
                elif fallback:
                    detail += " (可选 → 将使用默认值)"
                else:
                    detail += " (可选 → 可跳过)"
            lines.append(f"    {'✓' if passed else '✗'} {dep_name}: {detail}")

    # 未满足的必需依赖
    unsatisfied = [
        name for name, passed in dependencies.items()
        if not passed and rules.get("dependency_details", {}).get(name, {}).get("required", True)
    ]
    if unsatisfied:
        lines.append(f"  ⚠ 需要先执行: {', '.join(unsatisfied)}")

    return "\n".join(lines)
```

### 11.5 Act 阶段

```python
async def _act(self, thought: Thought) -> ActionResult:
    if thought.action_type == "skill":
        result = await self.skill_engine.execute(
            skill_name=thought.skill_name,
            params=thought.params,
            trace_id=self.trace_id
        )
        return ActionResult(
            status=result.status, data=result.data,
            degradation_info=result.degradation_info
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
```

### 11.6 Observe 阶段

```python
async def _observe(self, result: ActionResult) -> Observation:
    key_findings = []
    is_degraded = False
    degradation_summary = None
    error_summary = None

    if result.status == "degraded_success":
        is_degraded = True
        deg = result.degradation_info
        if deg:
            degradation_summary = (
                f"通过降级路径完成（{deg.fallback_workflow}），"
                f"跳过步骤：{', '.join(deg.skipped_steps) if deg.skipped_steps else '无'}"
            )
            key_findings.append(f"降级完成: {deg.fallback_workflow}")

    elif result.status == "failed":
        error_summary = f"执行失败: {result.error}"
        if result.retry_after:
            error_summary += f"（建议 {result.retry_after:.0f} 秒后重试）"
        key_findings.append(f"失败: {result.error_type}")

    else:
        for key, value in result.data.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    key_findings.append(f"{key}.{k} = {v}")
            else:
                key_findings.append(f"{key} = {value}")

    return Observation(
        status=result.status,
        data_summary=json.dumps(result.data, ensure_ascii=False)[:500],
        key_findings=key_findings[:10],
        is_degraded=is_degraded,
        degradation_summary=degradation_summary,
        error_summary=error_summary
    )
```

### 11.7 Reflect 阶段

```python
async def _reflect(self, observation: Observation, thought: Thought) -> Reflection:
    prompt = f"""
## 执行结果
状态: {observation.status}
关键发现:
{chr(10).join(f'- {f}' for f in observation.key_findings)}

{"降级信息: " + observation.degradation_summary if observation.is_degraded else ""}
{"错误信息: " + observation.error_summary if observation.error_summary else ""}

## 执行的行动
类型: {thought.action_type}
Skill: {thought.skill_name or "N/A"}
推理: {thought.reasoning}

## 指令
根据执行结果，决定下一步。返回 JSON：
{{
    "should_stop": true/false,
    "result": {{"status": "...", "message": "..."}},
    "next_action": "下一步描述",
    "reason": "决策理由",
    "update_memory": ["要记录的内容"],
    "update_scratch_pad": {{"key": "value"}}
}}
"""

    response = await self.llm_client.complete(
        system=self.config.reflect_system_prompt,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    reflection = Reflection.parse(response)

    # 自动构造结果
    if reflection.should_stop and not reflection.result:
        if observation.status == "success":
            reflection.result = TaskResult(status="completed", message="任务完成",
                                            data=observation.data_summary, trace_id=self.trace_id)
        elif observation.is_degraded:
            reflection.result = TaskResult(status="partial",
                                            message=f"部分完成：{observation.degradation_summary}",
                                            trace_id=self.trace_id)
        else:
            reflection.result = TaskResult(status="failed",
                                            message=observation.error_summary or "任务失败",
                                            trace_id=self.trace_id)

    return reflection
```

### 11.8 完整调用序列示例

```
用户请求："我要申请差旅报销3500元"
    │
    ↓
Iteration 1: Think
    ├── SkillEngine.match("我要申请差旅报销3500元")
    │   └── expense-reimbursement (0.92)
    │       激活状态: ✗
    │       前提条件: ✓ time_window, ✓ role_check, ✓ feature_flag
    │       上下文依赖: ✗ data-fetch (必需 → 必须先执行)
    │       ⚠ 需要先执行: data-fetch
    │
    └── Thought: action_type="skill", skill_name="data-fetch"
    │
    ↓
Iteration 1: Act → Observe → Reflect
    ├── data-fetch 成功，更新 scratch_pad
    └── should_stop=false → 继续
    │
    ↓
Iteration 2: Think
    ├── SkillEngine.match("我要申请差旅报销3500元")
    │   └── expense-reimbursement (0.92)
    │       激活状态: ✓ (所有规则通过)
    │
    └── Thought: action_type="skill", skill_name="expense-reimbursement"
    │
    ↓
Iteration 2: Act
    ├── SkillEngine.execute("expense-reimbursement")
    │   ├── ContextBuilder.build() → 六层上下文
    │   └── WorkflowEngine.execute()
    │       ├── Step 1: mcp-hr/verify_employee ✓
    │       ├── Step 2: mcp-finance/validate_expense ✓
    │       ├── Step 3: llm_reasoning (risk) ✓
    │       ├── Step 4: mcp-document/create_form ✓
    │       ├── Step 5: mcp-workflow/create_approval ✓
    │       └── Step 6: llm_reasoning (summary) ✓
    │
    ↓
Iteration 2: Observe → Reflect
    └── should_stop=true → TaskResult(status="completed")
    │
    ↓
返回: "您的3500元差旅报销申请已成功提交..."
```

---

## 12. 技术选型

| 组件 | 技术方案 |
|------|----------|
| Agent Core 服务 | Python + FastAPI |
| LLM 调用 | Anthropic SDK（Claude） |
| 状态热缓存 | Redis |
| 状态持久化 | MySQL |
| 文件监听 | watchdog |
| 配置格式 | YAML + Jinja2 模板 |
| 日志追踪 | trace_id 贯穿 + 结构化日志 |

---

## 13. 项目工程结构

```
agent-core/
├── app/
│   ├── main.py                        # FastAPI 入口
│   │
│   ├── core/                          # 通用基础类（避免循环引用）
│   │   ├── __init__.py
│   │   ├── config.py                  # 配置加载（YAML + 环境变量覆盖）
│   │   ├── database.py                # MySQL 连接池
│   │   ├── cache.py                   # Redis 连接管理
│   │   ├── llm_client.py              # LLM API 封装（Anthropic/OpenAI）
│   │   ├── embedding_client.py        # Embedding 模型 API 封装
│   │   ├── trace.py                   # TraceContext（trace_id 全链路注入）
│   │   └── exceptions.py             # 统一异常体系
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── loop.py                    # AgentLoop (ReAct)
│   │   ├── state.py                   # AgentState, StateStore
│   │   ├── pool.py                    # AgentLoopPool（多实例管理）
│   │   └── models.py                  # Thought, ActionResult, Observation, Reflection
│   │
│   ├── skill/
│   │   ├── __init__.py
│   │   ├── engine.py                  # SkillEngine（Agent 唯一入口）
│   │   ├── registry.py                # SkillRegistry（版本管理）
│   │   ├── matcher.py                 # SkillMatcher（两级匹配）
│   │   ├── executor.py                # SkillExecutor（降级递归）
│   │   ├── loader.py                  # SkillLoader（YAML + 模板加载）
│   │   └── validator.py              # SkillValidator（校验）
│   │
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── engine.py                  # WorkflowEngine
│   │   ├── models.py                  # WorkflowDefinition, WorkflowStep
│   │   └── context.py                 # WorkflowContext, ContextManager
│   │
│   ├── context/
│   │   ├── __init__.py
│   │   ├── builder.py                 # ContextBuilder
│   │   ├── loaders.py                 # L1-L6 LayerLoaders
│   │   ├── trimmer.py                 # SmartHistoryTrimmer, TokenTrimmer
│   │   ├── merger.py                  # MergeEngine
│   │   └── masker.py                  # SensitiveFieldMasker
│   │
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── client.py                  # MCPClientLayer（统一入口）
│   │   ├── pool.py                    # ConnectionPool
│   │   ├── auth.py                    # AuthManager
│   │   ├── retry.py                   # RetryController
│   │   ├── circuit_breaker.py         # CircuitBreaker
│   │   └── discovery.py              # ToolDiscoveryClient
│   │
│   ├── reload/
│   │   ├── __init__.py
│   │   ├── manager.py                 # HotReloadManager
│   │   └── watcher.py                # FileWatcher (watchdog)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── agent.py                   # Agent REST API
│   │   ├── admin.py                   # Admin API（鉴权保护）
│   │   ├── ws.py                      # WebSocket 实时推送
│   │   └── health.py                  # 健康检查
│   │
│   └── monitoring/
│       ├── __init__.py
│       ├── metrics.py                 # Prometheus 指标
│       └── logger.py                  # 结构化日志（trace_id 注入）
│
├── skills/                            # Skill 定义目录
│   ├── expense-reimbursement/
│   │   ├── skill.yaml
│   │   ├── context/
│   │   └── prompts/
│   └── leave-request/
│       ├── skill.yaml
│       ├── context/
│       └── prompts/
│
├── workflows/                         # Workflow 定义目录
│   ├── expense-reimbursement.yaml
│   ├── expense-no-risk.yaml
│   └── common/
│       ├── verify-employee.yaml
│       └── budget-check.yaml
│
├── config/
│   ├── settings.yaml                  # 主配置
│   ├── settings.test.yaml             # 测试环境覆盖
│   ├── settings.prod.yaml             # 生产环境覆盖
│   └── masking_rules.yaml             # 脱敏规则
│
├── tests/
│   ├── conftest.py                    # 公共 fixture
│   ├── unit/
│   │   ├── test_context_builder.py
│   │   ├── test_skill_matcher.py
│   │   ├── test_skill_registry.py
│   │   ├── test_workflow_engine.py
│   │   ├── test_circuit_breaker.py
│   │   ├── test_smart_trimmer.py      # 参数化边界测试
│   │   └── test_sensitive_masker.py   # 参数化脱敏测试
│   ├── integration/
│   │   ├── test_skill_to_workflow.py
│   │   ├── test_agent_loop_react.py
│   │   ├── test_degradation_chain.py
│   │   ├── test_circuit_breaker_degradation.py  # 熔断触发降级
│   │   └── test_hot_reload.py
│   └── e2e/
│       └── test_expense_flow.py
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

**core/ 目录职责**：

| 文件 | 职责 | 被引用方 |
|------|------|----------|
| `config.py` | 加载 YAML 配置，支持环境变量覆盖 | 所有模块 |
| `database.py` | MySQL 连接池（asyncmy） | StateStore, ContextManager |
| `cache.py` | Redis 连接管理 | StateStore, ToolDiscovery |
| `llm_client.py` | LLM API 封装（重试、超时、token 计数） | AgentLoop, ContextBuilder |
| `embedding_client.py` | Embedding API 封装 | SkillMatcher |
| `trace.py` | TraceContext（trace_id 全链路注入） | 所有模块 |
| `exceptions.py` | 统一异常体系 | 所有模块 |

---

## 14. API 接口层

### 14.1 Agent REST API

```python
# app/api/agent.py
from fastapi import APIRouter, BackgroundTasks, HTTPException

router = APIRouter(prefix="/api/v1/agents")

@router.post("/{agent_id}/tasks")
async def create_task(
    agent_id: str,
    request: TaskRequest,
    background_tasks: BackgroundTasks
):
    """提交任务给 Agent"""
    agent = agent_pool.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    task_id = uuid.uuid4().hex
    background_tasks.add_task(agent.run, request.task, request.context)
    return {"task_id": task_id, "status": "accepted"}

@router.get("/{agent_id}/tasks/{task_id}")
async def get_task_status(agent_id: str, task_id: str):
    """查询任务状态"""
    result = await state_store.get_task_result(agent_id, task_id)
    if not result:
        raise HTTPException(404, "Task not found")
    return result

@router.get("/{agent_id}/state")
async def get_agent_state(agent_id: str):
    """获取 Agent 状态"""
    agent = agent_pool.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return agent.state.model_dump()

@router.post("/{agent_id}/pause")
async def pause_agent(agent_id: str):
    """暂停 Agent"""
    agent = agent_pool.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    await agent.pause()
    return {"status": "paused"}

@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str):
    """恢复 Agent"""
    agent = agent_pool.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    await agent.resume()
    return {"status": "resumed"}
```

### 14.2 WebSocket 实时推送

```python
# app/api/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio

router = APIRouter()

@router.websocket("/ws/{agent_id}/stream")
async def agent_stream(websocket: WebSocket, agent_id: str):
    """实时推送 Agent 执行过程"""
    await websocket.accept()

    agent = agent_pool.get(agent_id)
    if not agent:
        await websocket.close(code=4004, reason="Agent not found")
        return

    try:
        # 注册事件监听
        async for event in agent.event_stream():
            await websocket.send_json({
                "type": event.type,          # think | act | observe | reflect
                "iteration": event.iteration,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
                "trace_id": event.trace_id
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
```

**事件类型**：

| type | 触发时机 | data 内容 |
|------|----------|-----------|
| `think_start` | Think 阶段开始 | `{task, context}` |
| `think_end` | Think 阶段结束 | `{action_type, skill_name, reasoning, confidence}` |
| `act_start` | Act 阶段开始 | `{action_type, skill_name}` |
| `act_end` | Act 阶段结束 | `{status, data_summary, degradation_info}` |
| `observe` | Observe 阶段 | `{status, key_findings, is_degraded}` |
| `reflect` | Reflect 阶段 | `{should_stop, reason, next_action}` |
| `checkpoint` | 状态持久化 | `{step_index, timestamp}` |
| `error` | 异常 | `{error_type, message}` |

### 14.3 Admin API（鉴权保护）

```python
# app/api/admin.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader

router = APIRouter(prefix="/api/v1/admin")

api_key_header = APIKeyHeader(name="X-Admin-Key")

async def verify_admin_key(key: str = Depends(api_key_header)):
    """Admin API 鉴权"""
    if key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin API key")

@router.post("/reload/skills", dependencies=[Depends(verify_admin_key)])
async def reload_skills(request: ReloadRequest):
    """重新加载 Skill 定义"""
    result = await hot_reload_manager.reload_skills(request.files)
    return {"success": result.success, "count": result.count, "errors": result.errors}

@router.post("/reload/workflows", dependencies=[Depends(verify_admin_key)])
async def reload_workflows(request: ReloadRequest):
    """重新加载 Workflow 定义"""
    result = await hot_reload_manager.reload_workflows(request.files)
    return {"success": result.success, "count": result.count}

@router.post("/reload/all", dependencies=[Depends(verify_admin_key)])
async def reload_all():
    """全量重载"""
    wf = await hot_reload_manager.reload_workflows()
    sk = await hot_reload_manager.reload_skills()
    return {"workflows": {"success": wf.success, "count": wf.count},
            "skills": {"success": sk.success, "count": sk.count}}

@router.get("/agents", dependencies=[Depends(verify_admin_key)])
async def list_agents():
    return agent_pool.list_all()

@router.get("/skills", dependencies=[Depends(verify_admin_key)])
async def list_skills():
    return [s.model_dump() for s in skill_engine.registry.list_all()]

@router.get("/workflows", dependencies=[Depends(verify_admin_key)])
async def list_workflows():
    return [w.model_dump() for w in workflow_engine.list_all()]
```

### 14.4 健康检查

```python
# app/api/health.py
router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@router.get("/health/detailed")
async def detailed_health():
    return {
        "status": "healthy",
        "components": {
            "mysql": await check_mysql(),
            "redis": await check_redis(),
            "mcp_discovery": await check_mcp_discovery(),
            "llm_api": await check_llm_api()
        },
        "metrics": {
            "active_agents": agent_pool.active_count(),
            "registered_skills": skill_engine.registry.count(),
            "active_workflows": workflow_engine.active_count()
        }
    }
```

---

## 15. 统一异常体系

```python
# app/core/exceptions.py
from typing import Dict, Any, Optional

class AgentCoreError(Exception):
    """基础异常"""
    error_type: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str, details: Dict[str, Any] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

class SkillNotFoundError(AgentCoreError):
    error_type = "skill_not_found"
    status_code = 404

class WorkflowNotFoundError(AgentCoreError):
    error_type = "workflow_not_found"
    status_code = 404

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

# 全局异常处理器
@app.exception_handler(AgentCoreError)
async def handle_agent_error(request, exc: AgentCoreError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_type,
            "message": exc.message,
            "details": exc.details,
            "trace_id": TraceContext.get_trace_id()
        }
    )
```

**details 字段示例**：

```json
{
    "error": "max_degradation_depth",
    "message": "Max degradation depth (2) exceeded for workflow 'expense_reimbursement'",
    "details": {
        "workflow_name": "expense_reimbursement",
        "depth": 2,
        "skipped_steps": ["risk_analysis", "create_document"]
    },
    "trace_id": "abc123def456"
}
```

---

## 16. TraceContext 全链路追踪

```python
# app/core/trace.py
from contextvars import ContextVar
import uuid

# 全局 trace 上下文变量
_trace_id: ContextVar[str] = ContextVar('trace_id', default='')

class TraceContext:
    """trace_id 全链路注入"""

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
        """获取当前 trace_id，不存在则生成"""
        tid = _trace_id.get()
        if not tid:
            tid = TraceContext.generate_trace_id()
            _trace_id.set(tid)
        return tid
```

**日志中自动注入 trace_id**：

```python
# app/monitoring/logger.py
import logging
from app.core.trace import TraceContext

class TraceFilter(logging.Filter):
    """日志过滤器：自动注入 trace_id"""

    def filter(self, record):
        record.trace_id = TraceContext.get_trace_id()
        return True

# 配置结构化日志
def setup_logging():
    handler = logging.StreamHandler()
    handler.addFilter(TraceFilter())
    formatter = logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s",'
        '"trace_id":"%(trace_id)s","module":"%(module)s","message":"%(message)s"}'
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
```

**指标中注入 trace_id**：

```python
# app/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge
from app.core.trace import TraceContext

# Agent 指标
agent_iterations = Counter(
    'agent_iterations_total', 'Agent loop iterations',
    ['agent_id', 'status', 'trace_id']
)
agent_task_duration = Histogram(
    'agent_task_duration_seconds', 'Task execution time',
    ['trace_id']
)

# 在记录指标时自动注入
def record_metric(counter, **labels):
    labels['trace_id'] = TraceContext.get_trace_id()
    counter.labels(**labels).inc()
```

**FastAPI 中间件注入**：

```python
# app/main.py
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.trace import TraceContext

class TraceMiddleware(BaseHTTPMiddleware):
    """请求级 trace_id 注入"""

    async def dispatch(self, request, call_next):
        # 从 Header 获取或生成
        trace_id = request.headers.get("X-Trace-Id") or TraceContext.generate_trace_id()
        TraceContext.set_trace_id(trace_id)

        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

app.add_middleware(TraceMiddleware)
```

---

## 17. 测试策略

### 17.1 参数化单元测试

```python
# tests/unit/test_smart_trimmer.py
import pytest
from app.context.trimmer import SmartHistoryTrimmer

class TestSmartHistoryTrimmer:

    @pytest.fixture
    def trimmer(self):
        return SmartHistoryTrimmer()

    @pytest.fixture
    def count_fn(self):
        # 简化：每步约 10 token
        return lambda text: len(text) // 10

    @pytest.mark.parametrize("history, max_tokens, expected_kept", [
        # 全部保留（未超限）
        (
            [{"step": "a", "status": "COMPLETED"}],
            1000,
            [{"step": "a", "status": "COMPLETED"}]
        ),
        # 保留失败步骤
        (
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "FAILED"},
                {"step": "c", "status": "COMPLETED"},
            ],
            20,  # 只够保留 2 步
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "FAILED"},
            ]
        ),
        # 失败全部保留 + 最近成功
        (
            [
                {"step": "a", "status": "COMPLETED"},
                {"step": "b", "status": "FAILED"},
                {"step": "c", "status": "COMPLETED"},
                {"step": "d", "status": "COMPLETED"},
                {"step": "e", "status": "FAILED"},
            ],
            35,  # 约 3 步
            [
                {"step": "b", "status": "FAILED"},
                {"step": "e", "status": "FAILED"},
                {"step": "d", "status": "COMPLETED"},
            ]
        ),
        # 空历史
        ([], 1000, []),
        # 全部失败
        (
            [
                {"step": "a", "status": "FAILED"},
                {"step": "b", "status": "FAILED"},
            ],
            10,
            [{"step": "a", "status": "FAILED"}, {"step": "b", "status": "FAILED"}]
        ),
    ])
    def test_trim(self, trimmer, count_fn, history, max_tokens, expected_kept):
        result = trimmer.trim(history, max_tokens, count_fn)
        # 验证保留的步骤名称
        assert [s["step"] for s in result] == [s["step"] for s in expected_kept]
```

```python
# tests/unit/test_sensitive_masker.py
import pytest
from app.context.masker import SensitiveFieldMasker

class TestSensitiveFieldMasker:

    @pytest.mark.parametrize("field, value, expected_pattern", [
        ("phone", "13812345678", "138****5678"),
        ("id_card", "110101199001011234", "110101********1234"),
        ("email", "zhangsan@company.com", "zh***@company.com"),
        ("bank_card", "6222021234567890123", "6222 **** **** 0123"),
        ("name", "张三", "张三"),  # 不在脱敏字段中
        ("salary", "25000", "***"),  # 默认脱敏
    ])
    def test_builtin_masking(self, field, value, expected_pattern):
        masker = SensitiveFieldMasker(fields_to_mask=[field])
        result = masker.mask({field: value})
        if expected_pattern == value:
            assert result[field] == value  # 不脱敏
        else:
            assert result[field] == expected_pattern

    def test_custom_pattern(self):
        masker = SensitiveFieldMasker(
            fields_to_mask=["employee_code"],
            custom_patterns={"employee_code": (r'^(EMP)(\d+)$', r'EMP***')}
        )
        result = masker.mask({"employee_code": "EMP001"})
        assert result["employee_code"] == "EMP***"

    def test_non_string_value(self):
        masker = SensitiveFieldMasker(fields_to_mask=["age"])
        result = masker.mask({"age": 25})
        assert result["age"] == 25  # 非字符串不脱敏
```

### 17.2 集成测试：熔断触发降级

```python
# tests/integration/test_circuit_breaker_degradation.py
import pytest
from unittest.mock import AsyncMock, patch

class TestCircuitBreakerDegradation:

    @pytest.mark.asyncio
    async def test_circuit_open_triggers_degradation(
        self, skill_engine, workflow_engine, mcp_client
    ):
        """熔断器打开后自动触发降级路径"""

        # 模拟 mcp-finance 连续失败 5 次（触发熔断）
        for _ in range(5):
            mcp_client.call_tool = AsyncMock(
                side_effect=CircuitOpenError("mcp-finance", retry_after=60)
            )

        # 执行 Skill
        result = await skill_engine.execute(
            skill_name="expense-reimbursement",
            params={"amount": 3500, "user_id": "E001"}
        )

        # 验证降级成功
        assert result.status == "degraded_success"
        assert result.degradation_info is not None
        assert result.degradation_info.fallback_workflow != "expense_reimbursement"
        assert len(result.degradation_info.skipped_steps) > 0

    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self, mcp_client):
        """熔断器半开状态恢复"""

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)

        # 触发熔断
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"

        # 等待恢复超时
        import asyncio
        await asyncio.sleep(0.15)

        # 探测成功
        cb.record_success()
        assert cb.state == "closed"
```

---

## 18. 配置管理

```yaml
# config/settings.yaml
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
    api_url: "${EMBEDDING_API_URL}"       # 独立 Embedding 服务
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

**测试环境覆盖**：

```yaml
# config/settings.test.yaml
agent:
  max_iterations: 3
  checkpoint_interval: 1

skill:
  embedding:
    api_url: "http://localhost:8081/embed"  # 本地 mock
    api_key: "test-key"

mysql:
  host: localhost
  database: agent_core_test
  password: "test"

redis:
  db: 1  # 使用不同 db 隔离

logging:
  level: DEBUG
```

---

## 19. 监控与可观测性

```python
# app/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Agent 指标
agent_iterations = Counter(
    'agent_iterations_total', 'Agent loop iterations',
    ['agent_id', 'status', 'trace_id']
)
agent_task_duration = Histogram(
    'agent_task_duration_seconds', 'Task execution time'
)
active_agents = Gauge(
    'active_agents', 'Number of active agents'
)

# Skill 指标
skill_executions = Counter(
    'skill_executions_total', 'Skill executions',
    ['skill_name', 'status']
)
skill_duration = Histogram(
    'skill_duration_seconds', 'Skill execution time',
    ['skill_name']
)

# Workflow 指标
workflow_step_duration = Histogram(
    'workflow_step_duration_seconds', 'Step execution time',
    ['step_type']
)
workflow_degradations = Counter(
    'workflow_degradations_total', 'Degradation events',
    ['workflow_name', 'fallback_workflow']
)

# MCP 指标
mcp_call_duration = Histogram(
    'mcp_call_duration_seconds', 'MCP tool call time',
    ['tool_name', 'action']
)
mcp_circuit_state = Gauge(
    'mcp_circuit_state', 'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['tool_name']
)
mcp_call_errors = Counter(
    'mcp_call_errors_total', 'MCP call errors',
    ['tool_name', 'error_type']
)
```

---

*文档版本: v1.1*
*设计日期: 2026-05-29*
*更新: 补充工程结构、API 层、异常体系、TraceContext、测试策略、配置管理、监控*
