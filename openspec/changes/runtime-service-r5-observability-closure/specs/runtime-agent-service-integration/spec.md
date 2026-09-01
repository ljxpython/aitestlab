## MODIFIED Requirements

### Requirement: Agent Service 组合根必须消费已决议 Runtime 配置

每个使用公共 Runtime 的 Agent Service SHALL 在自己的 `agent.py` 中显式声明 `AgentDefaults`，解析
`RunnableConfig` 中的新 Runtime Context，并调用 `resolve_runtime_config` 后才创建模型和 Agent Graph。
组合根 MUST NOT 接受旧字段或绕过 Policy 校验。若 Service 使用公共 Middleware，组合根还 MUST 直接列出
其 Middleware 顺序，并将同一组 Runtime 合同注入 Middleware；Tool、MCP、Backend、Skills 和 Subagents
等能力依赖也必须在组合根显式装配，不得由 `graphs/` 层或隐式扫描完成。Graph 创建完成后，Service
MUST 在返回前调用 Runtime observability adapter，以合并本次 Run 的 Langfuse callback、技术关联字段
和经过 Auth/Resolver 验证的安全 metadata；未经验证的 caller metadata 不得成为 Trace 身份。适配器不得
改变 Graph 拓扑、Runtime 决议结果或原始业务异常。Langfuse 生命周期由 Agent Server application
lifespan 统一管理，Service 入口不得自行关闭进程级 client。生产或 Agent Server 调用缺少已验证 Auth
facts 时，Service MUST fail-closed，并返回稳定的 `runtime.auth.missing_principal` 或等价认证错误；
Service MUST NOT 从空 `RunnableConfig`、RuntimeContext、metadata、state 或用户消息补 Principal、Policy
或凭据。Local test adapter 只有在显式测试配置下可用，不得成为生产默认路径。

#### Scenario: reference_agent 使用已验证身份
- **WHEN** Agent Server 调用 `get_agent(config)` 且 `config` 包含已验证的 Auth facts、未提供 Context 覆盖
- **THEN** Service 使用自己的 AgentDefaults 解析出 `ResolvedRuntimeConfig`，创建一个包含显式 Middleware
  的可运行 `create_agent` graph，向观测 adapter 传入可信摘要，并且不访问 Platform API

#### Scenario: 缺少身份时 fail-closed
- **WHEN** 调用 `reference_agent.get_agent({})` 或调用方只提供普通配置、metadata、RuntimeContext、state
  或用户消息而没有已验证 Auth facts
- **THEN** Service 不创建可执行生产 graph，并返回稳定的 `runtime.auth.missing_principal` 或等价认证错误，
  且不产生带伪造 user/tenant/project 的 Trace metadata

#### Scenario: 显式 local test adapter
- **WHEN** 本地组合测试显式提供 test-only model/identity adapter
- **THEN** 测试可以创建 fake model graph；该 adapter 不进入生产配置，也不能使匿名 Agent Server 请求获得身份

#### Scenario: Context 覆盖生成参数
- **WHEN** 调用图时传入合法 `RuntimeContext(temperature=0)`
- **THEN** Agent 使用解析后的零值参数，Context 不被写回 `configurable` 或持久化状态

#### Scenario: 非法模型或工具被拒绝
- **WHEN** Context 选择不在 Service Policy 中的模型或工具
- **THEN** `get_agent` 或图构建抛出稳定 `RuntimeResolutionError`，不创建模型、不返回部分 graph

#### Scenario: Langfuse disabled does not alter the service graph
- **WHEN** `LANGFUSE_ENABLED` is not true
- **THEN** `get_agent` 返回原始可运行 Graph，且不导入或初始化 Langfuse SDK

#### Scenario: Langfuse binding preserves the service contract
- **WHEN** `LANGFUSE_ENABLED=true`、应用 lifespan 已初始化有效 client 且配置有效
- **THEN** `get_agent` 返回同一 Graph 拓扑，保留 caller callbacks 和 allowlisted metadata/tags，同时附加可信
  Run 关联字段，并且不创建第二个进程 client
