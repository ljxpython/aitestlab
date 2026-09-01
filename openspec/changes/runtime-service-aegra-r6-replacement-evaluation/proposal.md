## Why

当前 Aegra 兼容性 Spike 已证明它能够承接 `get_agent(config) -> Pregel`、PostgreSQL/Redis
Durable、HITL 和 Worker 恢复，但仍有 SSE replay、DeepAgent 隔离、RuntimeContext 跨 Worker
恢复以及 Langfuse 端到端观测等未覆盖边界。现在需要一个独立的 B3 评估变更，决定 Aegra
是否足以替换正式 R6 Runtime，而不是凭基础测试直接切换生产路径。

## What Changes

- 建立 Aegra 替换 R6 的正式 readiness 门槛和证据矩阵。
- 在隔离环境补齐剩余 Durable、事件、权限、DeepAgent、Context 和观测实验。
- 评估 Platform API 与 Aegra Agent Protocol 的控制面/执行面边界、部署、优雅退出、升级和回滚。
- 只有全部硬门槛通过，才允许后续创建生产切换实施变更；本 change 本身不修改 R6 默认部署。
- **BREAKING** 若后续批准切换，Runtime 执行面将从现有 R6 Server 迁移到 Aegra，需显式回滚开关和数据兼容方案。

## Capabilities

### New Capabilities

- `aegra-r6-replacement-readiness`: 定义 Aegra 替换正式 R6 Runtime 的验证门槛、证据、决策和发布阻断条件。

### Modified Capabilities

- 无。本阶段只做受治理评估，不改变现有 Runtime、Platform 或 Observability 的正式需求。

## Impact

- 所有实验限定在 `apps/runtime-service/spikes/aegra/` 和本 change 产物内。
- 需要真实 PostgreSQL、Redis、DeepSeek/豆包模型、Langfuse、可控 Worker 进程和 Platform Context fixture。
- 评估结果将影响后续 `apps/runtime-service/deploy`、`apps/platform-api` gateway、运维 Runbook 和发布回滚策略，
  但本 change 不直接修改这些生产代码。
