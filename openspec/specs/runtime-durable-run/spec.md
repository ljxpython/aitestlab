# runtime-durable-run Specification

## Purpose

定义 Runtime Service 基于通用 Agent Server 的 Durable Run、Thread/Workspace 资源边界、
事件恢复、严格 RuntimeContext、外部 PostgreSQL/Redis 部署和通用可观测关联契约。
本规范不把 Runtime 专属的 Sandbox Provider、MCP Registry、Langfuse 业务逻辑或 Platform
控制面写入 GraphHarbor。

## Requirements

### Requirement: Runtime SHALL persist and recover durable runs through Agent Server

Runtime Service SHALL 使用 Agent Server 原生的 Thread、Run 和 Checkpoint 生命周期，并使用
`durability="sync"`。恢复 Run 必须继续使用原始 `thread_id` 以及有效的 checkpoint 或
interrupt resume 输入；Runtime 不得另建第二套持久化状态机。

#### Scenario: Sync checkpoint survives worker restart
- **WHEN** Run 到达已持久化的 super-step 后 Worker 被终止
- **THEN** 新 Worker 使用同一个 `thread_id` 从最近的有效 checkpoint 恢复，并最终只产生一个终态

#### Scenario: Invalid checkpoint is rejected
- **WHEN** resume 请求指定不存在、属于其他 Thread 或格式错误的 checkpoint
- **THEN** Runtime 返回稳定的恢复错误，并且不得使用其他 Thread 的状态执行

### Requirement: Runtime SHALL support precise interrupt and resume semantics

Runtime Service MUST 让 interrupt 暴露足够的 Run/checkpoint 身份信息，使调用方能够恢复同一执行范围。多个
interrupt 必须按顺序恢复，客户端断开连接不得隐式恢复或取消 Run。

#### Scenario: Resume after interrupt
- **WHEN** Run 发生 interrupt，调用方为同一 Thread 提交有效的 resume 输入
- **THEN** 执行从已记录的 interrupt 边界继续，并只产生一个终态事件

#### Scenario: Repeated interrupt remains ordered
- **WHEN** Graph 在完成前多次 interrupt
- **THEN** 每次 resume 都在同一个 Run 中按顺序推进，不跳过也不重放之前的 checkpoint

### Requirement: Runtime SHALL provide resumable and deduplicated event streams

Runtime 事件流 SHALL 提供按 Run 单调递增的 cursor。重连可以携带 `since` 回放事件；消费者必须
按 `(run_id, seq)` 去重。流关闭不得改变 Run 状态。

#### Scenario: SSE reconnect replays missing events
- **WHEN** SSE 连接在 cursor `n` 后关闭，客户端使用 `since=n` 重连
- **THEN** 服务按顺序发送之后仍保留的事件，不重复发送已经确认的事件

#### Scenario: Cursor is outside retention
- **WHEN** 重连请求的 cursor 已超出保留范围
- **THEN** 服务返回明确的 cursor-expired 结果，并指引调用方通过 Run snapshot 恢复

### Requirement: Runtime SHALL converge cancellation and failures to one terminal state

Runtime MUST 让取消、超时、Tool failure、优雅 drain 和硬关机都收敛到确定的终态。每个 Run 最多允许
一个终态事件，终态事件之后不得再产生普通事件。

#### Scenario: Client disconnect does not cancel
- **WHEN** SSE 观察者在 Run 执行期间断开连接
- **THEN** Run 按实际执行继续保持 active 或完成，调用方可以通过回放或 snapshot 再次观察

#### Scenario: Cancel wins before completion
- **WHEN** 有效 cancel 在终态转换前到达 active Run
- **THEN** Run 恰好一次变为 cancelled，后续 cancel 请求保持幂等

#### Scenario: Tool failure is terminal when unrecoverable
- **WHEN** Tool 在不允许重试时失败且 Graph 无法继续
- **THEN** Run 以稳定错误类别变为 failed，不产生 success 终态事件

### Requirement: Thread-scoped resources SHALL remain isolated and recoverable

Runtime Service SHALL 从已序列化且已验证的 Thread 事实中选择附加到 Thread 的 Backend、Workspace、MCP client 或 Sandbox，
并在重连时 fail-closed。资源失败不得回退到其他 Thread 或宿主机目录。

#### Scenario: Two Threads do not share Workspace state
- **WHEN** 两个 Thread 使用不同资源标识并发运行
- **THEN** 每个 Run 只能读写自己的资源范围

#### Scenario: Resource reconnect fails closed
- **WHEN** Worker 重启且记录的 Thread 资源无法重新打开
- **THEN** Run 以资源恢复错误失败，不得使用备用资源

### Requirement: Runtime SHALL expose a Platform-independent durable smoke path

Runtime 仓库 SHALL 提供不调用 Platform API 的本地 smoke 路径，使用仅用于测试的 Delegation
Token signer、真实 Agent Server 以及隔离的 PostgreSQL/Redis。该路径必须覆盖 Auth、Resolver、
Graph、Checkpoint、Stream 和终态。

#### Scenario: Local smoke executes a real durable run
- **WHEN** smoke 环境使用有效的本地测试 secret 启动
- **THEN** 它创建 Thread、运行 `reference_agent`、重连事件流并校验最终 Run snapshot

#### Scenario: Missing infrastructure is reported explicitly
- **WHEN** PostgreSQL、Redis、Worker 或必需测试配置不可用
- **THEN** Durable 测试标记为未执行或失败，并给出明确前置条件错误，不得报告为通过

### Requirement: Runtime SHALL support explicit external infrastructure deployment

Runtime 部署 MUST 提供 host-infra 模式，只启动 API、Worker 和 migration 容器。该模式不得声明
PostgreSQL 或 Redis service、volume 或 `depends_on`，且 API、Worker 和 migration 必须使用同一组
显式配置的外部 `DATABASE_URI` 与 `REDIS_URI`。

#### Scenario: Host-infra compose uses registered services
- **WHEN** host-infra 部署使用有效的外部 PostgreSQL 和 Redis URI 渲染
- **THEN** 只声明 Runtime 容器，且三个角色收到相同的外部 endpoint

#### Scenario: Host-infra compose rejects implicit infrastructure
- **WHEN** 检查 host-infra compose
- **THEN** 不存在 PostgreSQL/Redis service、数据 volume 或基础设施依赖

### Requirement: RuntimeContext SHALL use one strict producer/consumer contract

API producer 和 Worker consumer SHALL 一致使用严格签名的 RuntimeContext envelope schema，包括
身份、scope、Run/Thread 绑定、过期时间、issuer/audience 以及生产所需的 policy 字段。未知的
顶层或嵌套 claim 必须 fail-closed；Runtime 专属 context 字段必须留在 GraphHarbor 通用 envelope
契约之外。

#### Scenario: Valid context crosses the Worker boundary
- **WHEN** API 为同一个 Run 和 Thread 签发 context，Worker 对其验证
- **THEN** Worker 收到相同的规范化身份、scope 和 policy 事实

#### Scenario: Unknown context claim is rejected
- **WHEN** envelope 含有未识别的顶层或嵌套 claim
- **THEN** 验证返回稳定的 context 错误，Run 不得执行

### Requirement: Agent Server SHALL recover on same-port API restart

Agent Server MUST 在 API 进程收到 SIGTERM 后于配置的 grace period 内退出，并让替代进程能够在同一个显式请求
的 host/port 上绑定，并在有界 readiness timeout 内可用。CLI 不得为显式请求的端口静默替换随机端口。

#### Scenario: API restarts on the requested port
- **WHEN** ready API 收到 SIGTERM 后，替代 API 使用相同 host 和 port 启动
- **THEN** 替代进程在验收超时内通过同一端口提供 `/ready`

#### Scenario: Port conflict is explicit
- **WHEN** 显式请求的端口仍被其他进程占用
- **THEN** 启动以清晰的 bind error 失败，而不是公布另一个端口

### Requirement: Generic observability SHALL preserve correlation and fail soft

GraphHarbor SHALL 在 Runtime 契约提供 `request_id`、`run_id`、`thread_id` 和 `graph_id` 时，在
API、queue、Worker 和事件边界保留这些通用关联字段。telemetry exporter 失败或有界队列饱和
不得阻塞或改变 Run 执行，丢弃 telemetry 必须通过稳定指标或日志信号可观测。

#### Scenario: Correlation survives Worker execution
- **WHEN** 带有关联信息的 Run 入队并由其他 Worker 执行
- **THEN** 通用关联字段仍可在 Worker trace/event 边界取得

#### Scenario: Exporter failure does not fail the Run
- **WHEN** 配置的 telemetry exporter 拒绝数据或有界队列已满
- **THEN** Run 仍可用且终态不变，同时产生 drop signal
