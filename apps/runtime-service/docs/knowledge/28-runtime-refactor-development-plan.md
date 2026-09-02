# Runtime Service 绿色重构开发计划

> 文档类型：Draft
>
> 状态：R0-R5 仅完成部分局部能力；R4 已完成 local harness 验收；R6 Durable Core 与正式 acceptance 已通过，生产 hardening `deferred`，切流保持 `not_ready`
>
> 适用范围：`apps/runtime-service`，以及后续最短的 `platform-api` 整合链路
>
> 关联文档：`10-production-agent-platform-roadmap.md`、`13-runtime-service-target-code-layout.md`、
> `14-runtime-contracts-and-resolution-design.md`、`15-runtime-middleware-lifecycle-and-failure-semantics.md`、
> `27-platform-runtime-integration-phased-design.md`

## 1. 总原则

本次是绿色开发，不是旧系统迁移。开发者按照本计划在新目标目录中重新实现，旧代码和旧数据
不作为输入。

硬规则：

- 新 Runtime 只写入 `apps/runtime-service/src/runtime_service/`；
- 旧 `apps/runtime-service/runtime_service/` 包已归档到 `archive/apps/runtime-service/runtime_service/`，不能导入、复制或适配；
- 不支持 `platform_runtime`、`enable_tools`、旧 Graph ID、旧 Assistant 字段或旧 HTTP 路由；
- 不做双读、双写、兼容 Adapter、旧数据迁移或旧 Thread 恢复；
- 不先创建 `engine/`、`builder/`、`factory/`、`registry/`、`plugin/`、`orchestrator/` 等公共层；
- 每个 Agent Service 直接暴露 `async def get_agent(config: RunnableConfig) -> Pregel`；
- 只使用 LangGraph Agent Server 标准 Graph/Thread/Run/Stream 接口，不新增 Runtime Custom Route；
- 每个阶段完成最小验证后才能进入下一阶段。

## 2. 开发阶段总览

```text
R0 新包和启动基线
  -> R1 Runtime Contracts / Auth / Resolver / Modeling
  -> R2 Agent Service 组合根和第一个 reference_agent
  -> R3 Middleware 可靠性栈
  -> R4 Tool / MCP / Backend / Workspace / Skills / Subagents
  -> R5 Trace / Logs / Metrics / Run Event 投影
  -> R6 Durable Run 真实部署验证
  -> P1 Platform 控制面和配置快照整合
```

当前阶段为 R6 Durable Run 真实部署验证收口。R0-R5 的“局部实现”和“生产链路完成”必须分开理解；
逐文档对齐、证据等级和剩余缺口见 [31 号审计](./31-runtime-refactor-alignment-audit.md)。
R6 已确定采用 `API + Worker + PostgreSQL + Redis` 四组件部署，GraphHarbor 作为通用 Agent Server Core；
已取得 Durable Core 和修复后 bridge SSE formal acceptance 的真实 PostgreSQL/Redis/API/Worker 证据；
Sandbox/远程 MCP、Langfuse/OTLP、Rollback、Platform 灰度和性能 SLO 按 owner 决策 `deferred`，不作为本轮 R6 失败项；
任何 Platform 整合仍不得提前实施；
Demo 按本计划第 13 节随所属阶段进入。

R0～R6 完成前不改 Platform 业务代码。P1 不是 Runtime 的前置条件，而是 Runtime 已经可以
独立运行后的第二条工作流。

### 2.1 阶段与设计文档映射

开始某个阶段前，先阅读该阶段的必读文档；只有实现触及对应边界时才阅读辅助文档。本文档
负责阶段顺序、交付物和门槛，具体设计文档负责各自领域的契约与实现约束。

| 阶段 | 必读设计文档 | 辅助参考 | 阅读重点 |
| --- | --- | --- | --- |
| R0 | [13 目标目录](./13-runtime-service-target-code-layout.md)、[24 启停设计](./24-package-langgraph-startup-shutdown-design.md)、[12 本地调试](./12-runtime-context-and-local-debug-architecture.md) | [11 Service 目录规范](./11-agent-service-directory-architecture.md)、[10 总路线](./10-production-agent-platform-roadmap.md) | 新包边界、Graph 导出、配置文件、启动和本地调试 |
| R1 | [14 Contracts 与 Resolver](./14-runtime-contracts-and-resolution-design.md) | [22 Platform/Runtime 契约](./22-platform-runtime-contract-design.md)、[26 模型配置边界](./26-runtime-custom-routes-and-model-config-design.md) | Context、Token、解析、模型选择和 fail-closed |
| R2 | [11 Service 目录规范](./11-agent-service-directory-architecture.md)、[13 目标目录](./13-runtime-service-target-code-layout.md) | [12 本地调试](./12-runtime-context-and-local-debug-architecture.md)、[24 启停设计](./24-package-langgraph-startup-shutdown-design.md)、[14 Contracts](./14-runtime-contracts-and-resolution-design.md) | `get_agent()` 组合根、`create_agent`、`StateGraph` 和 Demo 模板 |
| R3 | [15 Middleware 生命周期](./15-runtime-middleware-lifecycle-and-failure-semantics.md) | [14 Contracts](./14-runtime-contracts-and-resolution-design.md)、[16 可观测设计](./16-runtime-observability-and-langfuse-design.md)、[25 测试契约](./25-runtime-testing-and-cross-service-contract-design.md) | 顺序、异常传播、超时、取消、重试和清理 |
| R4 | [19 Tool/MCP/副作用](./19-runtime-tool-capability-mcp-and-side-effect-design.md)、[20 Backend/Workspace/Skills/Subagents](./20-runtime-backend-workspace-skills-and-subagents-design.md) | [11 Service 目录规范](./11-agent-service-directory-architecture.md)、[23 生命周期](./23-graph-thread-backend-checkpoint-lifecycle-design.md)、[14 Contracts](./14-runtime-contracts-and-resolution-design.md) | 显式工具装配、权限隔离、资源生命周期和子 Agent |
| R5 | [16 可观测与 Langfuse](./16-runtime-observability-and-langfuse-design.md) | [15 Middleware 生命周期](./15-runtime-middleware-lifecycle-and-failure-semantics.md)、[25 测试契约](./25-runtime-testing-and-cross-service-contract-design.md) | Runtime Trace、日志、指标、脱敏和 fail-soft |
| R6 | [23 Graph/Thread/Checkpoint 生命周期](./23-graph-thread-backend-checkpoint-lifecycle-design.md)、[24 启停设计](./24-package-langgraph-startup-shutdown-design.md)、[25 测试契约](./25-runtime-testing-and-cross-service-contract-design.md)、[30 Agent Server 替代研究](./30-agent-server-replacement-research.md) | [18 事件与 Run Explorer](./18-open-swe-to-runtime-event-and-run-explorer-design.md)、[22 Platform/Runtime 契约](./22-platform-runtime-contract-design.md) | Durable Run、恢复、重连、重启和终态收敛 |
| P1 | [22 Platform/Runtime 契约](./22-platform-runtime-contract-design.md)、[27 分阶段整合](./27-platform-runtime-integration-phased-design.md) | [10 总路线](./10-production-agent-platform-roadmap.md)、[18 事件与 Run Explorer](./18-open-swe-to-runtime-event-and-run-explorer-design.md)、[25 测试契约](./25-runtime-testing-and-cross-service-contract-design.md) | 配置快照、Gateway、权限、幂等和跨服务契约 |

文档冲突时，28 号只决定“何时做、做到什么门槛”；14、15、19、20、22、23、24、25 等领域
文档决定“具体怎么做”。旧目录和旧契约仍然不属于任何阶段的参考输入。

## 3. R0：新包、依赖和启动基线

### 目标

建立一个不依赖旧包的可启动 Runtime Service。

### 产物

- `apps/runtime-service/src/runtime_service/` 新包；
- `graphs/<graph_id>.py`、`agent.py`、`prompts.py`、`schemas.py`、`tools.py` 等 Service
  目录；
- `services/reference_agent/`、`services/workflow_demo/` 的第一批参考实现骨架；
- `langgraph.demo.json` 的本地 Demo 注册配置；
- 根目录 `langgraph.json`，R0 只注册新 Graph；Auth 延后到 R1；
- 固定的 `pyproject.toml`、锁文件、容器启动命令和 `.env.example`；
- 本地 fake model、真实模型 E2E 配置和 `langgraph dev` 调试脚本；文本模型使用 DeepSeek 中转，
  多模态模型使用 GPT 中转。

### 门槛

- `langgraph dev --config ./langgraph.json` 能启动；
- 新 Graph 能被 Agent Server introspection 找到；
- 导入路径不触碰旧 `runtime_service` 包；
- `git grep` 不出现新代码对旧模块的导入；
- R0 真实模型 E2E 在显式提供中转凭据时必须执行并通过，不能用 fake model 代替；未提供凭据时
  只能标记为未执行，不能标记为通过。

## 4. R1：Runtime Contracts、Auth、Resolver、Modeling

### 目标

冻结并实现 14 号文档定义的最小运行时契约。

### 产物

- `runtime/contracts.py`：不可变的 `RuntimeContext`、`RuntimePolicy`、`AgentDefaults`、
  `RuntimePrincipal` 和 `ResolvedRuntimeConfig`；
- `runtime/resolver.py`：纯函数校验、默认值合并和 fail-closed 决议；
- `runtime/modeling.py`：`model_id -> ChatModel` 的明确映射；
- `runtime/auth.py`：签名、audience、scope、过期时间和 Context hash 校验；
- `runtime/errors.py`：稳定 Runtime 错误码和安全错误摘要；
- `middlewares/runtime_config.py`：把已验证 Context 注入 Agent 执行。

### 约束

- Resolver 不访问 env、HTTP、数据库、MCP 或模型 Provider；
- Provider 凭据只从 Runtime 环境或 Secret Store 读取；
- `context.tools` 使用 `None`、空数组、非空数组三态语义；
- 旧字段直接拒绝，不提供 fallback；
- `model_id` 位于 Context，不位于 `configurable`。

### 门槛

- Unit 覆盖合法、缺失、越权、边界值和 hash 篡改；
- 不启动 Platform API 也能完成 Resolver 和 fake model 测试；
- 错误码和脱敏摘要固定下来。

## 5. R2：Agent Service 组合根

### 目标

用全新的 `reference_agent` 和 `workflow_demo` 证明基础组合根和两种官方 Graph 形态。

### 产物

- `agent.py` 中直接调用 `create_agent(...)`、`create_deep_agent(...)` 或
  `StateGraph(...).compile()`；
- 工具、Prompt、Schema、Middleware、Backend 和 Subagent 在 Service 内显式装配；
- 只有确实需要 Thread 级资源时才在 `get_agent(config)` 中动态创建实例；
- 不创建公共 `build_graph()` 或万能 Builder。

### 门槛

- `get_agent(config) -> Pregel` 组合测试通过；
- 静态 Graph 多次调用拓扑一致；
- 动态 Graph 只绑定当前 Thread 资源；
- introspection 不创建 Sandbox、MCP 连接或外部副作用。

`reference_agent` 和 `workflow_demo` 必须有独立 README、fake model 测试和标准
`langgraph.demo.json` 启动方式，作为后续 Demo 的复制模板。

## 6. R3：公共 Middleware 可靠性栈

### 目标

按 15 号文档实现最小、显式、有顺序的 Middleware 生命周期。当前 R3 closure 已补齐
Reference Agent 的 Tool Error/Retry 真实 graph 证据；生产 Provider fallback/retry、Run deadline
和 finalization 仍按 15 号文档的边界单独验收或后置。

### 首批顺序

```text
RuntimeContext validation
  -> PrepareRun
  -> ModelCallLimit
  -> ToolPolicy
  -> ToolError
  -> ModelFallback
  -> ModelCallTimeout
  -> RunFinalizer
```

每个 Middleware 独立文件、独立构造参数、独立测试；不做万能 Middleware Builder。

### 门槛

- 顺序、异常传播、清理和取消测试通过；
- Provider 临时错误只进行有界 retry/fallback；
- 非幂等 Tool 不自动重试；
- 超时、工具错误和空结束都形成确定终态。

## 7. R4：能力和资源接入

### 目标

在真实 Service 需求出现后，逐项接入能力，不预建 Registry。

### 顺序

1. 只读 Tool；
2. 需要审批的写 Tool；
3. Service 私有 MCP；
4. 明确 Coding Agent 才接入 Thread Workspace/Sandbox；
5. 只读 Bundled Skills；
6. 显式缩权 Subagents。

R4 同时完成三个能力 Demo：`deep_agent_demo`、`mcp_demo`、`backend_demo`。它们分别覆盖
`create_deep_agent`、Service 私有 MCP、Tool 副作用隔离、Thread Workspace、动态
`get_agent` 和资源清理；不把这些能力硬塞进 `reference_agent`。

### 门槛

- Tool 同时通过模型可见性和执行前检查；
- MCP 名称冲突立即失败；
- 子 Agent 不得扩大父 Agent 权限；
- Backend 失败不静默切换目录；
- Thread、Workspace、Checkpoint 的恢复和清理有真实测试。

## 8. R5：Runtime 可观测（Runtime 闭环完成，生产 exporter hardening deferred）

### 目标

建立 Runtime 侧可排查性，但不把 Langfuse 当作 Run 状态库。

### 产物

- Langfuse Trace：模型、Tool、Subagent 和 Graph span；
- 结构化 Service 日志：`request_id`、`thread_id`、`run_id`、错误码和耗时；
- Runtime 指标：成功、失败、超时、取消、Tool 错误、Token 和恢复次数；
- 安全 metadata 脱敏和 Langfuse fail-soft 验证；
- Run Event 投影和 Run Explorer 不属于 Runtime R5，留给后续 Platform 变更。

### 门槛

- Langfuse 不可用不影响 Run 核心状态；
- 每次 Run 可定位 Graph、Model、Tool、Checkpoint 和终态；
- 日志和 Trace metadata 经过脱敏和大小限制。

R5 closure 已补齐 Runtime 内部生命周期、可信 metadata allowlist、Model/Tool/Subagent callback
传播、结构化诊断、稳定 `event_dropped` Counter 和可重跑真实 Langfuse smoke。
`16-runtime-observability-and-langfuse-design.md` 的 Harness 表逐项记录了 `✅/❌` 和命令证据。
SDK queue saturation、目标生产容器 SIGTERM/drain 和跨服务传播按 owner 决策 `deferred`。历史官方
`langgraph-api` 镜像曾因 Agent Server entitlement `403` 在 application startup 前退出；当前
R6 已切换到 GraphHarbor 的 API + Worker + PostgreSQL + Redis 路线，不再把该历史授权错误当作
当前启动链路证据，也不能因为本地 `langgraph dev`、归档 OpenSpec 或 `.env` 中存在凭据而升级为
生产全链路完成。

## 9. R6：Durable Run 真实验证（Durable Core 与正式 acceptance 已验证，生产 hardening deferred）

### 目标

证明新 Runtime 在真实 Agent Server、PostgreSQL、Redis 和 Worker 重启下可恢复。

### 9.0 本轮范围与延期项

本轮 R6 formal acceptance 的完成边界是 Durable Core、API/Worker 生命周期、Thread Workspace、
事件 replay 和唯一终态。以下项目由 owner 明确暂缓，不作为本轮验收失败；它们仍保留为 `❌`，
待后续独立变更重新建立证据：

| 能力 | Status | 当前处理 |
| --- | --- | --- |
| 真实 Sandbox Provider、任意远程 MCP 的生产恢复/清理/配额矩阵 | `deferred` | Runtime/Deep Agents 后续补 Provider 级验收；GraphHarbor 不实现具体 Provider |
| Langfuse/OTLP 生产故障矩阵和跨服务传播 | `deferred` | 暂不做生产 exporter/service-failure 验收；保留已有本地 callback/smoke 证据 |
| Runtime 真实 rollback rehearsal | `deferred` | 保留 dry-run/apply 入口，暂不执行生产回滚演练 |
| Platform 灰度、route ownership 和回滚 | `deferred` | 由后续 Platform governed change 负责 |
| 性能 SLO、queue lag、PG/Redis watermark | `deferred` | 保留 baseline，暂不设 SLO 门槛 |

`deferred` 不等于 `implemented`，也不等于 `blocked`：它表示本轮主动不做，未来恢复时必须重新
指定 owner、输入、验证环境和接受标准。

### 必须验证

- `durability=sync`、可恢复 Stream 和明确的断线策略；
- Thread 连续 Run、Interrupt/Resume、多次中断；
- Worker restart 后 checkpoint 恢复；
- cancel、timeout、Tool failure 和 terminal 状态收敛；
- SSE 重连按游标补发且不重复；
- 不依赖 Platform API 也能使用本地 Token 完成 smoke test。

R6 已选择 GraphHarbor 作为通用 Agent Server，部署拓扑固定为 `API + Worker + PostgreSQL + Redis`。
API 与 Worker 使用同一 Runtime 镜像，以不同启动角色运行；PostgreSQL 和 Redis 独立部署。
2026-09-02 的正式包基线使用已发布的
`graphharbor==0.13.0.post20` / `graphharbor-runtime==0.13.0.post20`、独立 PostgreSQL 16.9、
Redis 7.4.2、真实 API/Worker、Runtime 部署 env 中的模型凭据和本地 Delegation Token。Compose 使用
可注入的 `RUNTIME_GRAPH_CONFIG`；生产默认仍为 `langgraph.json`，R6 验收显式使用
`/app/langgraph.r6.json`。全新 `r6-verify-post20-20260902` 环境使用
`http://127.0.0.1:18134`，旧的 `post19` 验证环境未删除或修改。

最新可复现结果：

- Runtime durable suite：`14 passed, 1 skipped`；覆盖 sync/async/exit durability、Thread 重用、双顺序
  interrupt/resume、非法 checkpoint、replay 去重、断线不取消、cancel 幂等、Tool failure、Backend checkpoint
  隔离和 Thread Workspace 恢复/隔离；唯一 skip 是需单独 10 秒 Worker deadline 的 timeout 专项；
- Compose Worker lifecycle：restart 与 SIGTERM replacement 各 `1 passed`；使用确定性的 `recovery_demo`，
  两个场景均断言 checkpoint marker 恢复且最终完成；
- GraphHarbor full suite：`132 passed, 14 skipped`，Ruff、mypy、lock/version gate 通过；
- 独立 fault-injection harness 的真实进程 `SIGTERM` 与 `SIGKILL` checkpoint 接管均到达 `success`，
  从 `marker=checkpointed` 恢复，`shutdown_requeue_total=1`，且 terminal event 唯一；
- 重复 queue、迟到 finalize、reaper/cancel race 的唯一终态约束通过；
- R6 专用 failure/timeout graphs 在真实 API、独立 Worker、PostgreSQL/Redis 下均已验证；timeout demo
  使用显式可取消的 `StateGraph -> slow_tool`，避免 Fake model Tool loop 掩盖 Worker deadline；
  PostgreSQL 中 Tool error 与 timeout 均只有一个对应终态，Worker deadline 使用正数配置；
- Python 3.11、3.12、3.13 wheel 安装与启动通过。
- 独立 Docker bridge network namespace 的 SSE 正式验收已通过统一 Harness 入口：
  `scripts/r6_network_sse_acceptance.sh` 先检查 API `/ready`、收敛唯一 Worker 并执行真实 Worker
  功能探针，再由 `r6_network_sse_acceptance.py` 使用两个独立 SDK 客户端验证首客户端断开、
  `Last-Event-ID` 后续事件和最终 `success`。结果为 `initial_cursor=4`、`resumed_event_count=2`、
  `run_status=success`，`6.5` 已完成。
- 隔离 PostgreSQL 备份恢复通过：`scripts/r6_postgres_backup_restore.sh` 只读导出当前隔离源库，并恢复到
  临时 `pgvector/pg16` 实例；源库、现有 volume 和业务数据不被删除或修改。
- 性能基线通过但仅为记录：4 并发 `disconnect_demo` 的首事件 p50/p95 为 `508.63/535.72 ms`，完成
  p50/p95 为 `15648.47/15664.91 ms`，checkpoint read p50/p95 为 `27.39/42.80 ms`；公共 API 未提供
  queue enqueue watermark，`queue_lag_ms` 保持未观测，不能自动判定 SLO。
- Workspace acceptance 在已发布 PyPI `post20` 上通过写入、Worker replacement、API `SIGTERM -> restart`、
  Thread/tenant 隔离和不可用根 fail-closed；每个业务 Run 只有一个 terminal event。
- Closure 批次的 RuntimeContext 严格 claims、关联字段 fail-soft 和显式端口修复已随两个
  `0.13.0.post20` PyPI wheel 发布；同端口探针在正式 `post20` 镜像中通过，不再把本地 wheel 当作发布证据。
- Workspace 总字节配额、TTL cleanup dry-run/apply 和 Deep Agent `task` Subagent 的真实委派及
  namespace stream 投影已有对应代码与测试；生产 Backend/Sandbox provider 的原子配额、调度和清理
  按 owner 决策 `deferred`。
- Runtime rollback 已提供默认 dry-run 脚本；它要求调用方提供 known-good image，不执行 `compose down`
  或删除 PostgreSQL/Redis volume。真实发布回滚演练仍未执行。

这只证明 Durable Core 和正式 acceptance 的已覆盖边界。隔离库备份恢复和性能 baseline 已有本地证据；生产
Backend/Sandbox/远程 MCP、Langfuse/OTLP queue saturation 与服务端故障、Platform 灰度和 rollback 按本轮决策
保持 `deferred`，未纳入本轮 acceptance。
Runtime 依赖固定在 PyPI 上的 GraphHarbor `post20`，Docker 不依赖开发机源码或本地 wheel；正式切换仍保持
`not_ready`，不能把正式 acceptance 通过等同于生产切流通过。
详细原子状态见
30 号文档第 12 节；GraphHarbor readiness 必须保持 `not_ready`。

Thread Workspace 的 `post20` 真实验收通过：同一 Thread 在替代 Worker 和 API 重启后能读回持久化
Workspace 文件，第二个 Thread 无法读取该文件，跨 tenant 查询返回 `404`，不可用 Workspace 根以
`error` 终态 fail-closed，业务 Run 各只有一个 terminal event。该证据不扩展为 Backend、Sandbox
或 MCP Provider 的生产恢复结论。

Backend durable 隔离测试已在独立 GraphHarbor API、Worker、PostgreSQL 和 Redis 上通过：
`tests/durable/test_backend_isolation.py -k backend_demo_keeps_thread_checkpoints_isolated`
结果为 `1 passed`，两个 Thread 各自生成唯一 checkpoint；测试按最新 SDK 的公开契约将 `runs.wait()`
视为最终 State，再从 `threads.get_state()` 验证 checkpoint。该测试证明 Thread checkpoint 不串线，
不替代真实 Backend provider 跨 Worker 重连、清理和配额验收。

R6 的 MCP 本地真实恢复验收也已通过：`scripts/r6_mcp_acceptance.py` 使用独立 Streamable HTTP
provider，等待 provider readiness 后完成 discovery、`mcp_read` 调用、Worker 替换重连、provider
重启恢复；缺少 Thread binding 和 provider 不可达时均持久化 `runtime.mcp.recovery_failed`，5 个
Run 各只有一个终态事件。
这不扩展为任意远程 MCP provider 的生产可用性结论。

R6 Durable Core 通过后，Runtime 具备受控环境调用的基础；`6.6` 已完成 owner acceptance、spec sync
和 archive。正式生产切流仍需后续恢复并完成上述 deferred 项目。

### 9.1 历史 post18 修复后验证（2026-09-02）

GraphHarbor `0.13.0.post18` 双包已直接发布到 PyPI，Runtime lock 和 Docker 无缓存重建均确认使用
该版本。本节是历史验证记录，不代表当前 `post20` 的结果；本轮按 Harness 只执行一次修复后验证，
不因失败重试：

- durable suite：`7 failed, 6 passed, 2 skipped`；失败集中在 `reference_agent` 模型初始化、
  post18 Runtime Context unknown claims、timeout 配置未切到测试 deadline 和 Backend checkpoint
  断言；
- Workspace acceptance：首个写入 Run 因 `runtime context contains unknown claims` 进入 `error`；
- 容器宿主的 `.env` 虽有模型凭据，但没有通过部署 env file 注入镜像；服务内模型变量为空；
- 结论：版本发布和安装链已完成，但 Runtime Context 契约、凭据注入和 timeout 验收配置未闭合，R6
  继续保持 `durable-core-partial / production-cutover-blocked`。

不得把本轮失败后的任何重复执行写入为新的成功证据；下一次修复必须建立新的验证批次并重新记录根因。

### 9.2 Closure gate 对齐（2026-09-02）

| Gate | 是否实现 | 实现与验证位置 | 当前结论 |
| --- | --- | --- | --- |
| `6.1` host-infra 外部 PG/Redis | ✅ | `deploy/docker-compose.runtime-service.host-infra.yml`；静态 Compose contract test | API、Worker、migration 使用外部 PostgreSQL/Redis，未声明本地基础设施 |
| `6.2` RuntimeContext producer/consumer 对齐 | ✅ | GraphHarbor `langgraph_runtime_pg/auth.py`、`graph_executor.py`；`test_production_contract.py` | 未知 top-level/nested claims 拒绝；Context 绑定 Run、Thread、tenant、project |
| `6.3` 显式端口 SIGTERM/restart | ✅ | GraphHarbor `langhost/cli.py`、`test_cli.py`；`scripts/r6_api_restart_probe.py` | 已发布 `post20` 镜像同端口探针通过 |
| `6.4` correlation 与 exporter fail-soft | ✅ | GraphHarbor `test_production_contract.py`、`test_observability.py`；Runtime `tests/observability/` | API、queue、Worker 关联字段和 exporter/queue drop 的 focused tests 通过 |
| `6.5` 一次正式 R6 acceptance | ✅ | `openspec/.../verification.md`；`scripts/r6_network_sse_acceptance.sh` | 修复后仅执行一次正式 acceptance；API/Worker readiness、唯一 Worker、cursor `4`、后续事件 `2` 和最终 `success` 均通过 |
| `6.6` sync/archive | ✅ | `openspec/specs/runtime-durable-run/spec.md`；`openspec/changes/archive/2026-09-02-runtime-service-r6-durable-run/` | owner acceptance、spec sync 和 archive 已完成；延期生产 hardening 不纳入本 gate |

### 9.3 post20 正式验收记录（Harness 修复前，2026-09-02）

本批次使用已发布 `post20` 双包和独立 Compose project `r6-verify-post20-20260902`。预检确认
PostgreSQL、Redis、schema、queue 和 API readiness 均正常；Durable smoke、Worker `SIGTERM/SIGKILL`
接管、Workspace、MCP 和 API 同端口重启均通过。故障注入期间已停止常驻 Compose Worker，确保只有
一个消费者；两种 Worker 故障都从 `marker=checkpointed` 恢复，且 PostgreSQL 只有一个 terminal event。

bridge SSE 未形成有效证据：客户端建立连接时本批次 Worker 仍处于停止状态，未收到 cursor；该步骤
按 Harness 规则记为 `blocked`，没有重试。以后正式验收必须显式设置容器内 API URL、在创建 Run 前
确认 API/Worker readiness，并在故障注入与跨网络 SSE 之间明确切换唯一消费者。详细结果见
`openspec/changes/archive/2026-09-02-runtime-service-r6-durable-run/verification.md`。

因此本历史批次状态为：`Durable Core + closure gates post20-verified / formal-release-acceptance-blocked`。
本表中的 `✅` 只说明对应 gate 的实现和局部证据成立，不代表 GraphHarbor 已达到生产切流状态。

### 9.4 post20 修复后正式验收记录（2026-09-02）

修复后的 `scripts/r6_network_sse_acceptance.sh` 在已发布 `post20` 镜像和独立验收环境中只执行一次。
API 与 Worker readiness、唯一 Worker、真实 `recovery_demo` 功能探针和独立 bridge network SSE 均通过：

```json
{
  "status": "passed",
  "api_readiness": "passed",
  "worker_readiness": "passed",
  "initial_cursor": 4,
  "resumed_event_count": 2,
  "run_status": "success"
}
```

清理后 `project_containers=0`、`project_networks=0`、`port_18135_listeners=0`，保留 3 个验收数据卷，
旧 `post19` 环境未触碰。由此 `6.5` 和 `6.6` 均已完成（owner acceptance、spec sync、archive）；
外部 Sandbox/远程 MCP、观测服务端故障、真实 rollback 和 Platform 灰度仍是生产切流门槛。

## 10. P1：Platform 控制面整合

### 前置条件

R0～R6 全部通过，Runtime 的 Context、错误码、事件和模型执行边界已经冻结。

### 产物

- 新建 Model Catalog、Project Model Policy、Assistant Runtime Config 和 Durable Run schema；
- Platform 侧配置合并和不可变 `RuntimeContext` snapshot；
- `context_hash` 与 Delegation Token 绑定；
- Gateway 统一注入 Context、durable 默认值和幂等键；
- Platform/Runtime 双端独立契约测试；
- 最后接入配置页面和 Run Explorer。

### 禁止事项

- 不把模型调用、Graph、Tool、Checkpoint 搬入 Platform；
- 不让 Platform 访问 Provider 凭据；
- 不增加 Runtime Custom Route、Model Registry、Route Registry 或第二套 Run API；
- 不读取或迁移旧 Platform 数据；新配置通过新管理 API 或部署清单创建。

## 11. 每个开发任务的执行模板

每个任务必须按同一循环执行：

```text
确认本计划对应阶段
  -> 写/更新该阶段最小契约和伪代码
  -> 创建独立 OpenSpec change（进入实现阶段后）
  -> 先写最小失败测试
  -> 实现最小代码
  -> 运行本阶段门槛和最短相关链验证
  -> 更新文档、verification.md 和下一阶段入口
```

任何任务如果需要旧代码适配、旧数据迁移、兼容路由或新公共抽象，应立即停止并重新评审，
不得为了“先跑起来”偷偷加入。

## 12. 完成定义

本次 Runtime 重构完成的最低标准：

1. 新 Runtime 包可独立部署和本地调试；
2. 一个 `reference_agent` 通过真实 Agent Server 的 Thread/Run/Stream/Checkpoint 闭环；
3. Contracts、Middleware、Tool、Backend 和观测边界有可运行测试；
4. Runtime 不依赖旧代码、旧数据或 Platform API；
5. Platform 整合只通过新 Context、Token、Run Event 和 Gateway 契约完成；
6. 所有旧兼容、迁移、双读、双写和 Adapter 方案均不在仓库目标实现中。

## 13. 可运行 Demo 计划

Demo 是开发计划的一部分，不是重构完成后的补充材料。每个 Demo 都必须是一个遵守正式
Service 规范的可运行参考实现，具备独立的 `agent.py`、`get_agent()`、README、测试
和 `graphs/<graph_id>.py` 导出。Demo 不承载产品业务，也不依赖旧 Runtime、旧数据或
Platform API。

### 13.1 Demo 目录和注册

不创建公共 `server/` 目录。每个 Demo 都放在正式 Service 目录下：

```text
apps/runtime-service/src/runtime_service/
├── graphs/
│   ├── reference_agent.py
│   ├── workflow_demo.py
│   ├── deep_agent_demo.py
│   ├── mcp_demo.py
│   └── backend_demo.py
└── services/
    ├── reference_agent/
    ├── workflow_demo/
    ├── deep_agent_demo/
    ├── mcp_demo/
    └── backend_demo/
```

生产和学习使用不同配置：

```text
langgraph.json       -> 默认只注册 reference_agent
langgraph.demo.json  -> 注册五个 Demo，供本地学习和集成测试
```

`graphs/<graph_id>.py` 只重导出对应 Service 的 `get_agent`，不放业务装配、模型创建、Tool
扫描、MCP 连接或额外 metadata registry。

### 13.2 五个 Demo 的覆盖矩阵

| Demo | 主要构造方式 | 必须覆盖 | 开始阶段 |
| --- | --- | --- | --- |
| `reference_agent` | `create_agent` | 最小 Service、Prompt、Schema、显式只读 Tool、Context、Middleware、Trace | R2 |
| `workflow_demo` | `StateGraph` | Typed State、节点/边、条件分支、Checkpoint、Interrupt/Resume | R2 |
| `deep_agent_demo` | `create_deep_agent` | Skills、显式缩权 Subagent、StateBackend、子图事件、长任务上下文 | R4 |
| `mcp_demo` | `create_agent` + 私有 MCP | MCP 加载、名称冲突、凭据边界、Tool Policy、读写副作用隔离 | R4 |
| `backend_demo` | `create_deep_agent` + Backend | Thread Workspace、动态 `get_agent`、资源隔离、失败和清理 | R4 |

公共 Contracts、Auth、Resolver、Modeling、Middleware、Observability 和错误处理不重复复制成
第六个 Demo，而是在所有 Demo 中使用同一公共实现，由 `reference_agent` 展示最短路径。

### 13.3 各 Demo 的最低实现要求

`reference_agent` 是默认复制模板，必须展示 `create_agent(...)`、显式 Tool、RuntimeContext
绑定、公共 Middleware 顺序、fake model、真实 Provider smoke test 和标准 Thread/Run/Stream
调用。它不包含 MCP、Sandbox、Git、任意 shell 或复杂 Subagent。

`workflow_demo` 必须展示 Typed `WorkflowState`、确定的节点和条件边、人工确认或恢复点，
并说明为什么确定性流程不应伪装成 `create_deep_agent`。`workflow.py` 只负责拓扑，
`agent.py` 负责组合和导出。

`deep_agent_demo` 必须展示 `create_deep_agent(...)`、一个显式缩权 Subagent、Bundled Skill、
默认 `StateBackend`、`stream_subgraphs`、namespace 和 Subagent 事件投影。它不接真实
Sandbox、GitHub、Slack 或 Linear。

`mcp_demo` 必须使用本地 stdio fake MCP Server，展示 Service 私有 `loader.py`、
`MultiServerMCPClient.get_tools()`、名称冲突立即失败、
`context.tools` 三态语义、模型可见 Tool 与执行前策略双重检查，以及写 Tool 的审批、幂等、
超时和明确 retry 名单。

`backend_demo` 必须使用本地 fake/in-memory Backend，展示 Thread-scoped Workspace、动态
`get_agent(config)`、不同 Thread 的资源隔离、Backend fail-closed、introspection 不创建
外部资源、worker restart 重建和 TTL 清理。真实 Sandbox 只能作为可选 smoke test。

### 13.4 Demo 实施顺序

```text
R0  创建 Demo 目录规范、Graph 导出约定和 langgraph.demo.json
R1  让 Demo 统一使用 Contracts/Auth/Resolver/Modeling 的调用样例
R2  实现 reference_agent 和 workflow_demo
R3  将公共 Middleware、错误和 Trace 接入前两个 Demo
R4  实现 deep_agent_demo、mcp_demo 和 backend_demo
R5  为五个 Demo 增加 Trace、日志、指标和脱敏验证
R6  对 reference_agent、workflow_demo 做必需 Durable E2E，其余做能力专项 E2E
```

R4 的 Demo 组合骨架已经落地：每个 Demo 在自己的 `get_agent()` 中直接调用官方构造函数并显式装配
当前演示能力。不会新增公共 `build_agent`、Builder、Factory 或 Registry；只有真实重复、复杂资源
生命周期或独立测试边界出现时，才允许 Service 私有的下划线辅助函数。组合骨架不等于 R4 全部门槛
通过；19、20 号文档的 R4 Harness 表明确记录 Policy、写 Tool、Thread Workspace、Skill 只读、
跨 Worker 重建和清理等缺口。

Demo 必须跟随阶段实现，不能等全部 Runtime 开发完成后再临时补写。R2 的两个 Demo 是第一条
完整纵向链路和后续复制模板；R4 的三个 Demo 只在对应公共能力有最小实现后加入。

### 13.5 Demo 统一验收

每个 Demo 都必须满足：

1. `async def get_agent(config: RunnableConfig) -> Pregel` 是唯一正式入口；
2. fake model 下可以在不启动 Platform API 的情况下运行；
3. `langgraph.demo.json` 能加载，graph ID 与导入路径一致；
4. README 说明构造函数选择、静态/动态生命周期、Context 和依赖装配位置；
5. 至少有一个 Service 装配测试和一个关键失败分支测试；
6. introspection 不触发 Sandbox、MCP、数据库或其他外部副作用；
7. 必要时能验证 Tool、Skills、Subagents、Backend、Checkpoint、Interrupt 和事件边界；
8. 生产 `langgraph.json` 不自动注册 Demo。

Demo 不引入公共 Builder、Factory、Registry、Plugin、Custom Route 或重复的 Runtime 内核。

### 13.6 R4 Apply 验收状态（2026-09-01）

R4 apply 已完成本地能力闭环，但不能把本地内存适配器写成生产 Durable 证据。`InMemorySaver`、
进程内 `StateBackend`、本地 fake MCP 和 fake model 只允许用于 local harness；没有可用 Durable Agent
Server、PostgreSQL/Redis、跨 Worker 重建和真实 Sandbox Provider 时，生产状态必须保持 `blocked`。
当前 R6 使用 GraphHarbor，不依赖官方 Durable Server entitlement。

| 边界 | 是否实现 | 实现与验证位置 | 证据结论 |
| --- | --- | --- | --- |
| Tool Policy 与 Deep Agents 内置 Tool 收缩 | ✅ | `services/{deep_agent_demo,mcp_demo,backend_demo}/agent.py`；`tests/services/test_r4_capability_demos.py` | `44 passed`；模型可见面和 handler 前均拒绝未授权 Tool |
| MCP Service 私有加载、冲突和 required/optional 语义 | ✅ | `services/mcp_demo/loader.py`；同上测试 | 本地 stdio fake graph 闭环；不等于远程生产 MCP |
| Skill 只读和 Backend fail-closed | ✅ | `deep_agent_demo/agent.py`、`backend_demo/agent.py`；同上测试 | 写 Skill、伪造 `execute/task`、Backend 初始化失败均拒绝 |
| Thread Workspace 本地协议 | ✅ | `backend_demo/agent.py`；`test_backend_workspace_survives_graph_rebuild_for_same_thread`、`test_backend_workspace_isolated_between_threads` | 同 Thread 重建可读、不同 Thread 隔离；仅 `InMemorySaver` 证据 |
| Subagent 实际委派缩权 | ✅ | `deep_agent_demo/agent.py` 的 `summarizer` Subagent | `test_deep_agent_performs_explicit_subagent_delegation`、`test_deep_agent_streams_subagent_namespace_and_projection`；OpenSpec `3.4` 已有真实证据 |
| Durable Workspace、跨 Worker/服务重启、清理 | ❌ | `workspace_demo`、`scripts/r6_workspace_acceptance.py`、`scripts/r6_workspace_cleanup.py` | R4 本地表不承诺 Durable；后续 R6 的 `post20` 已证明 Thread Workspace、API restart 和隔离链路；生产 Backend/Sandbox provider 清理、配额和完整资源矩阵按 owner 决策 `deferred` |

R4 当前状态：`local-complete / production-resource-hardening-deferred`。本节覆盖并更新 19、20 号文档中的
旧 R4 结论；具体 Requirement 明细以两份领域文档的 Apply Evidence Update 为准。

## 14. R0 实现对齐目录

> 本目录是 R0 的阶段验收入口。每一行必须能追到设计要求、源码、可失败测试和
> 验证记录；未满足的项保留为缺口，不因 OpenSpec task 勾选而自动变绿。`是否实现` 只有
> Requirement 整体满足时才填 `✅`；其余状态统一填 `❌`。

| ID | 要求 | 实现位置 | 测试/检查 | 验证记录 | 状态 | 是否实现 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `28-R0-001` | 新 `src/runtime_service` 包可安装导入 | `pyproject.toml`；`src/runtime_service/` | `tests/test_r0_baseline.py:test_installed_package_imports_without_test_path` | `uv run --frozen python` 直接 import 和临时 wheel 安装后的独立 venv import 均通过 | `implemented-local` | ✅ | 已完成本地安装基线 |
| `28-R0-002` | `reference_agent` 和 `workflow_demo` 骨架、稳定导出和 `get_agent` | `src/runtime_service/graphs/*.py`；`services/*/agent.py` | `tests/test_r0_baseline.py:test_service_entrypoints_return_pregel`；`test_r0_services_have_readme_and_dedicated_tests` | R0 基线 `14 passed` | `implemented-local` | ✅ | 已完成本地基线 |
| `28-R0-003` | fake model 和 Typed StateGraph 最小执行 | `services/reference_agent/agent.py`；`workflow_demo/workflow.py` | `tests/test_r0_baseline.py:test_reference_agent_uses_deterministic_fake_model`；`test_workflow_demo_has_deterministic_state_transition` | R0 基线 `14 passed` | `implemented-local` | ✅ | 已完成最小执行，不等于 R2 完整 Workflow |
| `28-R0-004` | 生产配置只注册 `reference_agent` | `langgraph.json:5-10` | `tests/test_r0_baseline.py:28-34` | JSON 检查通过 | `implemented-local` | ✅ | 已完成 |
| `28-R0-005` | R0 基线与 R4 Demo 配置、测试相互独立 | `langgraph.demo.json:5-25`；R0/R4 测试文件 | `tests/test_r0_baseline.py`；`tests/services/test_r4_capability_demos.py:test_demo_config_registers_all_r4_capability_graphs` | R0 `14 passed`；R4 `10 passed` | `implemented-local` | ✅ | R4 的三个能力 Graph 由 R4 测试负责，R0 不再依赖其存在 |
| `28-R0-006` | `langgraph dev` 启动、`/info` introspection 成功 | 根配置；稳定 Graph 入口 | `curl -fsS http://127.0.0.1:8123/info` | 本轮启动成功，返回 LangGraph API `0.13.0`、Python `1.2.11` | `implemented-local` | ✅ | 只证明 local_dev/in-memory |
| `28-R0-007` | 旧包、旧 Graph 和旧入口不进入新导入链 | 应用根无旧可导入包；新代码均从 `src/runtime_service` 导入 | `test_installed_package_imports_without_test_path`；静态 `rg` | 独立安装 import、静态检查和 Service AST 依赖门禁通过 | `implemented-local` | ✅ | `conftest.py` 不能替代安装证据 |
| `28-R0-008` | 显式真实模型 E2E；无凭据不得降级 fake | `tests/e2e/test_reference_agent_real_model.py:18-70` | `RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -m e2e -q` | 本轮真实 DeepSeek E2E：`1 passed in 11.61s`；使用 `.env` 配置，未降级 fake | `implemented-local` | ✅ | 仍是直接 local graph E2E；Agent Server/Durable 证据分别由 R1/R6 记录 |
| `28-R0-009` | Dockerfile Graph 注册由 `langgraph.json` 生成并受同步门禁保护 | `deploy/Dockerfile:3-20`；`langgraph.json:5-10` | `tests/test_r0_baseline.py:test_docker_graph_registry_matches_production_config` | R0 基线 `14 passed`，注册表与生产配置逐项一致 | `implemented-local` | ✅ | 配置变更后必须重新生成；真实容器启动仍需单独验证 |
| `28-R0-010` | R0 完成后才进入后续阶段 | `28` 阶段顺序；R0-R6 OpenSpec archive 时间线 | `openspec list --json`；归档目录检查 | R0 归档早于 R1-R6；后续阶段未改变 R0 的 local scope | `implemented-local` | ✅ | 只证明阶段顺序，不把后续生产能力倒灌到 R0 |

### R0 结论

```text
R0 capability-local-complete / alignment-complete
```

可以确认：新包、稳定 Graph、两个最小 Service、fake 执行、本地启动、配置同步门禁和
R0/R4 测试边界都存在。
不能确认：R0 不覆盖真实生产容器的故障演练、跨服务 Platform 链和生产切流证据。
因此 R0 写成 `capability-local-complete / alignment-complete`，仍不能写成无条件的生产完成。

## 15. R1 实现对齐目录

> R1 主文档为 14 号文档；完整逐条矩阵见其“实现对齐目录”。本节只保留阶段入口和结论，
> 不复制第二份 Requirement 明细。`是否实现` 只有 Requirement 整体满足时才填 `✅`；其余状态统一填 `❌`。

| ID | 要求 | 实现/测试位置 | 验证记录 | 状态 | 是否实现 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `28-R1-001` | 五类不可变 Runtime 类型、严格 Context 和稳定错误 | `src/runtime_service/runtime/contracts.py`；`resolver.py`；`errors.py` | 修复前本地 R1 基线 `59 passed`；本次 GraphHarbor 集成 `3 passed` | `implemented-local` | ✅ | 受影响本地回归未在本次唯一命令中重复执行 |
| `28-R1-002` | 纯 Resolver 完成默认值、Tool Policy 和 hash 决议 | `src/runtime_service/runtime/resolver.py`；`services/reference_agent/agent.py:_TOOL_PERMISSIONS` | 修复前本地 R1 基线 `59 passed`；本次 GraphHarbor 合法 delegation 和非法 Context Run 均有证据 | `implemented-local` | ✅ | 受影响本地回归未在本次唯一命令中重复执行 |
| `28-R1-003` | Delegation JWT 验证 scope、时间、签名和 Context hash | `src/runtime_service/runtime/auth.py`；`auth/platform.py` | 修复前本地 R1 基线 `59 passed`；本次 GraphHarbor 3 项集成均使用签名 scope/context_hash | `implemented-local` | ✅ | 受影响本地回归未在本次唯一命令中重复执行 |
| `28-R1-004` | 已决议 Model 显式构造且凭据缺失不降级 fake | `src/runtime_service/runtime/modeling.py`；`tests/runtime/test_modeling.py` | `uv run pytest tests/runtime -q`：通过 | `implemented-local` | ✅ | 只证明构造参数和失败映射，不证明真实 Provider |
| `28-R1-005` | Runtime Config Middleware 可读取已验证 Context 并守住 Model/Tool 边界 | `src/runtime_service/middlewares/runtime_config.py`；`tests/middlewares/test_runtime_middleware.py`；`tests/integration/test_agent_server_auth.py` | 本地 Runtime/Middleware/Service 测试通过；GraphHarbor Durable 集成覆盖 Auth、未知 Context 失败、`runtime.server_info.user`、hash mismatch、Tool 边界和真实 Model | `implemented-chain` | ✅ | 当前 GraphHarbor Durable Model 链已成立；Platform 正式签发链和生产切流仍后置 |
| `28-R1-006` | R1 完成后才能进入后续阶段 | `openspec/changes/runtime-service-r1-contract-closure/verification.md`；14 号对齐目录 | 本地合同测试、GraphHarbor Durable 集成、audience 配置门禁和 OpenSpec strict 均通过 | `implemented-chain` | ✅ | R1 GraphHarbor Durable chain 已完成；Platform 正式 Gateway 和生产切流仍按阶段后置 |

### R1 结论

```text
R1 capability-chain-complete-graphharbor-durable / platform-cutover-deferred
```

R1 的 Contracts、Resolver、JWT scope/context_hash、Actor 权限交集、Modeling 和 Agent Server
Auth 接线已具备本地与 GraphHarbor Durable 证据，`temperature=0` Context 也已穿过 Resolver
到 DeepSeek Model。Platform 正式签发链和生产切流仍后置，因此不能把整个 Runtime 写成无条件
生产 `complete`。

## 16. R2 实现对齐目录

> R2 主文档为 11 号目录架构设计；这里保留阶段索引，完整逐条矩阵见 11 号文档的“R2
> 归档 R2 OpenSpec 与 11 号 Draft 对 `workflow_demo` 范围、`get_agent({})` 默认入口存在冲突；
> 详见 11 号矩阵的 `11-R2-REF-003`、`11-R2-SCOPE-001`。当前范围已获 owner 批准，代码实现
> 已完成本地部分；active spec 已 sync 并通过 strict validate。

| ID | 要求 | 实现/测试位置 | 验证记录 | 状态 | 是否实现 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `28-R2-001` | Service 组合根、稳定 Graph 导出和显式依赖装配 | `src/runtime_service/services/*/agent.py`；`src/runtime_service/graphs/*.py` | `uv run --frozen pytest tests/services/workflow_demo tests/services/reference_agent tests/test_r0_baseline.py -q`：`38 passed` | `implemented-local` | ✅ | reference/workflow 基础组合根已成立 |
| `28-R2-002` | `reference_agent` 使用 `create_agent`、RuntimeContext、Resolver、显式 Middleware 和 Tool | `services/reference_agent/agent.py`；`prompts.py`；`tools.py` | reference 专项既有 `16 passed`；本次 GraphHarbor Durable 真实模型链 `3 passed` | `implemented-chain` | ✅ | Platform 正式签发链不属于 R2 |
| `28-R2-003` | `workflow_demo` 使用 Typed StateGraph 并实现条件边、人工确认或恢复点 | `services/workflow_demo/workflow.py`；`workflow_demo/agent.py` | `tests/services/workflow_demo/test_agent.py` | 条件分支、Interrupt/Resume 和不重复执行测试通过 | `implemented-local` | ✅ | R2 本地证据；真实 Durable 仍由 R6 验证 |
| `28-R2-004` | 静态 Graph 重复调用拓扑一致；动态构图只用于 Thread/Run 资源 | `workflow_demo/agent.py:_AGENT`；`reference_agent/agent.py:get_agent` | `test_workflow_demo_static_topology_is_stable`、`test_reference_agent_topology_is_stable_across_runtime_bindings`；本地 R2/R0：`38 passed`；reference 不同绑定的 nodes、edges、schema 结构一致但实例不同 | `partial` | ❌ | 测试已证明拓扑稳定；仍需收敛 reference 生命周期，或记录并批准运行时模型绑定导致的 factory 例外 |
| `28-R2-005` | 两个 R2 Demo 均有独立 README、fake/确定性测试和标准 demo 配置 | `services/*/README.md`；`langgraph.demo.json` | `tests/test_r0_baseline.py`；`tests/services/workflow_demo/test_agent.py` | README、demo 配置和 Workflow 专属测试通过 | `implemented-local` | ✅ | R6 运行手册仍单独维护 |
| `28-R2-006` | introspection 不创建 Sandbox/MCP/数据库等外部资源，入口无外部副作用 | `graphs/*.py`；两个 Service `agent.py` | R0 基线、Workflow Server `/info` 和加载执行测试 | local Agent Server 加载/执行通过；无外部资源初始化 | `implemented-local` | ✅ | 仍缺独立静态依赖方向门禁 |
| `28-R2-007` | R2 两个 Demo 的 Agent Server 标准加载/执行链成立 | `langgraph.demo.json`；`tests/integration/test_agent_server_auth.py`；`test_workflow_demo_agent_server.py` | reference GraphHarbor Durable 测试 `3 passed`；workflow 需要独立的 `RUNTIME_DURABLE_DEMO_URL`，本轮未执行 | 两个 Demo 的同一条 Agent Server chain 尚未有当前有效证据 | `not-executed` | ❌ | 提供注册 `workflow_demo` 的 GraphHarbor 服务后单独验收，不能恢复旧 `langgraph dev` fixture |
| `28-R2-008` | R2 目标设计与 active spec 的能力范围一致，并为归档冲突保留迁移记录 | 11 号文档；`openspec/specs/runtime-agent-service-integration/spec.md`；归档 R2 文件 | `openspec validate runtime-agent-service-integration --strict --no-interactive` | 返回 `Specification 'runtime-agent-service-integration' is valid`；owner 已批准；active spec 已 sync；归档文件保留历史并有迁移记录 | `implemented-local` | ✅ | 后续以 active spec 为准 |

### R2 结论

```text
R2 capability-local-complete-local-agent-server / reference-lifecycle-incomplete
```

可以确认：Service 目录、组合根、稳定 Graph 导出、reference_agent 的 `create_agent` 组合、
真实模型链、workflow 条件分支/Interrupt/Resume、专属文档测试、active spec sync 和 reference
的 GraphHarbor Durable chain 已成立；workflow 的 Durable chain 本轮未执行。不能确认：reference
的静态/动态生命周期规则，因此 R2 仍不能标记为无条件完成。
