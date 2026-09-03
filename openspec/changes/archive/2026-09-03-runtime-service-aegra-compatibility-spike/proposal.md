## Why

官方 `langgraph-api` Durable Server 当前受 Agent Server entitlement 阻塞，而 Runtime 已经
需要 PostgreSQL、Redis Worker、Checkpoint、SSE Replay、HITL 和恢复能力。Aegra 声称提供
自托管 Agent Protocol 执行面，并支持异步 per-Run factory；需要用本项目真实 Agent 和真实
依赖验证这些能力，避免因为 README 兼容声明而错误切换生产运行时。

本变更属于 `apps/runtime-service` 的 B3 跨边界兼容性 Spike，所有真实模型和观测凭证只从
本地 `.env` 读取，不写入代码、日志或 OpenSpec 产物。

## What Changes

- 新增独立 Aegra Compatibility Spike，不改变正式 Runtime Service 的 Agent API。
- 使用当前 `async def get_agent(config: RunnableConfig) -> Pregel` 入口验证 Aegra 图加载与 per-Run config 传递。
- 使用真实 DeepSeek 中转模型、豆包多模态中转模型、PostgreSQL、Redis 和 Langfuse 验证最小真实链路。
- 验证 Durable Run 恢复、SSE Replay、HITL interrupt/resume、Worker 重启、Lease recovery、DeepAgent Workspace 和权限边界。
- 记录可复现的兼容性证据、已知缺口和是否引入 Aegra 的决策依据。
- 不替换当前 R6 Docker，不修改 Platform API 控制面，不引入 Aegra 内部模块到 `src/runtime_service`。

## Capabilities

### New Capabilities

- `aegra-compatibility-spike`: 验证 Aegra 与本项目 Runtime Agent 入口、Durable 运行时、观测和资源隔离的兼容性。

### Modified Capabilities

<!-- 本 Spike 不改变已批准 Runtime Contract 或现有能力要求。 -->

## Impact

- 影响 locus：`apps/runtime-service`；最短验证链：Runtime Agent -> Aegra Server -> PostgreSQL/Redis/Langfuse。
- 计划新增 Spike 专用配置、测试、运行脚本和验证报告；不得把测试依赖混入正式 Runtime 运行时。
- 需要锁定 Aegra 版本和 LangGraph 相关版本，记录数据库 migration、依赖容器和本地 uv
  运行命令影响。
- 需要真实用户拥有的模型与 Langfuse 凭证；凭证缺失或服务不可用时只能报告 blocked evidence，不能伪造通过。
- Spike 通过不等于批准生产切换；若要引入 Aegra，另行创建替换 Durable Server 的 OpenSpec change。
