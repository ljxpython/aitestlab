## MODIFIED Requirements

### Requirement: Agent Service 必须显式固定 Middleware 顺序

使用公共 Middleware 的 Agent Service SHALL 在自己的 `agent.py` 直接列出 Middleware 顺序，并复用 LangChain 官方调用限制、Tool 错误和 Tool 重试组件。公共 Runtime MUST NOT 自动向所有 Agent 注入全局 Middleware。`reference_agent` SHALL 在真实 `create_agent` graph 中接入官方 `ToolRetryMiddleware` 和 `ToolErrorMiddleware`；Tool retry MUST 位于 Tool error 的内层并配置 `on_failure="error"`。只有明确声明为幂等的 Tool 和明确的临时异常可以重试。

#### Scenario: reference_agent 构图顺序稳定
- **WHEN** 加载 `reference_agent`
- **THEN** 组合根返回包含 Runtime 校验、调用限制、Tool retry/error 和单次模型超时的 Agent graph，重复加载拓扑一致

#### Scenario: 幂等 Tool 临时失败后重试成功
- **WHEN** 已声明幂等 Tool 第一次抛出临时网络异常、随后在重试窗口内成功
- **THEN** Agent graph 最终产生成功结果，Tool 调用次数不超过初始调用加配置的重试次数

#### Scenario: 可恢复 Tool 错误在重试耗尽后返回错误消息
- **WHEN** 已声明 Tool 抛出可由模型修正的 `ValueError` 且重试次数耗尽
- **THEN** `ToolErrorMiddleware` 生成 `ToolMessage(status="error")`，消息是脱敏稳定摘要，模型可以继续处理

#### Scenario: 取消和未知异常不被吞掉
- **WHEN** 模型或 Tool handler 抛出取消、interrupt 或未声明异常
- **THEN** Middleware 链继续传播该异常，不生成伪造成功消息

## ADDED Requirements

### Requirement: Model Fallback 和 Model Retry 必须显式且有界

Service MAY 使用官方 `ModelFallbackMiddleware` 和 `ModelRetryMiddleware`，但 MUST 在组合根显式装配。Fallback model MUST 是已由 Service 构造并通过 Runtime Policy 允许的模型；不得从用户消息、普通 `configurable` 字段或匿名默认值读取。Model Retry 默认关闭，启用时 MUST 限定异常、重试次数和总预算，且不得与 Provider SDK retry 形成未记录的乘法重试。

#### Scenario: Primary 模型临时失败后使用显式 fallback
- **WHEN** Service 显式配置的 primary model 抛出可 fallback 的临时异常，且 fallback model 已注入并获 Policy 允许
- **THEN** Agent 使用 fallback model 完成本次模型调用，并保留正常的 graph 结果

#### Scenario: 不可 fallback 的模型错误直接失败
- **WHEN** primary model 抛出参数、权限、上下文长度或其他未列入临时错误集合的异常
- **THEN** Agent 不切换未经授权的模型，原异常继续传播

#### Scenario: Model Retry 达到上限后终止
- **WHEN** 显式启用的 Model Retry 对同一候选模型持续收到匹配异常直至达到上限
- **THEN** 不再发起额外调用，向 Run Coordinator 传播最后一个异常

### Requirement: R3 Middleware 必须有真实 graph 案例和证据分级

R3 测试 SHALL 通过 `create_agent` 编译出的 Reference Agent graph 驱动 Model/Tool 调用，不能仅直接调用 Middleware 方法。测试 SHALL 分别记录代码位置、组合入口、断言位置和证据等级；fake/local 证据 MUST NOT 被标记为真实 Provider、跨进程 Durable 或生产完成。

#### Scenario: 真实 graph 触发 Tool retry/error
- **WHEN** local test adapter 驱动模型发出 Tool call，并让测试 Tool 产生临时失败或可恢复错误
- **THEN** 断言真实 graph 的重试次数、ToolMessage 状态和模型后续结果，而不是只断言 Middleware 构造成功

#### Scenario: 单次模型超时和取消边界保持不变
- **WHEN** Provider handler 超过单次超时时限或收到取消
- **THEN** 当前调用被取消并传播 `TimeoutError`/`CancelledError`，不被 fallback、ToolError 或成功结果吞掉
