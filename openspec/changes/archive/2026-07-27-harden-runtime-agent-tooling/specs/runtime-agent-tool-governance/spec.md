## ADDED Requirements

### Requirement: 已注册工具必须在运行时 middleware 后保留
runtime-service SHALL 在应用 `RuntimeRequestMiddleware` 后保留图创建阶段已注册的工具，包括 `create_agent(tools=...)`、middleware 工具和 DeepAgents 内置工具。运行时 required 工具与允许的 public optional 工具必须在保留集合上追加并按名称去重。

#### Scenario: 普通 Agent 注册业务工具
- **WHEN** 一个服务 graph 在创建时注册业务工具并应用 runtime middleware
- **THEN** 模型请求与后续工具执行均保留该业务工具

#### Scenario: DeepAgents 注册内置工具
- **WHEN** 一个 DeepAgent 在创建时注册文件、待办或子任务内置工具并应用 runtime middleware
- **THEN** runtime middleware 不得移除这些内置工具

#### Scenario: 调用方禁用公共工具
- **WHEN** runtime context 将 `enable_tools` 设为 `false`
- **THEN** middleware 不公开 optional public 工具且仍保留已注册或 required 工具

### Requirement: 公共 optional 工具必须显式允许
runtime-service SHALL 仅公开 runtime context 指定的 public 工具名称；当 context 未指定 `tools` 时，必须仅使用该 Agent 的 `AgentDefaults.public_tool_names`。当两者为空时，不得公开任何 optional public 工具或 MCP server。

#### Scenario: Agent 声明默认公开工具
- **WHEN** `enable_tools` 为 `true` 且调用方未提供 `tools`，并且 Agent 声明 `public_tool_names`
- **THEN** middleware 仅公开该默认 allowlist 中的工具

#### Scenario: 未声明默认公开工具
- **WHEN** `enable_tools` 为 `true` 且调用方未提供或提供空 `tools`，并且 Agent 未声明 `public_tool_names`
- **THEN** middleware 不公开任何 optional public 工具或 MCP server

#### Scenario: 请求未知公共工具
- **WHEN** 调用方请求不在 Agent public 工具目录中的名称
- **THEN** runtime-service 必须拒绝该请求并返回包含未知名称与允许名称的清晰错误

### Requirement: 动态工具必须具有工具调用执行路径
runtime-service SHALL 只向模型公开已经在 graph 创建阶段注册的工具，或由已注册稳定代理在工具调用阶段执行的运行时发现工具。不得只在模型调用阶段注入 ToolNode 无法执行的工具。

#### Scenario: 静态可枚举工具
- **WHEN** 服务的工具可在 graph 创建时枚举
- **THEN** 服务必须在创建 graph 时注册该工具后才允许模型调用它

#### Scenario: 运行时发现工具有稳定代理
- **WHEN** runtime context 选择一个运行时发现工具且服务提供已注册的稳定代理
- **THEN** 代理在工具调用阶段根据经验证的 context 解析并执行目标工具

#### Scenario: 运行时发现工具缺少执行路径
- **WHEN** runtime context 选择的工具不能预注册且没有稳定代理
- **THEN** runtime-service 不得向模型公开该工具
