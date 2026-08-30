## ADDED Requirements

### Requirement: 平台事件必须使用稳定事件信封
平台 MUST 为每条 Run 事件提供 `event_id`、`event_version`、`run_id`、`thread_id`、`sequence`、
`event_type`、`occurred_at`、`source` 和脱敏后的 `safe_metadata`。事件不得包含完整 Prompt、
模型响应、Token 流、Tool 参数、凭据或私有源码。

#### Scenario: 写入生命周期事件
- **WHEN** `runtime_gateway` 将 Run 标记为终态
- **THEN** 同一事务写入包含完整信封的 `run.completed`、`run.failed` 或 `run.cancelled` 事件

#### Scenario: 拒绝敏感事件元数据
- **WHEN** 事件 metadata 包含 Authorization、API key、Cookie 或完整消息正文
- **THEN** 系统删除或拒绝该字段，并且不得将明文保存到 `runtime_run_events`

### Requirement: 事件顺序和幂等必须由平台维护
平台 MUST 为同一 `run_id` 分配单调递增的 `sequence`，并通过 `event_id` 及来源幂等键
防止重复事件。系统 MUST 采用 at-least-once 语义，不得声称 exactly-once。

#### Scenario: 重复投递同一事件
- **WHEN** Runtime 因网络重试再次投递相同来源和来源事件 ID
- **THEN** 系统返回幂等成功，事件表只保留一条记录，`sequence` 不发生变化

#### Scenario: 同一 Run 并发写入事件
- **WHEN** 两个请求同时为同一个 Run 写入事件
- **THEN** 系统提交后的 `sequence` 唯一且可排序，不产生重复游标

### Requirement: 生命周期事件必须与 Run 状态一致
`run.submitted`、`run.started`、`run.interrupted`、`run.resumed`、`run.cancel_requested`、
`run.cancelled`、`run.completed` 和 `run.failed` MUST 由 Platform API 生成，并与对应的
`runtime_runs`/`operations` 状态更新使用同一事务或可验证的重试对账机制。

#### Scenario: 终态事件写入失败
- **WHEN** `runtime_runs` 终态更新或对应事件写入失败
- **THEN** 事务不对外宣称成功，且系统记录可重试的对账信号

#### Scenario: 细节事件暂时不可用
- **WHEN** 非生命周期的执行细节事件队列已满
- **THEN** 系统可以丢弃该细节事件，但 Run 执行继续，且结构化日志和 metrics 记录丢弃

### Requirement: 平台事件流必须支持历史补发
平台事件查询和 SSE MUST 使用平台 `sequence`/`event_id`，支持 `after_sequence` 或
`Last-Event-ID` 补发。未知事件类型 MUST 被忽略而不是终止整个流。

#### Scenario: 客户端断线重连
- **WHEN** 客户端携带最后收到的 `event_id` 重新连接
- **THEN** 服务端只补发该事件之后的事件，并按 `sequence` 升序发送

#### Scenario: 历史和实时事件重叠
- **WHEN** 客户端先加载历史事件，再接收同一事件的实时推送
- **THEN** 客户端可通过 `event_id` 去重且不会出现重复时间线项

### Requirement: 生命周期事件必须遵守合法状态转移
平台 MUST 拒绝终态后的新生命周期事件，并且 MUST 区分 `run.cancel_requested` 与
`run.cancelled`。`run.interrupted` 和 `run.resumed` 必须分别表示进入和离开等待状态。

#### Scenario: 终态后重复完成
- **WHEN** 已经处于 `succeeded` 的 Run 再次收到 `run.completed`
- **THEN** 系统按幂等成功返回已有事件，不新增 sequence，也不改变终态

#### Scenario: 非法恢复
- **WHEN** `run.resumed` 对应 Run 当前不是 `waiting`
- **THEN** 系统拒绝状态转换并记录冲突，不写入产品事件时间线

### Requirement: 事件来源幂等冲突必须可识别
当相同来源和 `source_event_id` 已存在但 payload 不一致时，平台 MUST 返回明确的
`event_idempotency_conflict`，不得静默覆盖原事件。

#### Scenario: 相同来源键不同内容
- **WHEN** Runtime 使用已存在的 `source_event_id` 投递不同事件类型
- **THEN** 系统拒绝该投递并记录冲突审计/日志，原事件保持不变
