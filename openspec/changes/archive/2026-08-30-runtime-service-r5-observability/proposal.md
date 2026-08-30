## Why

R4 已完成 Runtime Agent Service 的 Tool、MCP、Backend、Skills 和 Subagents 能力，但当前没有统一的 Runtime Trace、结构化日志和指标边界，问题定位仍依赖临时输出。现在需要在不改变 Agent 业务结果、不把 Langfuse 当作 Run 状态库的前提下，建立 Runtime Service 的最小可观测能力。

## What Changes

- 新增 Runtime Service 的 Langfuse Callback 接入和安全 metadata 白名单。
- 在 Agent Service 入口统一关联 `request_id`、`thread_id`、`run_id`、`graph_id` 和 `trace_id`。
- 新增结构化日志事件，覆盖 Run、Model、Tool、Subagent、超时、取消和失败。
- 新增最小 Runtime 指标，覆盖成功、失败、超时、取消、Tool 错误、Token 和耗时。
- Langfuse 初始化、导出或网络故障采用 fail-soft，不改变 Agent 输入、输出和异常语义。
- 敏感 Prompt、模型响应、Tool 参数、凭据和超大 payload 不进入 Trace、日志或指标。
- 为 `reference_agent`、`deep_agent_demo`、`mcp_demo` 和 `backend_demo` 增加并发、脱敏和故障测试。
- **BREAKING**：Runtime 可观测字段只接受服务端可信 Runtime Context 和白名单 metadata，不再把任意 `RunnableConfig` metadata 作为身份或授权来源。

## Capabilities

### New Capabilities

- `runtime-observability`: Runtime Service 的 Langfuse Trace、结构化日志、指标、脱敏和 fail-soft 契约。

### Modified Capabilities

- `runtime-agent-service-integration`: Agent Service 在 `get_agent()` 返回 Graph 时显式绑定可观测配置，同时保留官方 Graph 构造和 Runtime Context 边界。

## Impact

- owning locus：`apps/runtime-service/src/runtime_service/observability/` 和各 Service 组合根；最短相邻链为 Runtime tests 和 LangGraph 启动配置。
- 不修改 `apps/platform-api`、`apps/platform-web`、数据库、Run Explorer 或 LangGraph 上游代理。
- 复用 LangChain Callback、现有 Runtime Context 和 `RunnableConfig`；不新增 Provider、Registry、Builder 或 Middleware 框架。
- 生产依赖 Langfuse 服务端配置；本地和单元测试使用 fake callback/exporter，不要求 Platform API。
- execution band：B3 Governed，原因是跨 Service 的公共可观测字段、敏感数据边界和故障语义发生变化。
