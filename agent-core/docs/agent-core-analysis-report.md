# Agent Core 系统架构与运行模式分析报告

**日期**: 2026-06-05
**版本**: v1.0
**分析对象**: [agent-core/](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core)

---

## 1. 整体架构逻辑分析报告

### 1.1 架构分层
基于设计文档与源码实现，`agent-core` 采用了典型的“顶层控制循环 + 领域能力插件 + 基础设施保障”的分层架构：

- **入口层 (Gateway/API)**: 基于 FastAPI 实现，负责路由分发、`trace_id` 注入及全局异常捕获。目前已定义 REST 和 WebSocket 接口，但部分调度逻辑仍为占位实现。
- **控制层 (Agent Loop)**: 采用 ReAct (Think-Act-Observe-Reflect) 模式，作为最高层执行引擎。它不直接操作具体工具，而是通过 `SkillEngine` 调度能力。
- **能力层 (Skill & Workflow)**: 
    - **Skill Engine**: 技能的入口，负责意图匹配（关键词+向量）与激活规则校验。
    - **Workflow Engine**: 技能的具体执行逻辑，支持 MCP 工具调用、LLM 推理、子流调用及技能递归。
- **基础设施层 (Shared Infra)**:
    - **MCP Client Layer**: 统一的工具访问层，内置连接池、熔断器、重试控制器及鉴权管理。
    - **Context Builder**: 六层上下文工程（L1-L6），负责提示词组装、智能裁剪及脱敏。
    - **State Store**: 冷热分层存储（Redis 缓存 + MySQL 持久化），支持状态检查点与恢复。

### 1.2 核心模块职责
| 模块 | 核心文件 | 主要职责 |
| :--- | :--- | :--- |
| **Agent Loop** | [loop.py](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core/app/agent/loop.py) | 驱动 ReAct 循环，维护任务栈与记忆，决策下一步动作。 |
| **Skill Engine** | [engine.py](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core/app/skill/engine.py) | 技能注册、匹配（[matcher.py](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core/app/skill/matcher.py)）与降级执行（[executor.py](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core/app/skill/executor.py)）。 |
| **Workflow Engine** | [engine.py](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core/app/workflow/engine.py) | 按照 YAML 定义执行步骤，处理变量替换与条件分支。 |
| **MCP Client** | [client.py](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core/app/mcp/client.py) | 对接外部 MCP 服务，保障调用稳定性（熔断、重试、池化）。 |
| **Context Builder** | [builder.py](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core/app/context/builder.py) | 动态组装上下文，根据 Token 限制进行智能裁剪（[trimmer.py](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core/app/context/trimmer.py)）。 |

### 1.3 模块依赖与数据流
- **依赖关系**: `API -> AgentLoop -> SkillEngine -> WorkflowEngine -> MCPClient`。
- **数据流**: 任务请求进入后，由 `AgentLoop` 发起 `Think`（调用 `SkillMatcher` 获取候选技能），确定 `Act`（调用 `SkillExecutor` 执行 Workflow），通过 `Observe` 获取结果并 `Reflect` 决定是否继续。所有过程通过 `TraceContext` 保持调用链一致。

---

## 2. Agent Loop 运行模式拆解

当前框架通过 `AgentLoop` 的 ReAct 循环与子引擎的配合，实际上支持以下多种运行模式：

| 模式名称 | 触发机制 | 资源调度逻辑 | 错误处理 | 适用场景 |
| :--- | :--- | :--- | :--- | :--- |
| **直接响应模式 (Respond)** | Think 阶段决策为 `respond` | 仅消耗 1 次 LLM 推理 | JSON 解析兜底 | 简单 FAQ、信息咨询 |
| **澄清询问模式 (Clarify)** | Think 阶段决策为 `clarify` | 无工具调用，直接返回 | 提示词引导 | 参数缺失、意图不明 |
| **单工具直连模式 (Tool)** | Think 决策跳过 Skill 直接调工具 | 绕过 Workflow，直达 MCP | MCP 重试/熔断 | 极简工具请求 |
| **Skill 编排模式 (Skill)** | Think 选中特定技能名 | 完整 Context + Workflow 链路 | 步骤短路 + 技能降级 | 复杂业务自动化 |
| **降级回退模式 (Degradation)** | 主 Workflow 失败且匹配 Policy | 递归切换 fallback workflow | 深度限制 (Max 2) | 高可用业务场景 |
| **断点恢复模式 (Stateful)** | 显式 pause/resume 或重启 | 从 Redis/MySQL 恢复 AgentState | 版本乐观锁 | 长耗时任务、系统迁移 |

---

## 3. 生产级生产需求适配分析与推荐

### 3.1 核心需求适配性评估
- **高并发能力**: `MCP Client` 已实现连接池，但 `Agent Loop` 缺乏顶层 Pool 调度，需补齐并发配额控制。
- **低延迟响应**: 建议通过减少 `llm_reasoning` 步骤和 `skill_call` 递归层级来优化。
- **准确性与稳定性**: 依靠 `Skill` 的两级匹配与 `MCP` 的熔断/重试保障。
- **可观测性**: 已有 `trace_id` 注入与 `Prometheus` 指标定义，但需补齐业务执行路径的埋点。

### 3.2 最优模式推荐
**推荐模式**: **Skill 编排模式 + 确定性 Workflow (mcp_tool 为主) + 降级策略**。

**核心理由**:
1. **语义解耦**: Skill 将底层 MCP 工具包装为业务语义，便于 LLM 理解与匹配。
2. **确定性高**: Workflow 采用 YAML 定义，执行路径可预测，优于全自主 Agent 探索。
3. **高可用保障**: 通过内置的降级（Degradation）和熔断（Circuit Breaker）机制，在外部服务抖动时仍能维持基础功能或优雅报错。

### 3.3 落地前置工作与性能指标
- **前置适配**:
    - 实现真实的 API 异步调度与任务队列。
    - 补齐管理面的热重载接线。
    - 统一 `ContextBuilder` 与 `MCP Discovery` 的工具列表接口。
- **性能校验指标**:
    - **吞吐量**: `tasks/s`、并发 Agent 实例数。
    - **时延**: `p95` 响应时间（区分推理时延与工具执行时延）。
    - **可靠性**: 熔断触发率、降级成功率、重试覆盖率。
    - **成本**: 平均任务 Token 消耗。

---
*本报告由 Trae Code Assistant 生成，基于对 agent-core 源码的深度静态分析。*
