## Context

`platform-api` 的 `runtime_gateway` 已经负责 Durable Run 预留、上游 `run_id` 绑定、取消、
interrupt 和终态同步，但当前只有 `runtime_runs` 与 `runtime_run_interrupts`，没有平台自己的
历史事件流。SSE 代理保留的是 LangGraph 上游 `last_event_id`，不能直接承担平台历史查询和
断线补发。

本变更跨越 `runtime_gateway`、`audit`、`operations`、LangGraph adapter 和 `platform-web`，
涉及数据库迁移、公共 HTTP API、项目权限和敏感数据边界，因此按 B3 Governed 执行。

## Goals / Non-Goals

**Goals:**

- 建立平台自己的 Run 事件信封、事件字典、顺序和 at-least-once 幂等语义。
- 让生命周期事件与 Run 状态在同一事务内保持一致。
- 提供使用 cursor 分页的 Run 列表、详情和事件查询 API。
- 以平台 `event_id/sequence` 支持 SSE 补发和历史/实时去重。
- 在项目权限边界内聚合 Audit、Operation 和 Langfuse 摘要，并对外部数据源 fail-soft。
- 保持 Runtime Service 不直接访问平台数据库，降低跨服务耦合。

**Non-Goals:**

- 不复制完整 Prompt、模型响应、Token 流或 Tool 参数。
- 不把 Langfuse、Prometheus、Loki 作为 Run 状态事实源。
- 不重写现有 `/api/langgraph` 上游兼容代理。
- 不在本变更中实现独立 Admin 后端、完整 Trace UI 或 OpenTelemetry parent 传播。
- 不承诺 exactly-once 事件投递或跨区域全局顺序。

## Decisions

### 1. Platform API 作为平台事件写入边界

`runtime_gateway` 生成并持久化 Run 生命周期事件；Runtime Service 不直接写数据库。这样可
在权限上下文、`runtime_runs`、`operations` 和事件表之间做单事务更新。执行细节事件未来
通过内部受认证入口投递，仍由 Gateway 规范化后写入。

替代方案：Runtime 直接连接平台数据库会减少 HTTP 代码，但破坏所有权、扩大数据库凭据
暴露面，并使租户校验分散到执行层，拒绝采用。仅解析前端 SSE 也无法覆盖无订阅者或断线
场景，因此只作为补充来源。

### 2. 平台自有 `event_id + sequence`

`event_id` 是幂等和客户端去重标识；`sequence` 是同一 Run 内由平台事件仓储分配的规范游标。
LangGraph 的 `last_event_id` 只用于上游代理，不进入平台事件排序。可选的
`source_event_id/source_sequence` 只用于追踪原始来源。

替代方案：直接透传上游事件 ID 无法统一 Platform API 生成的生命周期事件，也无法保证多个
来源共享连续游标，拒绝采用。

### 3. 生命周期事件事务化，细节事件可丢弃

`run.submitted/started/interrupted/resumed/cancel_requested/cancelled/completed/failed` 与
Run/Operation 状态更新在同一数据库事务中完成。普通执行细节事件采用 at-least-once，队列
满或外部存储暂时不可用时可以丢弃，但必须记录结构化日志和 metrics，不能阻塞 Agent。

### 4. 平台原生查询 API 与兼容代理并存

新增 `/api/runtime/runs` 查询域；现有 `/api/langgraph` 继续作为 LangGraph SDK 兼容代理。
Run 列表使用 cursor 分页，事件查询使用 `after_sequence`，详情只返回有限时间线和各数据源
摘要，避免一次请求加载完整 Trace。

### 5. 外部数据源部分返回

Run 核心记录、平台事件和权限校验失败时接口失败；Langfuse、Audit、Operation、日志或指标
摘要单独失败时返回空摘要和 `source_status`。浏览器不直接持有任何外部系统凭据。

### 6. 事件信封、状态转移与查询路由

事件信封的规范字段为 `event_id`、`event_version`、`run_id`、`thread_id`、`sequence`、
`event_type`、`occurred_at`、`source`、可选节点/工具字段、`status`、`safe_metadata` 和
`correlation`。生命周期事件由 Gateway 与 `runtime_runs`/`operations` 状态在同一事务中
提交；同一 Run 的序号由仓储分配，使用 `(run_id, sequence)` 唯一约束和来源幂等键。

项目用户使用 `/api/runtime/runs`、`/{run_id}`、`/{run_id}/events`；平台管理员使用独立的
`/api/admin/runtime/runs` 查询跨项目元数据。Run 列表采用 `created_at + id` cursor，事件
采用 `after_sequence` 升序分页。平台 SSE 后续复用同一事件信封，`Last-Event-ID` 只表示
平台 `event_id`，不透传 LangGraph 上游游标。

替代方案：把项目和全局查询合并为带 `scope=all` 的单一路由，会让权限遗漏更容易发生；把
上游 `last_event_id` 作为平台游标，会导致生命周期事件和 Runtime 事件无法共享顺序；两者
均拒绝采用。

## Risks / Trade-offs

- [事件写入与上游状态短暂不一致] -> 终态同步保留对账路径；生命周期事件和状态使用同一事务。
- [执行细节事件丢失] -> 只将其用于辅助时间线，记录丢弃计数；Run 核心状态不依赖细节事件。
- [事件表增长过快] -> 仅保存白名单事件和安全摘要，按保留策略归档/清理，并限制分页窗口。
- [外部查询延迟拖慢详情] -> 为每个 adapter 设置独立超时，串行/并行策略由实现验证决定，失败立即标记来源状态。
- [cursor 失效或重复] -> cursor 编码最后一条 `created_at + id`，服务端验证版本和项目范围，非法 cursor 返回 400。
- [管理员全局查询绕过项目隔离] -> 使用独立 `/api/admin/*` 路由，并在每次详情/事件查询中重新执行平台权限校验。
- [SSE 历史与实时重复] -> 统一使用 `event_id` 去重，并按 `sequence` 补发；前端不得按时间戳去重。

## Migration Plan

1. 增加 `runtime_runs` 可空关联字段和 `runtime_run_events` 表、索引、唯一约束；不改变现有路由行为。
2. 在 `runtime_gateway` 写入 `run.submitted/started`，再补充 interrupt、cancel 和终态事件。
3. 增加 `/api/runtime/runs` 列表、详情和事件接口，先只返回平台数据。
4. 接入 Audit、Operation 和 Langfuse 摘要 adapter，落实 `source_status` 和超时。
5. 增加 SSE 按 `Last-Event-ID` 补发的内部实现，保留现有 LangGraph 代理兼容行为。
6. `platform-web` 接入 Run Explorer 和 Admin 路由；旧页面保留兼容跳转。

回滚策略：先停止新查询路由和细节事件写入，保留 `runtime_runs` 原有状态机；新增字段可
保持为空，事件表可只读或按迁移工具回滚。不得删除已有 Run 数据或修改 LangGraph 上游状态。

## Open Questions

- Runtime 细节事件入口最终采用内部 HTTP、队列还是仅由 Gateway 解析上游事件？
- 事件表保留期限和归档策略由哪个平台配置模块负责？
- Langfuse Trace 摘要是返回内部跳转 URL，还是返回服务端签发的短时 token？
- 详情接口的 Audit/Operation/Trace adapter 是否并行执行，需要锁定统一超时值。
