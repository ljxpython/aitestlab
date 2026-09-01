# Agent Server 替代方案调研：Aegra 与 GraphHarbor

- 文档类型：`Supporting / Research`
- 调研日期：2026-08-30；复核日期：2026-08-31
- 适用范围：`apps/runtime-service` 的 Durable Agent Server 选型
- 结论状态：候选评估；GraphHarbor Core 已完成主要开发，但生产替代仍未授权

本文回答一个问题：在不购买官方 `langgraph-api` Durable Server 许可的前提下，
是否可以使用 Aegra 或 GraphHarbor 承担 Runtime 的 Agent Server / Durable 执行面。
本文不把第三方项目当作 Runtime 内核设计的权威，也不改变 10 号路线图和 14 号
Runtime Contract 的既定边界。

## 1. 先说结论

### 1.1 Aegra

Aegra 可以作为官方 `langgraph-api` Durable Server 的优先候选，但当前不能直接宣布
生产替换。理由是：

- 它提供自托管的 FastAPI Agent Protocol Server；
- PostgreSQL 保存 Thread、Run、Checkpoint 和执行参数；
- Redis Worker、Lease、重试、SSE Pub/Sub、事件重放和跨实例取消覆盖了 R6 的主要运行时需求；
- 图导出支持静态 Graph、零参数 factory、异步 factory、异步上下文管理器；
- 一参数 factory 会收到每次 Run 的配置，因此兼容我们的：

  ```python
  async def get_agent(config: RunnableConfig) -> Pregel:
      ...
  ```

- 通过 OpenTelemetry 可把 Trace 发送到 Langfuse、Phoenix 或通用 OTLP 后端，不强制绑定 LangSmith。

阻塞点也很明确：

- Aegra 是 Beta 项目，版本和实现仍在快速变化；
- 它使用自己的 `ServerRuntime`、`context`、认证和 Assistant 模型，不能代替本项目
  的 Platform/Runtime JSON 契约；
- 它没有 DeepAgent 的 Workspace、Backend、Skills、Subagent 隔离规范，需要由我们的
  Agent 代码显式实现并验证；
- Aegra 的自定义路由、认证和 Assistant 控制面不能吞并 `platform-api` 的职责；
- 兼容性 Spike 已在本仓库真实 `get_agent(config)`、PostgreSQL、Redis、真实模型、HITL、
  graceful shutdown 和 Worker 重启链路上完成；DeepAgent 跨 Worker namespace、RuntimeContext
  worker 恢复和 Langfuse 服务端字段查询仍为阻塞项。

因此结论是：**Aegra 已通过主要兼容性基础实验，但仍不能直接替换 R6 生产运行时；Spike
使用 uv 本地安装 Aegra，Docker Compose 只运行 PostgreSQL/Redis。**

### 1.2 GraphHarbor

截至 2026-08-31 的 GraphHarbor 复核，原先“不能把 `RunnableConfig` 传给异步
`get_agent(config)`”的判断已经过时。GraphHarbor 当前的 `GraphRegistry` 已支持静态
Graph、零参数 factory、一参数 `RunnableConfig` factory、异步 factory 和 Run 级资源
生命周期；每个 Run 会重新解析 graph，不共享首个请求的模型、Thread 或权限配置。

GraphHarbor 已完成主要 Core runtime 开发，并在固定 `langgraph==1.2.11`、PostgreSQL、
Redis、官方 Python/JavaScript SDK 和固定验收 fixture 上通过本地协议及故障验收。已确认
的能力包括 PostgreSQL durable Run/Thread/Checkpoint、Redis 队列与 Pub/Sub、Worker
lease/heartbeat/reaper、终态条件写入、SSE replay/cursor、HITL、Principal/JWT、Store、
标准 stream modes 和五类固定 P0 fixture。

因此，GraphHarbor **可以作为通用 Agent Server 的 Core profile 用于本地和受控集成环境**，
但尚不能据此宣布已经完成 `runtime-service` 的生产 drop-in 替代。剩余问题主要是实际
`runtime-service` 外部依赖、跨 Worker/跨租户隔离、真实 Langfuse/OTLP、跨网络 SSE、
多 Python 版本安装、迁移备份恢复、性能和发布回滚验收，不是异步 factory 缺失。

### 1.3 LangSmith 与官方 `langgraph-api` 不能混为一谈

| 能力 | Aegra | GraphHarbor | 本项目现状 |
| --- | --- | --- | --- |
| LangGraph Agent Protocol 执行面 | 候选，可自托管 | 候选，可自托管 | 目标由 Runtime/官方 Server 承担 |
| Durable Thread/Run/Checkpoint | PostgreSQL + LangGraph Checkpoint | PostgreSQL + LangGraph Checkpoint | R6 正在验证 |
| Worker、Lease、恢复 | Redis Worker + PostgreSQL Lease | Redis Queue/Lease + PostgreSQL | R6 需要真实验收 |
| SSE、Replay、HITL、Cancel | 已实现并有测试目录 | 已实现并有测试目录 | 契约已设计，链路待验收 |
| `async get_agent(config)` | **支持候选路径** | **已支持并通过固定 fixture 验证** | Runtime 的强约定 |
| DeepAgent 专用隔离 | 无平台级专用契约 | 无平台级专用契约 | Agent 代码显式装配 |
| Langfuse / OTLP Trace | OpenTelemetry fan-out | OpenTelemetry/OTLP 能力 | Langfuse 负责 Agent Trace |
| LangSmith Trace/UI/控制面 | 不提供完整替代 | 不提供完整替代 | 不采用 LangSmith 作为事实源 |
| LangSmith Agent Server License | 可移除 | 可移除 | 当前官方 licensed Server 被 entitlement 阻塞 |
| License | Apache-2.0（仓库声明） | MIT（仓库声明） | 需做依赖与法务复核 |
| 当前成熟度 | Beta | Beta | 不能仅凭 README 宣称生产可用 |

这里的“可替代 LangSmith”只能理解为“替代 LangSmith Deployments/Agent Server 的自托管
执行面”。Aegra 和 GraphHarbor 都不能替代 LangSmith 的 Trace 查询产品、Studio、组织
控制面或商业服务。我们的 Trace 方案仍然是 Langfuse，Run/审计/权限事实源仍然是
`platform-api` 和 Runtime 的既定契约。

## 2. Aegra 调研事实

本次核查的仓库提交为：

```text
repository: https://github.com/aegra/aegra
commit: 392a5457b25754cdc828f14b0053abdefe8b6766
commit date: 2026-08-22
package: aegra-api 0.10.4
```

### 2.1 图加载与 factory

Aegra 的 `aegra.json`（找不到时回退到 `langgraph.json`）使用如下图导出格式：

```json
{
  "graphs": {
    "reference": "./src/runtime_service/graphs/reference_agent.py:get_agent"
  }
}
```

其图服务启动时加载模块并分类 callable，执行时再调用 factory：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    model = resolve_model(config)
    return create_agent(model=model, tools=tools)
```

对一参数 callable，Aegra 将参数视为 per-Run 配置；返回值可以是 `Pregel`、`StateGraph`、
协程或异步上下文管理器。异步上下文管理器在 Graph 执行期间保持打开，适合 MCP 客户端、
临时 Backend 或其他需要释放的资源。

Aegra 还支持：

- `ServerRuntime` factory：访问用户、Store 和 execution context；
- `ServerRuntime[T]`：在 factory 构图时解析类型化 context；
- `Runtime[T]`：在节点执行时读取 LangGraph context；
- 静态 Graph 缓存、factory Graph 按请求重新构造；
- 为每次执行注入 Checkpointer 和 Store。

这套机制与我们“直接使用官方 `create_agent`、`create_deep_agent`、`StateGraph`，每个
Agent 暴露 `get_agent(config)`，不建设万能 Builder”的方向相容。但 Aegra 的 factory
分类器和 `ServerRuntime` 不应反向成为本项目的公共 `factory.py` 或 `builder.py`。

### 2.2 Durable 执行面

Aegra 的生产路径大致为：

```text
Client / Platform API
  -> FastAPI Agent Protocol
  -> PostgreSQL 写入 Run + execution_params
  -> Redis queue
  -> Worker claim lease
  -> get_agent(config) + LangGraph stream
  -> PostgreSQL Checkpoint / Run finalize
  -> Redis Pub/Sub + replay
  -> SSE client
```

已实现的运行时机制包括：

- PostgreSQL migration 与 LangGraph PostgreSQL Checkpointer；
- Redis BLPOP job queue、并发限制和跨实例执行；
- PostgreSQL lease、heartbeat、Lease Reaper 和崩溃恢复；
- Worker 优雅退出时将未完成 Run 重新入队；
- SSE keepalive、断线 replay、跨实例 Pub/Sub；
- cancel、interrupt、resume、HITL 和 state editing；
- stateless Run、Cron、Store 和自定义 FastAPI routes；
- Prometheus HTTP 指标和 OpenTelemetry Trace。

这些能力覆盖了 R6 的基础验收面，但“代码存在”不等于“在我们的 Agent 上验收通过”。
特别是 checkpoint 恢复是否能正确恢复 DeepAgent 的 thread-scoped Backend，必须用真实
PostgreSQL、Redis 和真实模型进行验证。

本次 Spike 已用 Aegra `0.10.4`、真实 PostgreSQL/Redis、DeepSeek 文本模型和豆包视觉模型
验证基础链路：完整真实 E2E 为 `18 passed, 3 skipped`；graceful shutdown、Backend 重启
专项均通过，Fail-closed 预检为 `4 passed`，SSE 多帧 replay 已通过；DeepAgent 深层隔离
仍未达到可验收条件。
豆包通过 OpenAI 兼容接口接入，使用 `DOUBAO_API_BASE`、`DOUBAO_MODEL` 和服务端密钥；
视觉输入必须满足服务端最小图片尺寸要求（测试使用 `32x32` PNG）。

### 2.3 观测与 Langfuse

Aegra 采用 OpenTelemetry，并通过 `openinference-instrumentation-langchain` 采集
LangChain/LangGraph 调用。它支持把同一份 Trace fan-out 到 Langfuse、Phoenix、Jaeger
或其他 OTLP 后端，也支持控制台导出。

这可以复用我们已有的 Langfuse 方向，但不能改变以下事实：

- Langfuse Trace 不是 Run 状态、Checkpoint 或权限事实源；
- Platform Run ID、Runtime Run ID、Thread ID 和 Agent 版本仍需按 16、18、22 号文档
  注入并持久化；
- 需要验证 Aegra Worker 跨 Redis 边界的 Trace context 是否能与我们的 Langfuse
  correlation metadata 对齐；
- Trace exporter 失败不能阻塞 Graph 执行和 Run finalize。

### 2.4 MCP、Backend 和 Subagent 边界

Aegra 本身提供的是执行容器和资源生命周期钩子，而不是我们的 Tool Policy。它的 factory
示例使用 `MultiServerMCPClient` 并在 async context manager 退出时关闭 MCP 连接，这个模式
可作为 Service 私有 `mcp.py` 的参考。

但 Aegra 没有替我们完成以下治理：

- 工具显式装配与模型可见/实际执行一致性；
- MCP 凭证服务端解析和工具名冲突拒绝；
- 写操作、管理员能力和 Sandbox 能力的按 Agent 隔离；
- Tool retry 白名单、HITL 审批和幂等校验；
- DeepAgent Backend 的 thread 目录隔离、回收和跨 Worker 恢复；
- Subagent 的能力收缩和事件 namespace 约束。

这些仍由本项目 19、20 号设计和各 Service 的 `agent.py` 显式代码负责。不要因为 Aegra
提供 `ServerRuntime` 就再引入一个全局 Tool Registry 或万能 Capability Builder。

Spike 启动脚本将项目约定的 `LANGFUSE_ENABLED=true` 映射为 Aegra 的
`OTEL_TARGETS=LANGFUSE`，启动日志已确认 exporter 和自动 instrumentation 启用；本地
adapter 故障注入保持 Run 终态不变。已通过 Langfuse Public API 查询真实 Trace：存在
`run_id/thread_id/graph_id`，但缺少 `model_id`，且 input/output 仍包含实际内容，因此
观测关联和脱敏门槛分别记录为 `fail`。

## 3. 与本项目入口的兼容性判断

### 3.1 可直接复用的部分

在不改变 Agent 代码规范的前提下，Aegra 理论上可以直接加载：

```python
# src/runtime_service/services/reference_agent/agent.py
async def get_agent(config: RunnableConfig) -> Pregel:
    return create_agent(
        model=resolve_model(config),
        tools=[search_tool],
        middleware=middleware,
    )
```

图配置只需要把导出符号指向 `get_agent`。Aegra 会在每个 Run 使用实际 config 调用它，
不需要把 Agent 改写成零参数全局单例。

### 3.2 必须适配或重新验证的部分

1. **Runtime Context**：Aegra 的请求 `context` 和 `ServerRuntime` 不是 14 号文档定义的
   `RuntimeContext`。Platform 透传的签名上下文必须在 Runtime 边界重新校验，不能直接信任
   Aegra 的任意 `config` 字段。
2. **模型解析**：Aegra 不提供我们的 Model Catalog。模型白名单、Provider、凭证引用和
   多模态约束仍由 Platform 签发、Runtime 本地校验。
3. **观测字段**：需把 Platform Run ID、Agent 版本、模型标识和工具策略映射到 Aegra 的
   OTEL/Langfuse metadata，并验证 Worker 重启后的连续性。
4. **Backend 生命周期**：需证明同一 Thread 在不同 Worker 上恢复时不会共享模块级目录、
   临时文件或 MCP 连接。
5. **事件契约**：Aegra 的 Agent Protocol v2 事件要与 18、22、25 号文档的事件类型、
   顺序、幂等和脱敏要求逐项对齐。不能只验证 SDK 能收到 SSE。
6. **权限边界**：Aegra 的 auth handler 不能替代 Platform 的 project/tenant 权限；平台
   需要继续作为唯一控制面，Aegra 只执行已授权的 Runtime 请求。
7. **版本耦合**：Aegra 依赖特定版本范围的 `langgraph`、`langgraph-sdk` 和
   `langgraph-checkpoint-postgres`，需要锁定版本并建立升级 Spike。

## 4. 推荐路线

### R6 当前阶段

不立即把官方 licensed Docker Server 替换成 Aegra 或 GraphHarbor。R6 先保留当前真实
验证结论：官方 `langgraph-api` 受 entitlement 阻塞；`langgraph dev` 只能证明本地
in-memory 协议，不能冒充 Durable Server 验收。

### Compatibility Spike（已完成，候选 R6.1）

本轮已优先验证 Aegra，GraphHarbor 仍作为对照，未修改正式 Runtime 目录：

1. 使用当前 `reference_agent.get_agent(config)` 注册到 Aegra（已通过）；
2. 使用真实 DeepSeek 中转模型和豆包多模态中转模型，执行文本和多模态 Run（已通过）；
3. 使用真实 PostgreSQL + Redis 验证 Thread、Run、Checkpoint、HITL、cancel、worker restart、
   lease recovery、graceful shutdown 和 SSE 多帧 replay（已通过）；
4. 验证 `RuntimeContext` 的签名、版本和拒绝语义（fixture 与模型/工具拒绝已通过；worker
   边界恢复 blocked）；
5. 验证 Langfuse Trace 与 Platform/Runtime Run ID 的 join；
6. 验证 DeepAgent 的 workspace、skills、subagent namespace 和跨 Worker 恢复；
7. 做一次 Aegra 版本升级回归，并记录 API/数据库迁移影响；
8. 只有全部通过，才提交独立的替换 OpenSpec，评审是否把 Aegra 作为运行时依赖。

最小验收标准：

```text
同一 thread 的恢复结果正确
重复提交不会产生第二个有效执行
SSE 断线可 replay 且事件不重复计入
worker 崩溃后只恢复一次并从 checkpoint 继续
HITL interrupt/resume 状态和事件顺序正确
权限、模型、工具和 workspace 越界请求 fail-closed
Trace 丢失不影响 Run 终态
```

## 5. 暂不建设和暂不承诺

- 不把 Aegra 或 GraphHarbor 的内部模块复制到 `src/runtime_service`；
- 不新增 `engine/`、`builder/`、`factory/`、`registry/`、`plugin/`、`orchestrator/` 或
  `coordinator/` 公共万能层；
- 不把 Aegra 的 Assistant CRUD、Auth Handler 或 custom routes 当作 Platform API；
- 不把 Aegra 的 OpenTelemetry exporter 当作完整 Run Explorer；
- 不宣称 Aegra/GraphHarbor 已达到本项目生产门槛，除非 Compatibility Spike 有真实依赖
  和可复现证据；
- 不因为能去掉 `LANGGRAPH_CLOUD_LICENSE_KEY` 就跳过权限、恢复、事件和数据保留评审。

## 6. 参考来源

- Aegra：<https://github.com/aegra/aegra>
- Aegra 配置与 factory：`docs/reference/configuration.mdx`、`services/graph_factory.py`、
  `services/langgraph_service.py`
- Aegra Worker：`docs/guides/worker-architecture.mdx`
- Aegra 观测：`docs/guides/observability.mdx`
- Aegra 特性矩阵：`docs/feature-support.mdx`
- GraphHarbor：<https://github.com/ljxpython/graphharbor>
- 本项目既定路线：`10-production-agent-platform-roadmap.md`
- 本项目 Runtime 入口：`11-agent-service-directory-architecture.md`、
  `14-runtime-contracts-and-resolution-design.md`、`23-graph-thread-backend-checkpoint-lifecycle-design.md`

## 7. 正式 R6 Runtime 的能力基线

这份基线定义“替换正式 R6”必须满足的行为契约。候选项目必须在真实 PostgreSQL、Redis、
Worker、模型和 Langfuse 环境中提供可复现证据；只启动成功、SDK 能连接或 mock 通过都不算验收。

### 7.1 Agent 入口与图生命周期

1. 支持静态 `Pregel/StateGraph` 导出和异步 per-Run factory。
2. 每次 Run 将 `RunnableConfig` 的 `configurable`、`metadata`、`tags`、`context` 和 callbacks
   传入，不能被静默丢弃或跨 Run 共享。
3. `async def get_agent(config: RunnableConfig) -> Pregel` 必须按 Run 调用，不能缓存首个请求的模型、Thread 或权限。
4. 工厂签名、返回值和 graph export 错误在启动阶段 fail-closed。
5. MCP client、Backend、连接池等资源在成功、异常、cancel、timeout 和 shutdown 时释放。

### 7.2 Durable Run 与 Checkpoint

1. Thread、Run、Checkpoint、execution params 和终态持久化到 PostgreSQL，重启不依赖进程内存。
2. Redis 只承担队列、通知和租约协调，不成为唯一事实源。
3. Worker 使用 lease、heartbeat 和 lease reaper；崩溃后新 Worker 从最新 checkpoint 接管。
4. 优雅退出停止领取新任务，排空或重新排队进行中 Run，并关闭 DB/Redis/Trace 资源。
5. 终态更新使用条件写入和唯一约束；迟到 Worker、重复消息、网络重试不能覆盖或重复发布终态。
6. `run_id`、`thread_id` 和幂等键可查询；同一幂等键重复提交只能产生一个有效 Run。

### 7.3 事件、SSE 与 HITL

1. Thread 内事件具有单调 `seq` 和稳定 `event_id`。
2. SSE 断线使用明确 `since` 游标，只发送游标之后的事件，重复连接不重复计数。
3. replay buffer 的 TTL、容量、溢出和游标过旧行为必须有文档和测试。
4. lifecycle、values、updates、messages、debug 映射到 Runtime Run Event Contract。
5. HITL interrupt、resume、cancel、timeout、error、success 状态转移稳定，resume 不创建隐式新 Run。
6. 客户端断开、服务重启、Worker 转移和 SSE 重连组合场景必须覆盖。

### 7.4 Tool、MCP、Backend、Workspace 与 Subagent

1. Agent 在 `get_agent()` 中显式装配工具，Server 不扫描目录或隐式扩展工具。
2. MCP 凭证仅服务端解析，工具名冲突启动即拒绝，连接按 Run/Worker 生命周期关闭。
3. 写操作、管理员、Sandbox 和外部副作用按 Agent/Policy 隔离，retry 只允许明确白名单。
4. DeepAgent Workspace 根目录以 tenant/project/thread 为边界，禁止共享临时目录和客户端绝对路径。
5. 同一 Thread 跨 Worker 可恢复 Backend 状态，不同 Thread/tenant 不能互读 checkpoint 或文件。
6. Subagent 只看到父 Agent 显式委派的模型、工具、路径和预算，默认内置 agent 类型必须关闭或列入 policy。
7. Workspace 清理、配额、超时、文件大小和符号链接越界必须有拒绝测试。

### 7.5 RuntimeContext、权限与控制面

1. Platform API 是控制面：负责 tenant/project、模型目录、工具策略、凭证引用、幂等键和签名 Context。
2. Runtime Server 是执行面：只验证签名、版本、过期时间和允许字段，不猜测租户或模型权限。
3. 客户端不能覆盖 `user_id`、`tenant_id`、`project_id`、`thread_id`、`run_id`、provider 凭证或 tool policy。
4. Context 在 Worker 边界从可信持久化记录或签名 token 恢复，不能从不可信 Run input 重建。
5. 未授权模型、工具、Thread、项目和租户请求必须在模型调用或副作用前失败，并返回稳定错误码。

### 7.6 可观测性、成本和发布门槛

1. Trace 至少关联 Platform Run ID、Runtime Run ID、Thread ID、Agent/Graph 版本和 model reference。
2. Trace 不得包含 API key、token、cookie、完整 Prompt/Response 或无限制 Tool 参数，metadata 使用 allowlist。
3. Exporter、队列满、网络超时和 flush 超时不能改变 Run 结果。
4. 日志和指标覆盖 success/error/timeout/cancel、Tool error、lease recovery、queue lag、checkpoint latency、
   SSE replay gap、token/cost 和 exporter failure。
5. 发布前必须有 lockfile、migration、健康检查、优雅退出、容量上限、回滚开关和数据保留策略。
6. 灰度必须能按 Agent、tenant、project 或百分比切换，并支持无丢 Run 回退 R6。

## 8. GraphHarbor 达到 R6 要求所需的修改（复核更新）

以下内容保留原始改造基线，并补充 2026-08-31 的实现状态。代码完成不等于生产门槛
完成；所有“真实环境未验收”的项目仍必须保持未通过，不能用单元测试结果冒充生产证据。

| 改造项 | 当前状态 | 结论 |
|---|---|---|
| 8.1 Graph Loader / per-Run Factory | `GraphRegistry` 已支持异步一参数 factory、config 传递、启动预检和资源关闭 | 主要开发已完成 |
| 8.2 Durable 状态、租约、终态幂等 | PostgreSQL durable record、lease/reaper、retry、条件终态、迟到 finalize 防护已实现；本地故障验收通过 | Core 已完成；完整生产故障矩阵未完成 |
| 8.3 SSE Replay、事件契约、HITL | v2/v3、标准 stream modes、seq/event、cursor/replay、interrupt/resume 已实现并通过本地 SDK/REST 验收 | Core 已完成；跨网络和全部故障组合未完成 |
| 8.4 DeepAgent、Workspace、Subagent | workspace 根目录、绝对路径/`..`/符号链接校验及部分 policy 已实现 | 真实双 Worker、marker 恢复、能力交集仍未完成 |
| 8.5 RuntimeContext、认证、权限 | 签名 Context、Principal、issuer/audience、模型/工具 policy 校验已实现 | 代码基本完成；真实 platform JWT 跨 Worker/租户仍未完成 |
| 8.6 Langfuse/OTLP 观测、脱敏 | metadata allowlist、摘要/hash、trace context 和 fail-soft 基础逻辑已实现 | 真实查询及 exporter 故障矩阵仍未完成 |
| 8.7 部署、升级、性能、回滚 | lockfile、migration、health/readiness、runbook、graceful shutdown 已有 | 三版本隔离安装、backup/restore、性能、发布回滚未完成 |

其中 `platform-api` 的 runtime route、灰度比例、legacy/GraphHarbor 选择和 rollback
属于 `ai-agent-platform` 控制面适配，不属于 GraphHarbor 通用项目。GraphHarbor 不应
增加 `runtime_route`、legacy upstream 或平台灰度配置。

### 8.1 Graph Loader 与 per-Run Factory

**修改：**扩展 loader 识别静态 Graph、零参数 factory、一参数 `RunnableConfig` factory、异步
factory 和异步 context manager；启动时做签名/返回类型 fail-closed 预检；每次 Run 构造独立
config 并保留 metadata/tags/context/callbacks；支持 Run 级资源释放。

**测试：**真实异步 factory 收到唯一 Run metadata；并发 Run config 不污染；错误签名、缺失 export、
非 Graph 返回和 factory 异常均有稳定错误且不产生部分成功事件。

### 8.2 Durable 状态、租约和终态幂等

**修改：**统一 PostgreSQL Thread/Run/execution params/lease/checkpoint/terminal event/idempotency
schema；原子 lease、heartbeat、reaper 和有上限的 backoff；`finalize_run` 条件更新和唯一约束；
Redis 消息丢失由 PostgreSQL 扫描补偿；graceful shutdown 增加 drain、停止领取、重新入队和强制退出。

**测试：**kill -9、SIGTERM、cancel race、迟到 finalize SQL、重复 queue message、并发幂等键、Redis
短暂不可用和 PostgreSQL 可用性组合场景，均验证只保留一个终态。

### 8.3 SSE Replay、事件契约和 HITL

**修改：**持久化或可恢复 Thread `seq`；实现带 TTL/容量的 replay buffer、`since`、游标过旧错误和跨实例读取；
统一事件 envelope、schema version、event_id 去重；interrupt/resume/cancel/timeout 走同一状态机。

**测试：**两节点以上 graph 断线后 `since=N` 只收 `seq>N`；覆盖 buffer 溢出、游标过旧、Redis 重启、慢消费、
跨实例连接以及 HITL 各种终态；增加字段级 Runtime Run Event Contract 测试。

### 8.4 DeepAgent、Workspace 和 Subagent 安全边界

**修改：**Workspace 使用 `<tenant>/<project>/<thread>` server root；文件、Sandbox、MCP、写工具默认 deny；
Subagent 配置携带允许的 tool names、path prefixes、模型和预算，关闭未委派内置 agent；增加配额、清理和
符号链接检查。

**测试：**双 Thread、双 Worker、重启后的读写互不可见；`general-purpose`、未授权 MCP、绝对路径和 `..`
穿越均拒绝；取消/超时后临时文件和锁最终释放。

### 8.5 RuntimeContext、认证和 Platform Gateway

**修改：**增加版本化签名/JWT Context envelope，包含 principal、project、thread/run、model、tool policy、
trace ids 和过期时间；只信任 Platform 字段；统一认证失败、权限拒绝、版本不支持、模型/工具不允许和资源冲突错误码。

**测试：**有效 Context 跨 Worker 恢复；过期、错误签名、issuer/audience、未知 claim 和 protected override
全部拒绝；Platform gateway 幂等、超时、重试和 Run ID 映射可追踪。

### 8.6 Langfuse/OTLP 观测与脱敏

**修改：**Trace middleware 使用 metadata allowlist，注入 Platform/Runtime Run ID、Thread、Agent version、
model reference；Prompt/Response/Tool 内容只保留 mask/hash/长度摘要；exporter 使用有界队列和后台 flush，
失败只记日志/指标；暴露 queue lag、drop、export latency、flush timeout 指标。

**测试：**Langfuse API 断言关联字段、无凭证、无完整内容和无高基数泄漏；endpoint 不可达、401/429/5xx、队列满、
flush 超时仍能 finalize；Agent 原始异常与 exporter 异常同时发生时返回原始错误。

### 8.7 部署、升级、性能和回滚

**修改：**固定 lockfile 和 migration checksum；健康/就绪探针、SIGTERM drain、Worker 并发和资源上限；
Server、PostgreSQL、Redis、Exporter 分离故障域；按 Agent/tenant/project 灰度并保留 R6 回滚；明确 Checkpoint
迁移策略，不兼容时新 Thread 起步并保留旧路径只读。

**测试：**migration forward/backward、已有数据升级、失败回滚；固定负载下 Run p50/p95、queue lag、checkpoint
latency、SSE replay latency 和 DB/Redis 水位；kill -9、Redis 重启、PostgreSQL failover、模型 429/timeout、
Langfuse 故障；灰度 0% -> 1% -> 10% -> 50% -> 100% 及立即回退无丢 Run/事件/租户隔离。

## 9. 候选替换统一验收矩阵

| 门槛 | 最小可接受证据 | 失败处理 |
| --- | --- | --- |
| Agent factory | 真实异步 `get_agent(config)` 并发 Run，config 字段逐项可见 | 保留 R6 |
| Durable | PostgreSQL/Redis、kill -9、SIGTERM、checkpoint 接管 | 保留 R6 |
| 终态幂等 | 迟到 Worker、重复消息、条件 finalize | 保留 R6 |
| SSE | 两帧以上 replay、`since`、seq、event_id、过旧游标 | 保留 R6 |
| HITL | interrupt/resume/cancel/timeout 状态机和顺序 | 保留 R6 |
| DeepAgent | 双 Thread/双 Worker Workspace、Backend、Subagent policy | 保留 R6 |
| 权限 | 签名 Context 和越权拒绝 | 保留 R6 |
| Langfuse | API 关联字段、脱敏和 exporter 故障 | 保留 R6 |
| 性能 | 固定负载 p95、队列/DB/Redis 水位 | 限制灰度 |
| 运维 | migration、探针、优雅退出、回滚演练 | 禁止切换 |

结果状态：`pass` 为真实可重复证据；`partial` 为近似证据；`blocked` 为实验条件不足；`fail` 为实际违反契约；
只有全部硬门槛 `pass` 且 owner 批准独立切换 change 才能标记 `ready_for_cutover`，否则保持 `not_ready`。

## 10. 当前建议

GraphHarbor 的 per-Run async factory、终态条件写入、SSE replay、Context 签名等原先列为
阻塞的代码改造已经完成主要部分，并有固定 fixture、PostgreSQL/Redis 本地验收和官方
`langgraph dev` 对照证据。当前可将 GraphHarbor 定位为“Core runtime 已实现、受控环境
可用”的候选，不应再描述为“因不支持 `get_agent(config)` 而不兼容”。

但正式替代仍保持 `not_ready`。在以下证据完成前，不得替换正式 R6：

1. 对外部 `runtime-service/langgraph.json` 及其真实模型、MCP、skills、custom routes
   完成 HTTP/SDK E2E；固定 acceptance fixture 不能替代业务 graph 验收。
2. 完成 platform-issued JWT、RuntimeContext、双 Worker、双 tenant/project 的真实隔离
   和恢复验收。
3. 完成 DeepAgent workspace/backend/subagent 的跨 Worker marker 恢复、越界拒绝和资源清理。
4. 完成生产 Langfuse/OTLP 查询、字段脱敏及 exporter 401/429/5xx/timeout/队列满故障矩阵。
5. 通过第二主机或受控故障代理完成跨网络 SSE 断线、重连、cursor、无丢失和无重复验收。
6. 完成 Python 3.11/3.12/3.13 隔离安装、migration、backup/restore、性能基线和发布回滚。

`ai-agent-platform` 另行负责 platform-api 的 route ownership、灰度和 rollback；这些不
应回写为 GraphHarbor 的通用实现任务。只有 GraphHarbor 自身硬门槛与平台集成门槛全部
通过，并获得 owner approval，才可以把状态改为 `ready_for_cutover`。

## 11. 2026-08-31 复核与交接状态

### 11.1 GraphHarbor 本地状态

GraphHarbor 当前 revision 为 `a5fe7d8`（`docs(acceptance): add compatibility evidence`）。
本地工作区存在大量已修改和未跟踪文件，包含 runtime、认证、worker、workspace、观测、
测试、验收产物和 OpenSpec 变更；这些变更目前**尚未 commit，也尚未 push 到远端仓库**。

关键本地证据：

- `graphharbor/docs/current-capability-assessment.md`
- `graphharbor/artifacts/compatibility-result.json`
- `graphharbor/artifacts/fault-injection-result.json`
- `graphharbor/artifacts/official-langgraph-dev-p0-comparison.json`
- `graphharbor/openspec/changes/graphharbor-runtime-service-cutover/verification.md`
- `graphharbor/artifacts/cutover-gates.json`
- `graphharbor/artifacts/cutover-readiness.json`

当前 readiness artifact 仍为 `not_ready`，所有正式切换 gate 仍是 `not_run`，
`owner_approved=false`。这是因为生产验收证据尚未完整，不代表上述 Core 代码没有开发。

### 11.2 ai-agent-platform 本地状态

`ai-agent-platform` 当前 revision 为 `e2459af`（`docs(runtime): plan durable run R6`）。
该仓库也存在大量已修改和未跟踪文件，包含 `runtime-service` 适配、测试、部署、OpenSpec
以及本研究文档；这些变更目前**尚未 commit，也尚未 push 到远端仓库**。因此当前只有
本地工作区交接记录，没有完成正式代码仓库交接。

### 11.3 交接边界

| 归属 | 后续责任 |
|---|---|
| GraphHarbor | 通用 Agent Server、Run/Event/Checkpoint、Worker、SSE/HITL、RuntimeContext、workspace、观测和自身发布验收 |
| ai-agent-platform | `runtime-service` 的 graph/custom route/MCP/skills 适配、platform JWT 签发、平台权限及业务 E2E |
| platform-api | runtime route ownership、灰度、legacy/GraphHarbor 选择、Run 映射和 rollback |

在正式交接前，应由双方 owner 先确认本文结论和证据范围，再分别整理 commit、远端分支、
锁定依赖、部署参数、验收命令和未完成 gate。本文记录的是当前事实，不代表已经完成
代码提交、远端推送或生产切换批准。
