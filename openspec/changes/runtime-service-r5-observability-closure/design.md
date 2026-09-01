## Context

R5 现有实现已经有 `observability/langfuse.py`、五个 Service 入口的 adapter 接线、脱敏函数和基础 Counter，但这些能力仍停留在调用边界和 fake Graph 单测：Langfuse client 没有由 Agent Server lifespan 管理，caller metadata 仍可能进入 Trace 身份字段，诊断日志缺少 Run/Thread/Request 关联，且没有真实 Model/Tool/Subagent 和 exporter 故障证据。

本变更只负责 `apps/runtime-service` 的 Agent 工程观测。Agent Server 仍拥有 HTTP、Queue、Thread、Run、Checkpoint、恢复和 drain；Platform API 仍拥有权限、调度、Audit 和 Run 事实源。Runtime 不创建第二套 Run 状态机，也不把 Langfuse 结果写回业务状态。

## Goals / Non-Goals

**Goals:**

- 通过 `http.app` 挂载最小 FastAPI lifespan，在服务接收 Run 前初始化一次 Langfuse，在 shutdown 执行一次有界 flush。
- 将 Trace metadata 分成调用方可提供的技术关联字段和 Runtime Auth/Resolver 产出的可信字段；未经验证的身份不能进入 `user_id`、租户或项目字段。
- 保持 `get_agent(config) -> Pregel`、Graph 拓扑、已有 callbacks 和业务异常语义不变。
- 用真实锁定依赖的 Graph 测试证明 Model、Tool、Subagent、并发隔离、诊断信号和 fail-soft 行为。
- 让 endpoint 不可达、队列满、callback 异常、flush 超时都可观察且不阻塞业务 Run。
- 让真实 Langfuse smoke 从现有环境读取凭据并可重跑，缺少外部资源时明确 skip/block。

**Non-Goals:**

- 不实现跨服务可信 OpenTelemetry parent/baggage 传播。
- 不实现 Platform Run Event、Run Explorer、Langfuse 查询代理、Audit 写入或前端 Trace UI。
- 不实现 Durable Run、PostgreSQL/Redis Checkpoint、Queue、Worker recovery 或自定义 shutdown manager。
- 不上传完整 Prompt、模型响应、Tool 参数/结果或模型思维链。
- 不创建 `ObservabilityProvider`、Registry、Factory、Middleware 或第二个 Trace/Run 状态机。

## Decisions

### 1. 使用 Agent Server 的 `http.app` lifespan 作为唯一资源边界

新增 `runtime_service.webapp:app`，只定义 `FastAPI(lifespan=...)`，不添加 Runtime 业务路由。lifespan startup 调用 `initialize_langfuse()`；显式启用但配置不完整时抛出稳定配置错误，默认关闭时不导入 SDK。shutdown 调用 `close_langfuse(timeout_seconds=...)`，flush 超时记录告警后继续退出。

`langgraph.json` 和 `langgraph.demo.json` 都声明同一个 `http.app`。这样 Agent Server 的生命周期和 Langfuse client 的所有权一致，Service 入口只创建 callback，不负责进程级初始化或关闭。

备选方案：在模块 import 或每次 `get_agent()` 中初始化。前者会让 schema/introspection 触发外部 client，后者会造成并发 client 和资源泄漏，均拒绝。

### 2. 保留一个 adapter，但将 metadata 变成显式 allowlist

`with_langfuse_tracing()` 只接收已存在的 `RunnableConfig` 和可选 `trusted_metadata`。合并规则如下：

1. callbacks 保留调用方顺序，追加 Langfuse callback 和 Runtime diagnostics callback。
2. metadata 只复制允许的技术关联字段；任意未知 caller key 丢弃。
3. `thread_id`、`run_id`、`assistant_id` 可从 Agent Server 规范化的 `configurable` 读取，不能从普通 metadata 推断身份。
4. `user_id`、`tenant_id`、`project_id`、`model_id`、`config_hash`、prompt/policy 字段只有 `trusted_metadata` 可以写入，trusted 值覆盖冲突 caller 值。
5. tags 只保留预先允许的低基数值，强制加入 `runtime-service` 和 graph id；高基数 ID 只放 metadata。
6. `langfuse_user_id` 只能由 trusted `user_id` 生成；没有 trusted user 时不得从 caller metadata 生成。

Service 组合根在已完成 Auth 和 Runtime resolution 后传入安全摘要。没有可信身份的 `workflow_demo` 只能使用技术关联 metadata，不伪造 user/tenant/project。

备选方案：让 Langfuse callback 自己解析 `configurable` 或从 metadata 推断身份。该方案把可观测边界错误地变成授权输入，拒绝。

### 3. 诊断使用标准 logging extra 和现有 Counter

继续复用 `langfuse.py` 的单一 diagnostics callback 和 `get_observability_metrics()`，但每条 Run/Tool/Exporter 日志必须带 `graph_id`、`run_id`、`thread_id`、`request_id`（未知时使用稳定的 `None` 字段）、status、duration 或 error category。日志只写 Tool 名称和错误类别，不写输入输出。

Counter 名称固定为 `run_success`、`run_failed`、`run_timeout`、`run_cancelled`、`tool_error`、`token_total`、`export_error`、`event_dropped`、`flush_error`、`flush_timeout` 等。指标快照是本 Service 的最小诊断契约；不新增 HTTP metrics 路由，避免和 Agent Server 路由/认证边界冲突。真实部署由现有日志采集和进程指标接入消费该契约，不能把测试快照称为远端 Prometheus 证据。

### 4. 对 exporter 故障采用隔离、丢弃、保留原异常

Langfuse SDK 负责其 exporter queue。Runtime adapter 不在 Run 完成时同步 flush；callback 创建、callback 回调和 shutdown flush 都捕获观测异常，递增 Counter 并记录结构化告警。队列满通过可注入 fake exporter/queue 在测试中证明非阻塞丢弃；Agent 原始 Model、Tool、interrupt、cancel、timeout 异常优先返回。

如果显式启用但启动配置非法，属于部署错误，lifespan 必须 fail-closed；如果配置合法后 Langfuse endpoint 暂时不可达，属于运行期观测故障，必须 fail-soft。这两个边界不能混为“全部静默关闭”。

### 5. 真实 Graph smoke 与本地故障测试分层

- 本地集成测试使用锁定的 fake/test model 和确定性 Tool，执行现有 `create_agent`/`create_deep_agent`，验证 callback 接收到 Model、Tool 和 Subagent 层级及原始业务结果。
- endpoint、queue、flush 故障使用可注入的 callback/client fake，不依赖网络即可稳定复现。
- `RUNTIME_R5=1` 才运行真实 Langfuse smoke；测试读取 `apps/runtime-service/.env` 或环境注入的现有凭据，不打印 secret。缺少完整配置或服务不可达时报告 skip/block，并在 verification 中保留结果。
- 真实 smoke 只证明 Trace ingestion 和安全字段，不证明 Langfuse 是 Run 状态源。

## Risks / Trade-offs

- [Langfuse SDK 生命周期 API 随锁定版本变化] -> 在当前 `langfuse<5` 和 LangGraph 版本上增加构造、callback、flush smoke；升级依赖必须重新跑该门禁。
- [http.app 改变 Agent Server 启动行为] -> app 不注册业务路由，只测 lifespan startup/shutdown 和 `/info`/Graph 加载链；失败时回滚配置挂载即可。
- [调用方原有自定义 metadata 被丢弃] -> 保留明确的技术字段 allowlist；新增字段必须先更新规范、测试和脱敏判断，不能恢复任意透传。
- [exporter 故障造成日志噪声或丢 Trace] -> 使用有界字段、Counter 聚合和单次结构化告警；Run、SSE、Checkpoint、Audit 不依赖 Langfuse。
- [真实外部凭据不可用] -> 不伪造通过；本地 contract/integration 证据与真实 smoke 的 blocked/skip 状态分开记录。
- [跨服务 request trace 尚未打通] -> R5 只接收已规范化的关联字段；可信 parent/baggage 另立 B3 变更。

## Migration Plan

1. 先实现并验证 `webapp.py` lifespan、adapter allowlist 和五个入口的 trusted metadata 接线。
2. 更新生产和 demo `langgraph.json` 的 `http.app`，执行配置解析、包导入、Agent Server introspection 和服务生命周期测试。
3. 执行观测专项、全量 Runtime 测试和真实 Graph smoke；确认 Langfuse 关闭路径不导入 SDK。
4. 在 verification、knowledge 16/24/28/31 和 README 中记录命令、结果、未覆盖边界和真实 smoke disposition。

回滚：关闭 `LANGFUSE_ENABLED` 并移除 `http.app` 配置后重启服务。Graph、Auth、Run、SSE、Checkpoint 和 Tool Policy 不依赖本变更的 Trace 数据，因此不需要数据迁移或业务回滚脚本。

## Open Questions

- 当前锁定的 Agent Server/CLI 版本是否在生产发行版中保证 `http.app` lifespan 的 startup/shutdown 都会执行；需用目标镜像启动和 SIGTERM 测试确认。若不能证明，不能将生命周期要求标记为完成。
- 真实部署的日志采集是否已把标准 logging `extra` 转成结构化字段；本变更只定义 Runtime 字段契约，不伪造基础设施 exporter 已存在。
- Langfuse 实际 SDK 在 queue 满时的异常类型和丢弃计数是否稳定；实现阶段必须以锁定版本源码/运行测试确认，不能只断言自建 Counter。
