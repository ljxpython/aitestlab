## Why

R0～R5 已证明新 Runtime 包、Agent Service 入口、可靠性 Middleware、能力隔离和 Langfuse
观测可以独立运行，但还没有真实 Agent Server 持久化链路的证据。没有 PostgreSQL/Redis、Worker
重启、Checkpoint 恢复和 SSE 重连验证，Runtime 仍不能作为 Platform 的可靠执行面。

现在需要用一个独立阶段锁定 Durable Run 的行为和验收边界，先在不依赖 Platform API 的本地部署中
证明恢复语义，再进入 Platform 控制面整合。

## What Changes

- **BREAKING** 为新 Runtime Service 固定真实 Agent Server 的 Durable Run 验证方式，使用
  `durability="sync"` 和锁定版本的 PostgreSQL/Redis/Worker 组合。
- 验证 Thread、Run、Graph、Backend、Checkpoint 的生命周期和作用域，确保多次 Run、Interrupt/Resume
  与 Worker 重启不会串线或丢失可恢复状态。
- 固化可恢复 Stream 的 SSE `since` 游标、补发、去重和断线不等于取消语义。
- 验证 cancel、timeout、Tool failure、graceful shutdown 和 hard shutdown 后的唯一终态收敛。
- 使用本地 Delegation Token 完成最短 smoke test，不修改或等待 Platform API。
- 增加真实部署、故障注入和恢复 E2E 的测试与发布门槛；快速 Unit/Composition 测试继续保留。
- 不新增 Runtime Custom Route、第二套 Run Coordinator、公共 Builder/Factory、事件总线或旧代码兼容层。

## Capabilities

### New Capabilities

- `runtime-durable-run`: 定义 Runtime Service 在真实 Agent Server 部署中的 Thread/Run/Checkpoint
  持久化、Interrupt/Resume、SSE replay、Worker 重启恢复、取消和终态语义。

### Modified Capabilities

无。R6 首先新增 Durable Run 能力，不修改 R5 已冻结的可观测性要求；Platform 控制面契约留到 P1。

## Impact

- 影响范围：`apps/runtime-service` 的部署配置、Agent Server 启动参数、Durable/Integration/E2E 测试和
  本地 smoke 脚本；必要时补充测试专用容器编排文件。
- 依赖：锁定 LangGraph Agent Server/CLI 与 SDK 版本，使用隔离的 PostgreSQL、Redis 和 Worker。
- 运行契约：沿用 14、22、23、24、25 号文档的 `thread_id`、`run_id`、`checkpoint_id`、
  `durability`、`stream_resumable`、`on_disconnect` 和本地 Delegation Token 约定。
- 不修改旧 `apps/runtime-service/runtime_service/`，不迁移旧数据，不要求 Platform API 改动。
- 通过 R6 门槛后，才允许创建 P1 Platform API / Runtime Service 整合变更。
