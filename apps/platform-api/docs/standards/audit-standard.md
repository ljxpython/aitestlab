# Platform API 审计标准

这份文档定义 `platform-api` 的审计标准。它不是 access log 美化版，而是能真的回答“谁在什么时间对哪个资源做了什么”的那种审计。

## 1. 审计目标

审计系统必须满足：

- 可追责
- 可检索
- 可分页
- 可做平台治理统计
- 可支撑后续 worker / queue / 分布式演进

## 2. plane 标准

后续统一只允许 3 类 plane：

- `control_plane`
- `runtime_gateway`
- `system_internal`

禁止再把控制面流量误记成 `runtime_proxy`。

## 3. action 命名标准

action 统一使用：

`{domain}.{resource}.{verb}`

示例：

- `identity.session.created`
- `identity.password.changed`
- `project.member.removed`
- `agent.updated`；历史 `assistant.updated` 仅作为旧审计记录的读取兼容
- `catalog.graph.refresh_requested`
- `runtime.thread.cancelled`
- `user.credentials.reset`
- `project.project.archived`
- `project.project.restored`
- `project.takeover.completed`
- `service_account.project_grant.upserted`

禁止继续用一大片 `http.request` 糊弄过去。

## 4. 审计事件字段

最小字段集必须有：

- `request_id`
- `plane`
- `action`
- `target_type`
- `target_id`
- `actor_user_id`
- `actor_subject`
- `tenant_id`
- `project_id`
- `result`
- `status_code`
- `duration_ms`
- `created_at`

可选增强字段：

- `client_ip`
- `user_agent`
- `operation_id`
- `trace_id`
- `metadata`

## 5. 事件写入时机

### 5.1 同步请求

默认在请求完成后写入一条结果事件：

- 成功写 `success`
- 失败写 `failed`
- 取消或中断写 `cancelled`

### 5.2 异步任务

operation/job 必须单独记录生命周期事件：

- `submitted`
- `started`
- `succeeded`
- `failed`
- `cancelled`

## 6. 查询标准

审计查询必须是真分页，不能再搞“先查 5000 条回来再 Python 过滤”这种土办法。

至少支持这些筛选：

- 时间范围
- plane
- action 前缀
- actor
- project_id
- result

默认排序：

- `created_at desc`
- 二级排序 `id desc`

## 7. 脱敏与隐私

这些内容禁止原文落审计：

- 密码
- token
- cookie
- 原始密钥
- 完整 Authorization header

需要记录时只能做掩码或 hash 摘要。

项目接管允许在 metadata 中记录非空 `reason`。审计 metadata 采用允许列表，
不得因为“方便排查”直接复制请求体。租户归属固定使用服务端默认租户，不能使用
客户端提交的 `x-tenant-id`。

## 8. 代码落点

推荐收敛：

- `modules/audit/domain/`：事件模型
- `modules/audit/application/`：查询 use case
- `modules/audit/infra/`：repository / writer
- `core/`：request_id、trace、公共 helper

handler 层只负责传上下文，不直接拼审计 payload。

## 9. 分布式演进

后续接 Redis、queue 或消息总线时，审计不能重写协议，只允许替换写入通道：

- 当前：直写数据库
- 后续：DB + outbox / queue sink

事件 schema 保持不变，这样前端查询和治理报表不会跟着炸。
