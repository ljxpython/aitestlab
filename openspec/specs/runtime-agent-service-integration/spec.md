# runtime-agent-service-integration Specification

## Purpose

定义 Agent Service 组合根如何显式消费 Runtime 合同并导出可运行 LangGraph。
## Requirements
### Requirement: Agent Service 组合根必须消费已决议 Runtime 配置

每个使用公共 Runtime 的 Agent Service SHALL 在自己的 `agent.py` 中显式声明 `AgentDefaults`，解析 `RunnableConfig` 中的新 Runtime Context，并调用 `resolve_runtime_config` 后才创建模型和 Agent Graph。组合根 MUST NOT 接受旧字段或绕过 Policy 校验。若 Service 使用公共 Middleware，组合根还 MUST 直接列出其 Middleware 顺序，并将同一组 Runtime 合同注入 Middleware；Tool、MCP、Backend、Skills 和 Subagents 等能力依赖也必须在组合根显式装配，不得由 `graphs/` 层或隐式扫描完成。Graph 创建完成后，Service MUST 在返回前调用 Runtime observability adapter，以合并本次 Run 的 Langfuse callback 和安全 metadata；该适配器不得改变 Graph 拓扑或 Runtime 决议结果。生产或 Agent Server 调用缺少已验证 Auth facts 时，Service MUST fail-closed，并返回稳定的 `runtime.auth.missing_principal` 或等价认证错误；Service MUST NOT 从空 `RunnableConfig`、RuntimeContext、metadata、state 或用户消息补 Principal、Policy 或凭据。Local test adapter 只有在显式测试配置下可用，不得成为生产默认路径。

#### Scenario: reference_agent 使用已验证身份
- **WHEN** Agent Server 调用 `get_agent(config)` 且 `config` 包含已验证的 Auth facts、未提供 Context 覆盖
- **THEN** Service 使用自己的 AgentDefaults 解析出 `ResolvedRuntimeConfig`，创建一个包含显式 Middleware 的可运行 `create_agent` graph，并且不访问 Platform API

#### Scenario: 缺少身份时 fail-closed
- **WHEN** 调用 `reference_agent.get_agent({})` 或调用方只提供普通配置、metadata、RuntimeContext、state 或用户消息而没有已验证 Auth facts
- **THEN** Service 不创建可执行生产 graph，并返回稳定的 `runtime.auth.missing_principal` 或等价认证错误

#### Scenario: 显式 local test adapter
- **WHEN** 本地组合测试显式提供 test-only model/identity adapter
- **THEN** 测试可以创建 fake model graph；该 adapter 不进入生产配置，也不能使匿名 Agent Server 请求获得身份

#### Scenario: Context 覆盖生成参数
- **WHEN** 调用图时传入合法 `RuntimeContext(temperature=0)`
- **THEN** Agent 使用解析后的零值参数，Context 不被写回 `configurable` 或持久化状态

#### Scenario: 非法模型或工具被拒绝
- **WHEN** Context 选择不在 Service Policy 中的模型或工具
- **THEN** `get_agent` 或图构建抛出稳定 `RuntimeResolutionError`，不创建模型、不返回部分 graph

### Requirement: Service 必须使用明确的 LangChain Agent Context 边界

使用 `create_agent` 的 Service SHALL 将 `RuntimeContext` 作为 `context_schema`，并通过 LangGraph invoke 的 `context` 参数接收每次 Run 的 Context。Service MUST NOT 把 Principal、Policy 或 Provider 凭据放入模型可见 Prompt。

#### Scenario: 合法 Context 传入 Agent
- **WHEN** 使用 `RuntimeContext` 调用 `graph.ainvoke(..., context=context)`
- **THEN** Agent 成功执行，且工具/中间件可从 Runtime context 读取同一个不可变值

#### Scenario: 旧字段不兼容
- **WHEN** Context 包含 `platform_runtime`、`enable_tools` 或身份字段
- **THEN** Context 解析失败并返回 `runtime.context.unknown_field` 或 `runtime.context.identity_field_forbidden`

### Requirement: Service 入口必须保持 LangGraph 部署契约

每个 Service SHALL 导出 `async def get_agent(config: RunnableConfig) -> Pregel`，`graphs/<graph_id>.py` SHALL 只重导出该入口。对无 Thread 级外部资源的静态 Agent，重复调用入口 MUST 保持相同拓扑；测试模型注入不得改变生产部署配置。

#### Scenario: 入口返回可编译 Graph
- **WHEN** LangGraph Server 导入 `runtime_service.graphs.reference_agent:get_agent`
- **THEN** 入口返回 `Pregel`，且不触发 Platform、MCP、Sandbox 或数据库连接

#### Scenario: Server 配置被保留
- **WHEN** `get_agent(config)` 返回 graph
- **THEN** graph 保留传入的 LangGraph `RunnableConfig` metadata/configurable，业务 Runtime Context 仍通过 invoke context 传递

#### Scenario: Langfuse disabled does not alter the service graph
- **WHEN** `LANGFUSE_ENABLED` is not true
- **THEN** `get_agent` 返回原始可运行 Graph，且不导入或初始化 Langfuse SDK

#### Scenario: Langfuse binding preserves the service contract
- **WHEN** `LANGFUSE_ENABLED=true` 且配置有效
- **THEN** `get_agent` 返回同一 Graph 拓扑，并保留调用方 RunnableConfig 的 callbacks、metadata 和 tags，同时附加安全的 Run 关联字段

### Requirement: workflow_demo 必须提供 Typed StateGraph 和可判定条件分支

`workflow_demo` SHALL 在自己的 Service 模块内声明 Typed StateGraph，并提供至少一个由 State
决定的条件分支。每条分支 MUST 是可执行、可观察且有稳定结果的路径；Graph 入口和拓扑仍
遵守 `graphs/<graph_id>.py` 只重导出的部署契约。该要求只冻结 R2 的本地 Workflow 行为，
不要求真实 Provider 或 Platform API。

#### Scenario: 条件分支选择路径 A
- **WHEN** 输入满足 Service 声明的路径 A 条件
- **THEN** Graph 执行路径 A 的节点并返回路径 A 的稳定结果，不执行路径 B 的节点

#### Scenario: 条件分支选择路径 B
- **WHEN** 输入满足 Service 声明的路径 B 条件
- **THEN** Graph 执行路径 B 的节点并返回路径 B 的稳定结果，不执行路径 A 的节点

#### Scenario: 分支拓扑在重复加载中稳定
- **WHEN** 在无 Thread 级外部资源的情况下重复调用 `workflow_demo.get_agent(config)`
- **THEN** 返回 Graph 的 nodes、edges 和 state schema 一致，且加载不连接 Sandbox、MCP、数据库或 Platform API

### Requirement: workflow_demo 必须支持本地 Interrupt/Resume 且不重复已完成步骤

`workflow_demo` SHALL 提供至少一个服务端声明的可恢复 Interrupt。使用同一 Thread 和本地
checkpointer Resume 时，Graph MUST 从未完成的恢复点继续；已经成功完成的节点 MUST NOT
再次执行。R2 的 checkpointer 可以是进程内测试实现；PostgreSQL、Redis、Worker 重启、
SIGTERM handoff 和生产 Durable Run 不属于本 Requirement 的通过证据。

#### Scenario: Workflow 在人工确认点暂停
- **WHEN** 输入到达需要人工确认的节点
- **THEN** Graph 返回可识别的未解决 interrupt，暂停点和此前已完成的 State 被 checkpointer 保存

#### Scenario: Resume 从指定 interrupt 继续
- **WHEN** 使用同一 Thread 对服务端声明的 interrupt 提交合法 Resume value
- **THEN** Graph 从该恢复点继续并产生终态结果，不能通过 thread 最新状态或前端数组索引推断恢复目标

#### Scenario: Resume 不重复已完成节点
- **WHEN** Workflow 在确认点之前已有节点成功执行，随后发生 Resume
- **THEN** 节点执行计数或等价可观察事件证明此前成功节点只执行一次

#### Scenario: 非法 Resume 被拒绝
- **WHEN** Resume 使用不存在、已解决或不属于当前 active Workflow 的 interrupt 标识
- **THEN** Service 返回稳定恢复错误，不改变其他 Thread 或 interrupt 的状态
