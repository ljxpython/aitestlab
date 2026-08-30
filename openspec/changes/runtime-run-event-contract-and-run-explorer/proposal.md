## Why

当前 `runtime_gateway` 已持久化 Durable Run 和 Operation，但没有平台自己的运行事件时间线；
SSE 仍直接依赖 LangGraph 上游游标，平台无法稳定支持历史查询、断线补发、跨数据源聚合和
Admin 运维查看。现在补齐事件契约和 Run Explorer，可以在不把 Langfuse 变成事实源的前提下，
建立可授权、可审计、可降级的平台查询边界。

## What Changes

- 新增平台级 `runtime_run_events` 事件模型，定义事件信封、事件字典、`event_id`、`sequence`、
  版本和 at-least-once 幂等语义。
- 扩展现有 `runtime_runs` 的关联字段，支持 assistant、graph、request、trace 和终态查询。
- 由 `runtime_gateway` 事务化写入 Run 生命周期事件；为 Runtime 执行细节预留受认证的内部投递边界。
- 新增平台原生 Run Explorer 查询接口：Run 列表、Run 详情和事件分页查询。
- 使用平台自己的 `event_id/sequence` 支持 SSE 历史补发和实时事件去重，不复用 LangGraph 的上游游标。
- 聚合 Audit、Operation、Langfuse Trace 摘要和日志/指标摘要，外部数据源失败时返回部分结果和
  `source_status`。
- 增加项目级、平台级权限校验、脱敏规则和 Admin 接管审计要求。
- **BREAKING**：平台原生查询接口不承诺返回完整 Prompt、模型响应或 Tool 参数；这些内容不再作为
  平台事件数据保存。

## Capabilities

### New Capabilities

- `runtime-run-events`: 平台 Run 事件信封、生命周期事件、幂等、顺序、持久化和 SSE 补发语义。
- `run-explorer-api`: Run 列表、详情、事件分页、跨模块摘要聚合、权限和部分失败响应。

### Modified Capabilities

无。

## Impact

- owning locus：`apps/platform-api/app/modules/runtime_gateway`；最短相邻链为 `audit`、
  `operations`、LangGraph adapter 和 `apps/platform-web`。
- 数据库：扩展 `runtime_runs`，新增 `runtime_run_events`、唯一约束和索引；需要可回滚迁移。
- API：新增 `/api/runtime/runs`、`/api/runtime/runs/{run_id}` 和 `/api/runtime/runs/{run_id}/events`。
- Runtime Service：首期不直接访问平台数据库；后续执行细节事件通过内部受认证入口投递。
- 前端：为 Run Explorer 和 Admin 路由使用平台 API 的固定响应结构，不直连 Langfuse、Loki 或 Prometheus。
- 依赖：复用现有 SQLAlchemy、IAM、Audit、Operation 和 LangGraph adapter，不新增观测平台 SDK。
- execution band：B3 Governed；原因是公共 API、数据库迁移、权限和跨模块所有权发生变化。
