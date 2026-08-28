## ADDED Requirements

### Requirement: 正式运行以 Durable Run 作为唯一资源

系统 MUST 通过 `platform-api` 为正式 Agent Web 提供 thread-scoped Durable Run 的查询、取消和
状态恢复，并以 Protocol v2 `run.start`/`input.respond` 创建或恢复执行、以 Protocol v2 event
stream 观察事件。浏览器 MUST NOT 直连 runtime-service，也 MUST NOT 使用 legacy 创建并隐式
流式返回的接口作为生产 fallback。platform-api MUST 从已认证 actor 和 project scope 构建可信运行上下文。

#### Scenario: 已授权用户创建 Run
- **WHEN** 有 thread write 权限的用户在已选 project 为该 thread 提交合法创建请求
- **THEN** platform-api 接受或拒绝 `run.start`，后台 Durable Run 独立于浏览器执行，并且 runtime 收到的可信身份、项目和策略只来自服务端

#### Scenario: 越权创建被拒绝
- **WHEN** actor 没有 project/thread write 权限，或请求夹带身份、project、role 或 permissions 字段
- **THEN** platform-api 拒绝请求且不向 runtime 创建 Run

### Requirement: 创建 Run 保持幂等且可检测冲突

正式创建请求 MUST 在 HTTP `Idempotency-Key` header 提供跨网络重试边界的幂等键。gateway MUST
为 Protocol v2 `run.start` 记录该键与规范化请求摘要，并按 `(project_id, thread_id, idempotency_key)` 唯一化。
相同 key 和摘要 MUST 返回同一 Run；相同 key 与不同摘要 MUST 返回确定的冲突错误。客户端 command
`id` 只用于协议关联，MUST NOT 被视为持久幂等键；gateway MUST NOT 将 HTTP 幂等键转发到
Protocol v2 payload 或 runtime config。

#### Scenario: 客户端在创建响应超时后重试
- **WHEN** 客户端以相同 idempotency key 和等价请求再次创建同一 thread 的 Run
- **THEN** 系统返回原有 `run_id`，且 Agent 只执行一次

#### Scenario: idempotency key 被不同请求复用
- **WHEN** 客户端复用已关联不同请求摘要的 idempotency key
- **THEN** 系统返回 `idempotency_key_conflict`，且不修改原有 Run

### Requirement: Run 标识、并发与恢复目标必须确定

`run.start` success result MUST 包含可解析的 `run_id`。系统 MUST 拒绝同一 thread 在已有非终态
Run 时创建第二个 active Run。`input.respond` MUST 使用服务端声明的 interrupt ID，且 gateway
MUST 验证该 interrupt 属于当前 active Run；系统 MUST NOT 通过查询 thread 最新 Run、前端数组
索引或 thread 本身推断运行或恢复目标。

#### Scenario: 同一 thread 并发创建
- **WHEN** 用户在已有 queued、running 或 waiting_for_input Run 的 thread 发起新的 `run.start`
- **THEN** gateway 返回确定冲突且不创建第二个 Run，现有事件时间线不发生串写

#### Scenario: 多 interrupt 精确恢复
- **WHEN** 同一 thread 暴露多个未解决 interrupt
- **THEN** 用户提交的 `input.respond` 只恢复匹配 interrupt ID 的 active Run，其他 interrupt 与 Run 保持不变

### Requirement: SSE 订阅只观察并可恢复 Durable Run

系统 MUST 通过 Protocol v2 `POST /threads/{thread_id}/stream/events` 提供授权事件订阅。客户端以
Bearer `fetch + ReadableStream` 请求该 endpoint，并以 body 内最后确认的 `seq` 作为 `since`
恢复；系统 MUST 先交付未消费的可重放事件再交付实时事件。浏览器断线、刷新或 gateway
subscription 失败 MUST NOT 修改 Durable Run 成功、失败或取消状态。

#### Scenario: 页面刷新恢复运行观察
- **WHEN** 用户刷新仍处于非终态的 Run 页面
- **THEN** 客户端先查询 Run snapshot，再以最后确认 `seq` 提交 Protocol v2 event subscription，且不重新创建 Run

#### Scenario: 已重放事件重复到达
- **WHEN** 客户端收到已确认 event `seq` 的重放事件
- **THEN** 客户端和服务端投影保持幂等，不重复消息、工具卡片或状态迁移

### Requirement: Run 终态与恢复由服务端确认

runtime-service MUST 在 durable checkpoint 同步后写 Run 终态，再发布 completed/failed event。
cancel MUST 作用于明确 run id；resume MUST 以未解决 interrupt ID 为目标并校验其所属 active Run。
客户端 MUST 通过 Run snapshot 确认终态，不能以 SSE 最后一帧或网络关闭推断成功。

#### Scenario: 用户取消 active Run
- **WHEN** 有 write 权限的用户取消 running Run
- **THEN** 系统请求服务端取消并最终返回 cancelled/interrupted 或确定失败 snapshot，客户端恢复可编辑状态

#### Scenario: Worker 在 checkpoint 后重启
- **WHEN** worker 在持久 checkpoint 后重启
- **THEN** 系统恢复同一 Run 或将它写入确定 failed 状态，且不会创建第二个 Run

### Requirement: 每个 Durable Run 映射 project operation 与审计生命周期

platform-api MUST 将每个 Durable Run 一对一映射为同 project 的 operation。operation 与 audit
MUST 覆盖 submitted、started、succeeded、failed、cancelled 和 resumed，并关联 project、actor、
thread、run 与 operation。审计、operation payload 与诊断日志 MUST NOT 保存 Bearer token、
Authorization header 或完整用户输入。

#### Scenario: Run 生命周期可追责
- **WHEN** 已授权用户创建、恢复、取消或完成 Durable Run
- **THEN** 系统写入对应 operation 状态与 runtime run 审计事件，且记录可按 project、actor、thread、run 和 operation 查询

### Requirement: Durable Run 契约具有固定 DTO、状态、错误和保留规则

gateway 的持久 Durable Run DTO MUST 仅包含 `id`、`project_id`、`thread_id`、`idempotency_key`、
`request_digest`、`run_id`、`operation_id`、`status`、`active`、`created_at` 和 `updated_at`。其中
`request_digest` 是规范化 Protocol v2 command 的摘要，MUST NOT 是完整输入的可恢复副本。持久状态
MUST 限定为 `submitted`、`running`、`succeeded`、`failed`、`cancelled`；上游 snapshot 的 `success`
映射为 `succeeded`，`error`、`failed`、`timeout` 映射为 `failed`，`cancelled`、`interrupted` 映射为
`cancelled`。非终态不得释放同 thread active slot。

`run.start` MUST 使用 HTTP `Idempotency-Key`，并返回 Protocol v2 success envelope 的 `result.run_id`。
最小可归一化错误码 MUST 包括 `idempotency_key_required`、`invalid_idempotency_key`、
`idempotency_key_conflict`、`run_start_in_progress`、`thread_active_run_conflict`、
`protocol_run_id_missing`、`interrupt_id_required` 与 `interrupt_not_active`。HTTP 幂等键不得进入
Protocol payload。

本阶段 MUST NOT 自动删除 Durable Run、幂等记录、operation 或审计证据；retention/归档/删除策略
属于后续受治理 change，必须先定义合规期限、审计可查询性和恢复影响并获得独立批准。

#### Scenario: 已终态 Run 保留用于审计与幂等查询
- **WHEN** Run 已经成功、失败或取消
- **THEN** gateway 释放该 thread 的 active slot，但保留 Durable Run、operation、请求摘要和审计关联，
  不执行自动删除
