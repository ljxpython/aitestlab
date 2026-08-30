## MODIFIED Requirements

### Requirement: Agent Service 组合根必须消费已决议 Runtime 配置

每个使用公共 Runtime 的 Agent Service SHALL 在自己的 `agent.py` 中显式声明 `AgentDefaults`，解析
`RunnableConfig` 中的新 Runtime Context，并调用 `resolve_runtime_config` 后才创建模型和 Agent Graph。
组合根 MUST NOT 接受旧字段或绕过 Policy 校验。若 Service 使用公共 Middleware，组合根还 MUST 直接列出
其 Middleware 顺序，并将同一组 Runtime 合同注入 Middleware；Tool、MCP、Backend、Skills 和 Subagents
等能力依赖也必须在组合根显式装配，不得由 `graphs/` 层或隐式扫描完成。Graph 创建完成后，Service
MUST 在返回前调用 Runtime observability adapter，以合并本次 Run 的 Langfuse callback 和安全 metadata；
该适配器不得改变 Graph 拓扑或 Runtime 决议结果。

#### Scenario: reference_agent 使用默认配置
- **WHEN** 调用 `get_agent({})` 且未提供 Context 覆盖
- **THEN** Service 使用自己的 AgentDefaults 解析出 ResolvedRuntimeConfig，创建一个包含显式 Middleware
  的可运行 `create_agent` graph，并且不访问 Platform API

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
- **WHEN** `LANGFUSE_ENABLED=true` 且配置有效
- **THEN** `get_agent` 返回同一 Graph 拓扑，并保留调用方 RunnableConfig 的 callbacks、metadata 和 tags，
  同时附加安全的 Run 关联字段
