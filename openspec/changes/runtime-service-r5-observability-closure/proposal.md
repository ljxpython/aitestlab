## Why

R5 目前只有 Langfuse adapter 和局部单元测试，尚未证明它被 Runtime Service 的真实生命周期接管，也未证明可信身份边界、真实 Model/Tool/Subagent Trace、故障 fail-soft 和诊断出口在运行中成立。现在补齐这些缺口，才能把“代码存在”升级为可重跑、可审计的 R5 Harness 证据。

本变更归属 `apps/runtime-service`，受影响链路为 `langgraph.json -> Agent Server lifespan -> graph entrypoint -> RuntimeConfigMiddleware -> Model/Tool/Subagent -> Langfuse exporter`，执行级别为 B3 Governed。当前 `apps/runtime-service/docs/standards/` 没有可读取的叶子规范，本变更遵循根级 `AGENTS.md`、`docs/standards/01-ai-execution-system.md` 的 Harness/OpenSpec 规则，以及 Runtime knowledge 文档 16、24、28、31 的当前设计结论。

## What Changes

- 把 Langfuse 初始化和有界关闭接入 Agent Server 使用的 FastAPI/Starlette lifespan；`langgraph.json` 通过 `http.app` 挂载该生命周期，不增加业务路由。
- 在唯一的观测 adapter 内收紧 metadata 和 tags：技术关联字段与经过 Runtime 决议的可信身份字段分阶段合并，禁止调用方原始 metadata 伪造 `user_id`、租户、项目或策略信息。
- 为 `mcp_demo`、`workflow_demo` 及其他现有 Graph 入口补齐符合信任边界的观测上下文；没有可信身份时不得伪造身份。
- 用真实锁定版本的 Graph 执行覆盖 Model、Tool、Subagent、并发隔离、Run/Thread/Request 标识和 Token/耗时诊断信号；保留既有业务异常语义。
- 覆盖 Langfuse endpoint 不可达、回调/队列故障、flush 超时、timeout、cancel、interrupt 和原始 Model/Tool 异常，证明观测故障不阻塞或覆盖 Run 业务结果。
- 提供最小生产诊断出口或明确的结构化日志/指标契约，包含 Run、Thread、Request 关联标识及导出失败/丢弃/flush 信号；不建立第二套 Run 状态机或 Provider/Registry/Factory 抽象。
- 增加 `RUNTIME_R5=1` 的真实 Langfuse smoke 入口：凭据只从现有环境读取，缺少资源时明确 skip/block，不把 fake callback 当作真实 ingestion 证据。
- 同步 R5 knowledge、启动部署设计、开发计划、对齐审计、README 和 OpenSpec verification，记录每项证据及未覆盖边界。

明确不做：跨服务 OpenTelemetry parent/baggage 可信传播、Platform Run Explorer、Run Event 数据库、Durable Run/Checkpoint/Queue 实现、完整正文采集和 Langfuse 查询代理。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `runtime-observability`: 将 R5 的生命周期接入、可信 metadata、真实 Graph 层级、诊断信号和故障 fail-soft 从设计要求变为可执行要求。
- `runtime-agent-service-integration`: 要求所有 Runtime Graph 入口在生命周期可用的前提下接入统一观测 adapter，并保持 `get_agent(config) -> Pregel` 契约和业务异常语义。

## Impact

- 代码：`apps/runtime-service/src/runtime_service/observability/langfuse.py`、新增最小 `webapp.py`、`langgraph.json`/demo 配置、五个 Service 入口及相关测试。
- 部署：Agent Server 的 `http.app` 生命周期挂载和 Langfuse 配置读取；不复制 Dockerfile 的 Graph/依赖真源。
- 测试：观测单测、真实 Graph 集成测试、故障注入测试和显式启用的真实 Langfuse E2E smoke。
- 文档：knowledge 文档 16、24、28、31、Runtime README 与本变更 `verification.md`。
- 兼容性：Langfuse 默认关闭；未启用时 Graph 行为不变。启用但配置不完整时启动失败，属于有意的 fail-closed 部署行为。回滚可移除 `http.app` 挂载并关闭 Langfuse，不影响 Run、SSE、Checkpoint 和权限事实源。
