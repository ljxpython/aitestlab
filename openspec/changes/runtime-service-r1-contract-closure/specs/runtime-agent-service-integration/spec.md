## MODIFIED Requirements

### Requirement: Agent Service 组合根必须消费已决议 Runtime 配置
每个使用公共 Runtime 的 Agent Service SHALL 在自己的 `agent.py` 中显式声明 `AgentDefaults`，解析 `RunnableConfig` 中的新 Runtime Context，并调用 `resolve_runtime_config` 后才创建模型和 Agent Graph。组合根 MUST consume the Principal and Policy facts produced by Agent Server Auth at run time, MUST NOT accept old fields or bypass Policy/Actor permission checks, and MUST not depend on module-level production identity constants. 若 Service 使用公共 Middleware，组合根还 MUST 直接列出其 Middleware 顺序，并将同一组 Runtime 合同注入 Middleware；Tool、MCP、Backend、Skills 和 Subagents 等能力依赖也必须在组合根显式装配，不得由 `graphs/` 层或隐式扫描完成装配。Graph 创建完成后，Service MUST 在返回前调用 Runtime observability adapter，以合并本次 Run 的 Langfuse callback 和安全 metadata；该适配器不得改变 Graph 拓扑或 Runtime 决议结果。

#### Scenario: reference_agent 使用 Agent Server Auth 身份
- **WHEN** Agent Server authenticates a request with a valid Delegation JWT and the graph receives a valid Runtime Context
- **THEN** the Service resolves the request's Principal, Policy and Context through one Resolver chain and does not use a fixed production Principal or Policy

#### Scenario: 缺少或伪造身份时拒绝
- **WHEN** graph execution has no verified Agent Server user or the caller puts identity/permissions in Runtime Context
- **THEN** execution fails closed before model or tool creation with a stable auth/context error

#### Scenario: Context 覆盖生成参数
- **WHEN** 调用图时传入合法 `RuntimeContext(temperature=0)`
- **THEN** Agent 使用解析后的零值参数，Context 不被写回 `configurable` 或持久化状态

#### Scenario: 非法模型或工具被拒绝
- **WHEN** Context 选择不在 Service Policy 或 Actor permission 交集中的模型或工具
- **THEN** `get_agent` 或图构建抛出稳定 `RuntimeResolutionError`，不创建模型、不返回部分 graph

### Requirement: Service 必须使用明确的 LangChain Agent Context 边界
使用 `create_agent` 的 Service SHALL 将 `RuntimeContext` 作为 `context_schema`，并通过 LangGraph invoke 的 `context` 参数接收每次 Run 的 Context。Service MUST validate the Context hash against the verified Auth facts before a model or tool call. Service MUST NOT 把 Principal、Policy 或 Provider 凭据放入模型可见 Prompt。

#### Scenario: 合法 Context 传入 Agent
- **WHEN** 使用 `RuntimeContext` 调用 `graph.ainvoke(..., context=context)` and the verified Auth facts contain the matching Context hash
- **THEN** Agent 成功执行，且工具/中间件可从 Runtime context 读取同一个不可变值

#### Scenario: 旧字段不兼容
- **WHEN** Context 包含 `platform_runtime`、`enable_tools` 或身份字段
- **THEN** Context 解析失败并返回 `runtime.context.unknown_field` 或 `runtime.context.identity_field_forbidden`

#### Scenario: Context hash 不匹配
- **WHEN** the request Context differs from the signed Context hash
- **THEN** the Agent rejects the Run before model invocation and does not fall back to a default Context

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

