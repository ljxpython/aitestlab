## MODIFIED Requirements

### Requirement: Agent Service 组合根必须消费已决议 Runtime 配置

每个使用公共 Runtime 的 Agent Service SHALL 在自己的 `agent.py` 中显式声明 `AgentDefaults`，解析
`RunnableConfig` 中的新 Runtime Context，并调用 `resolve_runtime_config` 后才创建模型和 Agent Graph。组合根 MUST NOT 接受旧字段或绕过 Policy 校验。若 Service 使用公共 Middleware，组合根还 MUST 直接列出其 Middleware 顺序，并将同一组 Runtime 合同注入 Middleware；Tool、MCP、Backend、Skills 和 Subagents 等能力依赖也必须在组合根显式装配，不得由 `graphs/` 层或隐式扫描完成。Graph 创建完成后，Service MUST 在返回前调用 Runtime observability adapter，以合并本次 Run 的 Langfuse callback 和安全 metadata；该适配器不得改变 Graph 拓扑或 Runtime 决议结果。生产或 Agent Server 调用缺少已验证 Auth facts 时，Service MUST fail-closed，并返回稳定的 `runtime.auth.missing_principal` 或等价认证错误；Service MUST NOT 从空 `RunnableConfig`、RuntimeContext、metadata、state 或用户消息补 Principal、Policy 或凭据。Local test adapter 只有在显式测试配置下可用，不得成为生产默认路径。`reference_agent` SHALL use the official Tool Error and Tool Retry middleware in an actual graph invocation, with test-only model/tool adapters allowed only for local evidence.

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

#### Scenario: Reference Agent 的 Tool 可靠性由真实 graph 证明
- **WHEN** 显式 local test adapter 使 Reference Agent 发出 Tool call
- **THEN** Agent graph 实际执行 Tool retry/error Middleware，并对成功、可恢复错误和未知异常分别呈现规范结果
