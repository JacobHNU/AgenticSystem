# Findings

## 2026-06-05
- 关键输入文档位于项目根目录：`2026-05-29-agent-core-architecture-design.md`、`2026-05-29-agent-core-implementation-plan.md`。
- 目标代码位于 `agent-core/`，核心包分为 `agent`、`api`、`context`、`core`、`mcp`、`monitoring`、`reload`、`skill`、`workflow`。
- 测试目录覆盖 `agent loop`、`workflow engine`、`mcp client`、`circuit breaker`、`retry controller` 等关键能力，说明 loop、工具调度、稳定性机制已有基础实现。
- 真实主链路与 README、设计文档基本一致：`FastAPI -> AgentLoop -> SkillEngine -> WorkflowEngine -> MCPClientLayer`，其中 `SkillEngine` 负责技能匹配与执行，`WorkflowEngine` 负责步骤级编排，`MCPClientLayer` 负责最终工具调用。
- `AgentLoop.run()` 当前实现的是单一 ReAct 主循环，内部通过 `Thought.action_type` 分化为 `respond`、`clarify`、`skill`、`tool` 四类动作路径，并支持 `pause()` / `resume()` / 周期性 checkpoint。
- `SkillExecutor` 已实现递归降级执行：主工作流失败后按 `degradation_policy` 匹配 fallback workflow，最多递归两层，成功后返回 `degraded_success`。
- `WorkflowEngine` 已实现 4 类步骤执行模式：`mcp_tool`、`llm_reasoning`、`sub_workflow`、`skill_call`，并带条件判断、模板变量替换、步骤级重试与超时控制。
- `ContextBuilder` 的实际实现更偏“按层加载+裁剪”的 prompt 组装器：遍历 L1-L6 layer loader，统计 token，超限时按优先级裁剪；`load_history` 内部优先保留 FAILED/SKIPPED，再保留最近 COMPLETED。
- `MCPClientLayer` 实现了发现、连接池、重试、熔断、鉴权、trace 透传；其中熔断器在入口先短路 `OPEN` 状态，异常时记录失败并返回 `tool_unavailable`。
- `SkillRegistry` 已实现热更新版本历史和执行绑定，但当前 `SkillEngine.execute()` 直接 `registry.get(skill_name)`，未使用 `bind/release`，说明“运行中版本绑定”设计仅部分落地。
- API 层当前明显偏占位：`agent.py` 未真正启动后台任务，`ws.py` 只做 echo/ack，`admin.py` 也未接入 `HotReloadManager`；因此生产运行入口与管理面尚未完全闭环。
- `agent-core` 的核心执行链路已闭环（Loop -> Skill -> Workflow -> MCP），且已升级支持并行调度与动态固化。
- 升级后的 `WorkflowEngine` 采用基于 `depends_on` 的拓扑并行执行逻辑，显著提升了“固定工作流”场景的执行效率。
- `DynamicWorkflowBuilder` 模块成功打通了“业务说明 -> 运行态 Workflow”的转换路径，满足了“柔性场景”的自主解读需求。
- `SkillRegistry.promote_skill` 实现了执行后的自动化“晋升”机制，使得柔性 Skill 在首次成功执行后可自动转化为固定 Skill，实现了效率的自进化闭环。
- 识别出 11 种细分运行模式，推荐以 `Skill 编排 + MCP 工具为主` 的组合作为生产级基准。
- 详细分析结论已汇总至本地文件 [agent-core-analysis-report.md](file:///g:/02LLM/02Claude_Code/01_projects/05-llm+agent/AgenticSystem/agent-core-analysis-report.md)。
