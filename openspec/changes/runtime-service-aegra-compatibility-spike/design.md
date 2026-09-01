## Context

`apps/runtime-service` 约定每个 Agent 暴露 `async def get_agent(config: RunnableConfig) -> Pregel`，
并由 Durable Server 提供 Thread、Run、Checkpoint、Replay、HITL 和恢复。官方 licensed
`langgraph-api` 当前受到 entitlement 阻塞；Aegra 声称提供兼容 Agent Protocol 的自托管执行面。

本 Spike 是 `apps/runtime-service` 的 B3 外部兼容性验证，涉及 Runtime、Aegra、PostgreSQL、
Redis、真实模型、Langfuse 和 Platform Context 边界。它不是生产替换，也不把 Aegra 内部模块
复制进 `src/runtime_service`。

## Goals / Non-Goals

**Goals:**

- 证明 Aegra 能按 Run 调用当前异步 `get_agent(config)`；
- 用真实模型、PostgreSQL、Redis 和 Langfuse 验证 R6 关键 Durable 语义；
- 验证 DeepAgent Workspace、Backend、Subagent 和 RuntimeContext 的隔离边界；
- 生成可复现的 pass/fail/blocked 证据，为是否引入 Aegra 提供决策依据；
- 让 Spike 可独立启动、停止和清理，不改变正式 Runtime 默认路径。

**Non-Goals:**

- 不把 Aegra 作为 R6 Docker 的直接替换；
- 不修改 `platform-api` 正式控制面契约；
- 不建设第二套 Runtime Engine、Tool Registry、Factory、Coordinator 或 Durable 状态机；
- 不验证 Aegra 的全部 LangGraph SDK API、Cron、Store 或 Studio 功能；
- 不把 Langfuse 当作 Run 状态或权限事实源；
- 不在没有真实凭证和真实依赖时用 mock 结果宣称通过。

## Decisions

### 1. Spike 采用隔离目录和独立依赖

Spike 代码放在 `apps/runtime-service/spikes/aegra/`，测试和运行脚本只在该目录内维护；
正式 Runtime 的 `pyproject.toml`、`langgraph.json` 和 `src/runtime_service` 不增加 Aegra
依赖。Aegra 版本和 LangGraph 版本固定在 Spike 自己的依赖文件中；Aegra 本身通过 `uv`
在宿主机隔离环境运行，Compose 只提供 PostgreSQL 和 Redis。

**原因：** 兼容性试验需要快速替换和回滚，不能把 Beta Server 绑定到正式运行时。

**替代方案：** 直接改 R6 Docker。拒绝，因为当前还没有真实恢复和隔离证据，回滚成本更高。

### 2. 使用 Aegra 的 Agent Protocol/SDK 路径

Spike 通过 Aegra Server 和官方兼容 SDK 提交 Thread、Run、SSE、HITL 和取消请求，避免调用
Aegra 私有内部 Python API。图配置指向现有 `get_agent` 导出。

**原因：** 这验证的是可部署的公开边界，而不是对内部实现的脆弱耦合。

**替代方案：** 只测试 `LangGraphService` 私有函数。拒绝，因为不能证明真实 Server 的队列、
Checkpoint 和事件语义。

### 3. 真实依赖优先，缺失时显式 blocked

模型、PostgreSQL、Redis 和 Langfuse 都走本地 `.env`；测试不得打印密钥。没有依赖时报告
`blocked`，不自动降级为 mock pass。可以保留少量本地单元测试用于排查协议格式，但不能作为
Durable/模型/观测验收证据。

**原因：** 这条链路的主要风险就是外部依赖和跨进程恢复，mock 无法证明它们。

### 4. 先验证 Aegra，GraphHarbor 只做对照

Aegra 的一参数异步 factory 支持当前 `get_agent(config)`；GraphHarbor 当前图加载器不传入
`RunnableConfig`。因此 Spike 先实现 Aegra，GraphHarbor 只保留兼容性差异记录，不并行维护
两套完整测试框架。

### 5. Platform Context 使用最小边界夹具

Spike 提供一个仅用于测试的 Platform Context fixture，包含签名/版本、身份、project、
thread/run、model、tool policy 和 trace metadata。Runtime 仍执行本地 fail-closed 校验；
Aegra 的 `ServerRuntime`/`context` 只作为适配输入，不成为本项目公共契约。

## Risks / Trade-offs

- [Aegra Beta API 变化] -> 锁定 commit/package 版本，记录版本和迁移结果，失败时不影响正式 Runtime。
- [Aegra 的 context 与本项目 RuntimeContext 不同] -> 使用边界适配夹具，并对 protected 字段做拒绝测试。
- [Worker 重启造成重复执行] -> 使用 PostgreSQL lease、checkpoint 和终态条件更新，断言只接受一个终态。
- [DeepAgent 文件状态未被 Checkpoint 持久化] -> 将 Workspace marker 和 worker handoff 作为独立验收，不通过则否决生产引入。
- [Langfuse exporter 拖慢或阻塞 Run] -> 注入 exporter 故障，断言 Run finalize 不依赖 Trace 成功。
- [真实模型成本或限流] -> 只使用小规模、可控的 E2E 场景，复用 `.env` 中已授权的中转模型，不把密钥写入产物。
- [Spike 代码污染正式依赖] -> 独立目录、独立 Compose profile 和 opt-in 命令，完成后可整体删除。

## Migration Plan

1. 先创建并评审本 OpenSpec change，不修改 R6 正式部署。
2. 在 `apps/runtime-service/spikes/aegra/` 固定 Aegra、LangGraph 和 SDK 版本，提供
   PostgreSQL/Redis Compose、`.env` 检查和本地 uv 运行命令。
3. 先完成 `get_agent(config)`、文本模型和健康检查，再按任务顺序执行 Durable、Replay、HITL、隔离和观测测试。
4. 记录每项证据和缺口到 `verification.md`，生成最终 Spike 报告。
5. Spike 失败或放弃时删除/停用隔离目录即可回滚；正式 Runtime 和 R6 Docker 不需要迁移。
6. 只有全部门槛通过后，另行提交“引入 Aegra 作为 Durable Server”的 OpenSpec change，重新评审依赖、运维和生产发布。

## Open Questions

- 当前 Aegra 发布包是否提供可复现的生产 Worker 启动命令，还是需要固定源码 commit？
- Aegra Agent Protocol v2 事件字段是否能无损映射到 18、22、25 号文档的事件契约？
- DeepAgent 使用的具体 Backend 是否能在不同 Worker 上安全恢复，还是需要 Service 自行提供持久 Workspace？
- Platform Context 的签名夹具应复用 Platform 测试公钥，还是在 Spike 内生成专用测试密钥？
