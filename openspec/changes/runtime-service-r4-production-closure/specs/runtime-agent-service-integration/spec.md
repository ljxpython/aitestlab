## MODIFIED Requirements

### Requirement: Agent Service 组合根必须消费已决议 Runtime 配置

每个使用公共 Runtime 的 Agent Service SHALL 在自己的 `agent.py` 中显式声明 `AgentDefaults`，解析
`RunnableConfig` 中的新 Runtime Context，并调用 `resolve_runtime_config` 后才创建模型和 Agent Graph。
组合根 MUST NOT 接受旧字段或绕过 Policy 校验。若 Service 使用公共 Middleware，组合根还 MUST 直接
列出其 Middleware 顺序，并将同一组 Runtime 合同注入 Middleware；Tool、MCP、Backend、Skills 和
Subagents 等能力依赖也必须在组合根显式装配，不得由 `graphs/` 层或隐式扫描完成。生产或 Agent
Server 调用缺少已验证 Auth facts 时，Service MUST fail-closed；Local test adapter 只有在显式测试
配置下可用，不得成为生产默认路径。

#### Scenario: R4 Service 使用已验证身份
- **WHEN** Agent Server 调用任一 R4 `get_agent(config)` 且 `config` 包含已验证 Auth facts
- **THEN** Service 使用自己的 AgentDefaults 解析出 `ResolvedRuntimeConfig`，创建带显式 Policy/Middleware/Backend 边界的可运行 graph，并且不访问 Platform API

#### Scenario: R4 Service 缺少身份时 fail-closed
- **WHEN** 调用 R4 `get_agent({})` 或调用方只提供普通配置、metadata、RuntimeContext、state 或用户消息而没有已验证 Auth facts
- **THEN** Service 不创建可执行生产 graph，并返回稳定的 `runtime.auth.missing_principal`

#### Scenario: R4 显式 local test adapter
- **WHEN** 本地组合测试显式提供 `_runtime_test_model`、local identity 和必要的 in-memory checkpointer
- **THEN** 测试可以创建 fake graph；这些 adapter 在返回 graph 前被移除，不能使匿名 Agent Server 请求获得身份或生产资源

### Requirement: Service 必须使用明确的 LangChain Agent Context 边界

使用 `create_agent` 或 `create_deep_agent` 的 R4 Service SHALL 将 `RuntimeContext` 作为 `context_schema`
并通过 LangGraph invoke 的 `context` 参数接收每次 Run 的 Context。Service MUST NOT 把 Principal、Policy、
Provider 凭据、Backend 实现、MCP connection 或 Skill 路径放入模型可见 Prompt 或客户端 configurable。

#### Scenario: 合法 Context 传入 Agent
- **WHEN** 使用 `RuntimeContext` 调用 R4 graph
- **THEN** Agent、Middleware 和 Tool 使用同一个不可变 Context，且只公开经过 Policy 收缩的 Tool

#### Scenario: 资源和凭据注入被拒绝
- **WHEN** Context/configurable 包含 Backend、Skill 路径、Subagent 定义、MCP URL 或凭据
- **THEN** graph 构建或执行前返回稳定拒绝错误，不创建或替换资源

### Requirement: Service 入口必须保持 LangGraph 部署契约

每个 R4 Service SHALL 导出 `async def get_agent(config: RunnableConfig) -> Pregel`，`graphs/<graph_id>.py`
SHALL 只重导出该入口。静态构图不得在 introspection 时连接外部 MCP、Sandbox 或数据库；动态 Thread
Workspace 只能由已验证执行 scope 触发，并必须使用 Agent Server durable checkpointer 承载状态。

#### Scenario: 入口返回可编译 Graph
- **WHEN** LangGraph Server 导入任一 R4 graph entrypoint 并提供已验证 Auth facts或显式 local test adapter
- **THEN** 入口返回编译 graph，且 graph ID、Tool surface 和安全边界稳定

#### Scenario: Durable Workspace 不依赖宿主机目录
- **WHEN** R4 Backend Service 在生产 Agent Server 中创建 Thread Workspace
- **THEN** graph 使用 durable checkpointer-backed `StateBackend`，不使用共享宿主机 `FilesystemBackend` 或 `LocalShellBackend`
