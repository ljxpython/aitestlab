## MODIFIED Requirements

### Requirement: Agent Service 组合根必须消费已决议 Runtime 配置

每个使用公共 Runtime 的 Agent Service SHALL 在自己的 `agent_server.py` 中显式声明 `AgentDefaults`，解析 `RunnableConfig` 中的新 Runtime Context，并调用 `resolve_runtime_config` 后才创建模型和 Agent Graph。组合根 MUST NOT 接受旧字段或绕过 Policy 校验。若 Service 使用公共 Middleware，组合根还 MUST 直接列出其 Middleware 顺序，并将同一组 Runtime 合同注入 Middleware；能力依赖（Tool、MCP、Backend、Skills、Subagents）也必须在该组合根显式装配，不得由 Registry 或自动扫描完成。

#### Scenario: reference_agent 使用默认配置
- **WHEN** 调用 `get_agent({})` 且未提供 Context 覆盖
- **THEN** Service 使用自己的 AgentDefaults 解析出 `ResolvedRuntimeConfig`，创建一个包含显式 Middleware 和 Tool 列表的可运行 `create_agent` graph，并且不访问 Platform API

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
