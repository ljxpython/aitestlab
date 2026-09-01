## Why

R3 的归档记录把 Tool 错误和重试写成已装配，但当前 `reference_agent` 的真实组合根只接入了
Runtime 配置、调用上限和单次模型超时；官方 Tool Middleware 只有孤立单测，Agent 没有真实调用案例。
本轮需要收敛 R3 的可靠性证据，同时筛选 Open SWE 中真正适合 Runtime 的模式，避免把 Provider、Sandbox、
GitHub 或 Slack 业务逻辑误搬进公共层。

## What Changes

- **BREAKING** 在 `reference_agent` 的 `agent.py` 显式接入官方 `ToolRetryMiddleware` 和
  `ToolErrorMiddleware`，固定“重试耗尽后再转换明确可恢复错误”的顺序；未知异常、取消和中断继续传播。
- 在 Service 组合根中为模型 fallback/retry 留出显式、受策略约束的装配路径；使用官方
  `ModelFallbackMiddleware`/`ModelRetryMiddleware`，不叠加 Provider SDK retry，也不默认启用未经授权的模型。
- 增加真实 Agent graph 可触发的只读 Tool 案例，覆盖 Tool 临时失败重试、可恢复错误返回
  `ToolMessage(status="error")`、未知异常传播和模型故障 fallback/retry；案例使用确定性的 local test adapter，
  不伪装成真实 Provider 证据。
- 更新 15 号 Middleware 文档，增加 R3 Harness 对齐矩阵；每项标明 `是否实现`、代码、验证、测试、真实案例和
  Open SWE 取舍，区分已接线、仅有单测、后置和不适用。
- 保持 Runtime 的责任边界：不新增 Run deadline、durable finalizer、Auth Middleware、公共 Builder/Registry、
  通用 Dynamic Tool、Sandbox circuit breaker 或 Open SWE 的 GitHub/Slack 业务 Middleware。

## Capabilities

### New Capabilities

- 无。本变更只收敛已有 R3 Middleware 能力，不创建重复的 capability。

### Modified Capabilities

- `runtime-middleware-reliability`: 补充 Tool Error/Retry 的真实组合要求、模型 fallback/retry 的显式授权边界和案例验收。
- `runtime-agent-service-integration`: `reference_agent` 的组合根必须显式声明并实际调用 R3 可靠性 Middleware。

## Impact

- 代码：`apps/runtime-service/src/runtime_service/services/reference_agent/`，必要时补充最小公共 Middleware 导出。
- 测试：Reference Agent 组合/调用测试、Middleware 契约测试和真实模型测试说明。
- 文档：`15-runtime-middleware-lifecycle-and-failure-semantics.md`、R3 对齐审计和 Reference Agent README。
- 依赖：仅使用当前锁定的 `langchain==1.3.17` 官方 Middleware 与 Python 标准库，不新增依赖。
- 运行边界：默认生产路径仍要求已验证 Auth facts 和真实 Provider 凭据；fake model、fake Tool 只允许显式测试配置。
- 回滚：移除新增 Middleware 装配和测试案例即可恢复当前 R3 最小栈，无数据迁移。
