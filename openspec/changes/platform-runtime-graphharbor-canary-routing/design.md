## Context

`platform-api` 当前在 `get_runtime_gateway_service()` 中根据单一
`settings.langgraph_upstream_url` 创建 `LangGraphRuntimeGatewayUpstream`。它已有
`runtime_runs`、idempotency 和 platform config 持久化，但 durable record 没有 upstream
归属字段。GraphHarbor 的执行面已经拥有自己的 Run/Event/Checkpoint 事实源，因此控制面
必须保留跨 upstream 的路由映射，不能让客户端或 GraphHarbor 自己决定灰度。

本变更是 B3 Governed，影响路由、数据所有权、migration、回滚和 runtime gateway 公共行为。

## Goals / Non-Goals

**Goals:**

- 在不改变默认流量的前提下，对新 Run 提供稳定、可回滚的 legacy/GraphHarbor 选择。
- 让同一 Run 的所有后续请求始终回到创建时的 upstream。
- 让路由策略、决策原因、版本和回滚状态可审计、可观测、可测试。
- 与 GraphHarbor 的 delegation JWT、idempotency 和 durable Run 契约一致。

**Non-Goals:**

- 不在 platform-api 内复制 GraphHarbor Worker、Checkpoint、Event 或 SSE 实现。
- 不让客户端选择 `runtime_route`，不通过请求体或普通 header 绕过策略。
- 不在 upstream 超时后自动跨路由重试，不迁移旧 runtime 数据。
- 不在本变更中删除 legacy runtime 或宣布生产切换完成。

## Decisions

### 1. `platform-api` owns selection and GraphHarbor only executes

新增 Run 的路由选择放在 `runtime_gateway`，GraphHarbor 只验证 delegation JWT 并执行
业务 graph。这样灰度、权限和回滚仍在控制面，避免两个系统各自做一套路由判断。

### 2. Durable Run record stores the route

为 `runtime_runs` 增加 `runtime_route`，允许值为 `legacy` 或 `graphharbor`，对已有记录
回填 `legacy`。创建 durable record 时先完成路由决策，再调用 upstream；upstream 返回的
`run_id` 与 route 一起持久化。所有带有 `run_id` 的后续操作先读取 durable record，按
记录构造 upstream client。

### 3. Deterministic selection, one decision per idempotency key

百分比选择使用标准库 `hashlib.sha256` 对规范化的
`tenant_id/project_id/thread_id/idempotency_key` 做稳定 hash；允许列表优先于百分比，
全局 disable 优先级最高。相同 idempotency key 只返回原 record，不重新计算。百分比只
控制新 Run，不修改已有 record。

### 4. No cross-route automatic fallback

upstream 调用可能已经创建 Run 时，跨路由 fallback 会造成重复执行和重复副作用。因此
超时/5xx 只按原 route 处理，并依靠现有 idempotency/retry 语义；只有明确的“尚未发送”
配置/连接错误才可在调用前返回错误，不隐式改投另一 upstream。

### 5. Configuration is separate from credentials

legacy URL、GraphHarbor URL、percentage、allowlists 和 policy version 进入受权限保护的
platform config；delegation secret/JWKS 继续由环境或 secret manager 提供。配置 snapshot
只返回 URL 的非敏感标识和 masked state，不返回 token 或 key。

## Risks / Trade-offs

- [旧记录缺少 route] -> migration 中统一回填 `legacy`，并在代码层对 null fail-closed。
- [百分比变化造成流量跳变] -> 使用稳定 scope hash、分阶段只允许 `0/1/10/50/100`，并
  记录 policy version。
- [upstream 超时导致未知状态] -> 原 route + 原 idempotency key 重试，禁止跨路由复制。
- [GraphHarbor 认证配置不一致] -> 启动/ready 检查比较 delegation issuer/audience，失败
  时不允许启用 GraphHarbor route。
- [共享数据库 migration 回滚风险] -> 先向前兼容新增 nullable 字段并回填，再切换为
  非空；代码 rollback 保留字段，禁止直接 downgrade 生产 schema。

## Migration Plan

1. 增加 nullable `runtime_route` 字段和索引，回填历史记录为 `legacy`，验证可重复执行。
2. 发布兼容代码：读取 null 时按 `legacy`，写入新 route；此时 GraphHarbor 百分比保持 0。
3. 配置两个 upstream 和 delegation JWT audience，启动 readiness/metrics/审计检查。
4. 依次执行 `0% -> 1% -> 10% -> 50% -> 100%`，每阶段检查成功率、p95、queue lag、
   checkpoint latency、SSE replay、跨租户错误和 exporter failures。
5. 回滚时只将新分配策略设为 legacy；保留既有 `runtime_route`，等待或恢复进行中的
   GraphHarbor Run。
6. 只有 GraphHarbor change 的所有硬门槛、platform-api 路由门槛和 owner approval 都
   通过后，才允许将 100% 作为正式默认路径。

## Open Questions

- platform config 是沿用现有 boolean feature flag，还是增加专用 typed runtime route
  配置表；实现前需要与平台配置 owner 确认审计和并发更新语义。
- legacy 与 GraphHarbor 的跨系统 Run 查询是否需要在运维 API 显式返回 route 和 upstream
  run id；默认应返回脱敏标识，避免暴露内部地址。
- 生产 GraphHarbor 使用 JWKS 还是共享 secret；两端必须在 deployment manifest 中固定。
