## Context

本变更属于 `apps/runtime-service` 的 B3 Governed Change，适用边界是 Runtime Service ->
`reference_agent` -> LangChain Agent graph -> Model/Tool 调用。当前锁定版本为
`langchain==1.3.17`，官方已经提供 `ToolErrorMiddleware`、`ToolRetryMiddleware`、
`ModelFallbackMiddleware` 和 `ModelRetryMiddleware`；项目已有公共
`RuntimeConfigMiddleware`、`ModelCallTimeoutMiddleware`，但 R3 归档后只有前两者真正接入
Agent，Tool 错误/重试停留在孤立测试。

本设计加载了 Runtime Service 的 15 号 Middleware 设计、14 号 Runtime 合同、25 号测试契约，
并对照 Open SWE 的 `model_fallback.py`、`task_retry.py`、`tool_error_handler.py`、
`prepare_run.py`、`repair_orphaned_tool_calls.py` 和 `stable_tool_order.py`。Open SWE 的
GitHub、Slack、Sandbox、Provider sanitizer 和 Plan/PR 业务不属于本变更。

## Goals / Non-Goals

**Goals:**

- 让 `reference_agent` 的 Tool 错误和有限重试成为真实 Agent 调用链，而不只是直接调用 Middleware 的单测。
- 固定并验证 Tool Middleware 的嵌套顺序：`ToolRetryMiddleware` 在内，`ToolErrorMiddleware` 在外；
  重试耗尽后只把明确可恢复异常转换为脱敏 `ToolMessage`。
- 以显式 local test adapter 覆盖官方 Model fallback/retry 的组合路径，同时保持生产默认不偷偷增加
  未经 Policy 授权的模型，也不与 Provider SDK retry 叠加。
- 使用确定性的 fake model 和注入 Tool 覆盖成功、临时失败、可恢复错误、未知异常、超时和取消案例。
- 在 15 号文档记录每个候选 Middleware 的实现状态、证据位置和 Open SWE 取舍。

**Non-Goals:**

- 不创建 Middleware Builder、Registry、默认全家桶或自动扫描机制。
- 不实现 Run 总 deadline、durable terminal/finalizer、Auth Middleware、业务 Workflow、MCP 动态加载、
  Sandbox circuit breaker 或 Subagent 编排。
- 不复制 Open SWE 的全捕获 Tool Error；权限错误、取消、interrupt、未知异常和副作用未知结果继续传播。
- 不默认启用 Model Retry；若真实 Provider retry 证据不足，后续 Service 变更再显式开启并记录乘法重试预算。
- 不把 fake model、fake Tool 测试证据写成真实 Provider 或 Durable 证据。

## Decisions

### 1. 真实接入官方 Tool Middleware

在 `reference_agent/agent.py` 直接导入并列出官方 Middleware。列表保持 Service 组合根唯一真源，
顺序使用当前 LangChain 官方契约：

```text
RuntimeConfigMiddleware
  -> ModelCallLimitMiddleware
  -> ToolCallLimitMiddleware
  -> ToolErrorMiddleware(on_error=严格错误分类器, tools=[同一 Tool 集])
  -> ToolRetryMiddleware(on_failure="error", tools=[显式幂等 Tool])
  -> ModelCallTimeoutMiddleware
```

LangChain 当前锁定版本中列表第一个 wrapper 是最外层，因此上表中 `ToolRetryMiddleware` 实际位于
`ToolErrorMiddleware` 内层。列表顺序和实际嵌套关系由组合测试固定。`ToolErrorMiddleware` 的错误处理函数只处理当前案例定义的
`ValueError` 等可由模型修正的错误，返回不包含原始异常文本的稳定摘要；其他异常返回 `None` 并传播。
`ToolRetryMiddleware` 只对显式幂等 Tool 和明确的临时异常重试，使用 `initial_delay=0` 的确定性单测配置，
生产配置保持有界退避。

### 2. Model fallback/retry 采用显式测试适配和策略门槛

`reference_agent` 的正式默认路径不凭空构造第二个 Provider。测试通过已经存在的
`configurable._runtime_model` 注入 primary，并新增同样显式、test-only 的 fallback model 注入；
只有注入 fallback 时才装配官方 `ModelFallbackMiddleware`。这样可以验证真实 `create_agent` graph 的
fallback，而不会把 fake 模型入口变成生产匿名路径。

`ModelRetryMiddleware` 默认不装配。仅在测试显式声明 retry adapter 时组合，用于验证异常过滤、有限尝试和
最终传播；真实 Service 以后要启用它，必须有明确 Provider retry 配置和预算证据，并在 Service 组合根直接
声明，不放进公共默认层。

`RuntimeConfigMiddleware` 仍负责每次 Model 边界的 Runtime Resolver。Fallback model 只能通过显式注入的
测试对象进入测试路径；未来真实 fallback 必须先成为 Service catalog 中经 Policy 允许的模型，再由 Service
创建并装配，不能从 `configurable.model_id` 或用户消息读取。

### 3. 案例使用真实 graph，Tool 用测试注入保持生产工具最小

生产 `read_reference` 保持只读和稳定。组合测试在不改变 Tool 名称和 Policy 的前提下，将测试 Tool
注入 `reference_agent` 模块，驱动真实 `create_agent` graph 发出 tool call，覆盖：

- 幂等 Tool 第一次 `ConnectionError`、第二次成功；
- `ValueError` 经重试耗尽后变为 `ToolMessage(status="error")`，模型可以继续结束；
- `RuntimeError`、`CancelledError` 和 interrupt 类控制流不被 ToolError 吞掉；
- primary model 失败后 fallback model 返回结果；
- model retry 达到上限后抛出最后一个异常；
- 单次模型超时只取消当前 Provider handler。

这些是本地/组合证据，不替代 `RUNTIME_E2E=1` 的真实模型证据。真实模型 smoke 继续使用生产默认
Tool 和当前凭据，不人为制造 Provider outage。

### 4. Open SWE 取舍

借鉴 `task_retry.py` 的按任务/异常分类、`model_fallback.py` 的 fallback 只处理临时 Provider 错误、
以及 `prepare_run.py` 的 fingerprint 幂等思路；不复制实现，因为官方 Middleware 已覆盖本轮调用边界，
而 Runtime 尚无 Open SWE 的 Sandbox、Thread store、Slack/GitHub 目标。

`RepairOrphanedToolCallsMiddleware`、`StableToolResultOrderMiddleware` 和 `PrepareRunMiddleware` 只在
当前 LangGraph 版本出现可复现恢复/缓存问题且拥有对应持久化边界时另起变更；`TimeoutWrapupMiddleware`
属于长任务产品行为，不替代 Run deadline。

## Risks / Trade-offs

- [官方 Middleware 的列表顺序容易被误读] -> 用真实 `create_agent` graph 和事件/调用计数测试固定嵌套关系。
- [Tool retry 可能重复外部副作用] -> 只配置只读/明确幂等 Tool；未知结果 Tool 不进入名单。
- [Provider SDK retry 与 ModelRetryMiddleware 形成乘法] -> 默认关闭 ModelRetry，并在任何后续启用变更中记录总预算。
- [fallback 可能绕过 Runtime Model Policy] -> fallback 只接受 Service 显式构造对象；真实路径必须先完成 Policy catalog 校验。
- [fake graph 证据被误读为生产能力] -> 文档和 verification.md 明确标记 local-complete，不提升 E2E/Durable 证据等级。
- [Open SWE 的全捕获错误处理隐藏程序缺陷] -> 使用官方严格 `on_error`，未知异常返回 `None`。

## Migration Plan

先更新组合测试和 15 号对齐矩阵，再在 owner review 通过后接入 Middleware。验证顺序为本地 Middleware 单测、
Reference Agent 真实 graph 组合测试、全 Runtime 测试、真实模型 smoke（显式 `RUNTIME_E2E=1`），最后更新
verification.md 和 graphify。回滚只需移除新增列表项和 test-only adapter，不涉及数据迁移。

## Open Questions

- 真实 Provider fallback 的模型 ID、凭据和 Policy catalog 尚未冻结，当前只实现显式测试适配，不把它标记为生产 fallback 完成。
- `RepairOrphanedToolCallsMiddleware` 是否需要公共化要等 R6 的真实取消/恢复复现结果，当前不提前实现。
