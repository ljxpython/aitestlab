# runtime-middleware-reliability Specification

## Purpose
TBD - created by archiving change runtime-service-r3-middleware-reliability. Update Purpose after archive.
## Requirements
### Requirement: RuntimeConfigMiddleware 必须在执行边界重新决议配置

公共 `RuntimeConfigMiddleware` SHALL 使用注入的 Principal、Policy 和 AgentDefaults 解析每次 Agent Run 的 Runtime Context，并在 Model/Tool 执行前 fail-closed。它 MUST NOT 读取 Platform API、环境变量或跨 Run 缓存运行值。

#### Scenario: 合法 Context 通过模型边界
- **WHEN** Agent 使用合法 `RuntimeContext` 执行模型调用
- **THEN** Middleware 调用 Resolver 并将已决议的模型和生成参数交给下一层

#### Scenario: 非法 Context 在模型前失败
- **WHEN** Context 包含未知字段、身份字段或越权模型
- **THEN** Middleware 抛出稳定 `RuntimeResolutionError`，且 Provider handler 不被调用

#### Scenario: 未授权 Tool 在执行前失败
- **WHEN** Tool 请求名称不在已决议 Required/Optional allowlist 中
- **THEN** Middleware 拒绝调用 Tool handler，不产生外部副作用

### Requirement: 单次模型超时必须有界且传播

`ModelCallTimeoutMiddleware` SHALL 仅限制一次 `handler(request)` 的 wall-clock 时间，超时后 MUST 取消当前调用并传播 `TimeoutError`。它不得自动 retry、fallback 或吞掉取消。

#### Scenario: Provider 调用在时限内完成
- **WHEN** Model handler 在 timeout 前返回
- **THEN** Middleware 返回原始 `ModelResponse`，不改变结果

#### Scenario: Provider 调用超时
- **WHEN** Model handler 超过配置时限
- **THEN** 当前调用被取消并向外抛出 `TimeoutError`，外层可观察到失败

### Requirement: Agent Service 必须显式固定 Middleware 顺序

使用公共 Middleware 的 Agent Service SHALL 在自己的 `agent.py` 直接列出 Middleware 顺序，并复用 LangChain 官方调用限制、Tool 错误和 Tool 重试组件。公共 Runtime MUST NOT 自动向所有 Agent 注入全局 Middleware。

#### Scenario: reference_agent 构图顺序稳定
- **WHEN** 加载 `reference_agent`
- **THEN** 组合根返回包含 Runtime 校验、调用限制和单次模型超时的 Agent graph，重复加载拓扑一致

#### Scenario: 取消和未知异常不被吞掉
- **WHEN** 模型或 Tool handler 抛出取消、interrupt 或未声明异常
- **THEN** Middleware 链继续传播该异常，不生成伪造成功消息

