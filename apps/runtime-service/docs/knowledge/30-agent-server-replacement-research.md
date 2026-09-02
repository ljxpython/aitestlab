# Agent Server 替代方案调研：Aegra 与 GraphHarbor

- 文档类型：`Supporting / Research`
- 调研日期：2026-08-30；复核日期：2026-09-02
- 适用范围：`apps/runtime-service` 的 Durable Agent Server 选型
- 结论状态：GraphHarbor R6 Durable Core 与正式 acceptance 验证通过；生产替代仍为 `not_ready`

本文回答一个问题：在不购买官方 `langgraph-api` Durable Server 许可的前提下，
是否可以使用 Aegra 或 GraphHarbor 承担 Runtime 的 Agent Server / Durable 执行面。
本文不把第三方项目当作 Runtime 内核设计的权威，也不改变 10 号路线图和 14 号
Runtime Contract 的既定边界。

## 1. 先说结论

### 1.1 Aegra（历史候选，退出当前路线）

Aegra 曾作为官方 `langgraph-api` Durable Server 的候选进行调研，但不再属于当前 R6
实施路线。以下内容保留用于记录选型依据和未采用原因：

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

因此结论是：**Aegra 的 Spike 结果不转化为当前实现承诺；当前部署不使用 Aegra。**

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
`runtime-service` 生产依赖切换、Workspace 之外的资源恢复、真实 Langfuse/OTLP、跨网络 SSE、
迁移备份恢复、性能和发布回滚验收，不是异步 factory 缺失。

### 1.3 LangSmith 与官方 `langgraph-api` 不能混为一谈

| 能力 | Aegra | GraphHarbor | 本项目现状 |
| --- | --- | --- | --- |
| LangGraph Agent Protocol 执行面 | 候选，可自托管 | 当前 R6 采用 | GraphHarbor API 负责通用执行面 |
| Durable Thread/Run/Checkpoint | PostgreSQL + LangGraph Checkpoint | PostgreSQL + LangGraph Checkpoint | R6 Durable Core 已验证 |
| Worker、Lease、恢复 | Redis Worker + PostgreSQL Lease | Redis Queue/Lease + PostgreSQL | 独立 Worker，R6 Durable Core 已验证 |
| SSE、Replay、HITL、Cancel | 已实现并有测试目录 | 已实现并有测试目录 | GraphHarbor Core 已验证，生产组合仍有边界 |
| `async get_agent(config)` | **支持候选路径** | **已支持并通过固定 fixture 验证** | Runtime 的强约定 |
| DeepAgent 专用隔离 | 无平台级专用契约 | 无平台级专用契约 | Agent 代码显式装配 |
| Langfuse / OTLP Trace | OpenTelemetry fan-out | OpenTelemetry/OTLP 能力 | Langfuse 负责 Agent Trace |
| LangSmith Trace/UI/控制面 | 不提供完整替代 | 不提供完整替代 | 不采用 LangSmith 作为事实源 |
| LangSmith Agent Server License | 可移除 | 可移除 | 当前路线不依赖官方生产 Durable Server 授权 |
| License | Apache-2.0（仓库声明） | MIT（仓库声明） | 需做依赖与法务复核 |
| 当前成熟度 | Beta | Beta | 不能仅凭 README 宣称生产可用 |

这里的“可替代 LangSmith”只能理解为“替代 LangSmith Deployments/Agent Server 的自托管
执行面”。Aegra 和 GraphHarbor 都不能替代 LangSmith 的 Trace 查询产品、Studio、组织
控制面或商业服务。我们的 Trace 方案仍然是 Langfuse，Run/审计/权限事实源仍然是
`platform-api` 和 Runtime 的既定契约。

### 1.4 最终部署架构决策

当前 R6 采用以下四个独立部署单元：

```text
API + Worker + PostgreSQL + Redis
```

- `API` 提供 HTTP、鉴权、Thread/Run API 和 SSE；`Worker` 领取并执行 Run，写入
  Checkpoint 和终态。
- API 与 Worker 使用同一个 `runtime-service` 应用镜像，只是启动命令和进程角色不同。
  这样可以保持代码、Graph 配置、依赖和版本一致，同时允许 API 与 Worker 分别扩容。
- PostgreSQL 是 Thread、Run、Checkpoint、执行参数和终态的持久化事实源；Redis 只承担
  队列、Pub/Sub、实时通知和租约协调。二者均独立部署，不打包进 Runtime 应用镜像。
- 旧仓库 `langgraph_teach/src/docker_single` 的三容器路线是合理的；其中 `single` 表示
  单个后端应用交付面，不表示必须把 API、数据库和 Redis 合并为一个容器。
- GraphHarbor 是通用 Agent Server Core，负责 Agent Protocol、Durable Run、队列、恢复
  和事件服务，不承载本项目特有的 Platform、Runtime Context、Tool Policy 或业务逻辑。
- Aegra 不再作为并行替代方案。当前路线不依赖官方生产 Durable Server 授权，但仍必须
  单独完成 Runtime 的权限、数据、恢复、性能和发布验收。

该架构已经确定，但“采用 GraphHarbor”不等于“无条件生产完成”。GraphHarbor R6 Durable
Core 已有真实 API/Worker/PostgreSQL/Redis 证据；生产切流的剩余卡点单独记录在本文件第
12 节和 R6 验证 Harness 中，不通过改变容器拓扑规避。

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

GraphHarbor 已获批准作为 R6 的通用 Agent Server，并已从 PyPI 正式发布包安装到
`apps/runtime-service/.venv`。R6 真实验证使用 GraphHarbor 的 PostgreSQL/Redis API/Worker
链路；`langgraph dev` 只保留为本地 in-memory 对照，不能冒充 Durable Server 验收。

### Compatibility Spike（已完成，候选 R6.1）

本轮已完成 GraphHarbor 本地替换验证，未把 Runtime 私有业务逻辑复制进 GraphHarbor：

1. 使用当前 `reference_agent.get_agent(config)` 注册到 GraphHarbor（post20 已通过）；
2. 使用真实 DeepSeek 中转模型执行 Runtime Durable Run（已通过）；
3. 使用真实 PostgreSQL + Redis 验证 Thread、Run、Checkpoint、HITL、cancel、Worker restart、
   lease recovery、graceful shutdown 和 SSE replay（已通过）；
4. 验证 `RuntimeContext` 的签名、版本和拒绝语义（已通过）；
5. 验证 GraphHarbor `0.13.0.post20` 在 Runtime `.venv` 中为 PyPI 非 editable 安装（已通过）；
6. 验证 Thread Workspace 的跨 Worker 恢复、Thread/tenant 隔离、不可用根 fail-closed 和 API restart
  恢复监听（post20 已通过）。

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
| 8.3 SSE Replay、事件契约、HITL | v2/v3、标准 stream modes、seq/event、cursor/replay、interrupt/resume 已实现并通过本地 SDK/REST 验收 | Core 已完成；独立 Docker bridge network 的断线重连也通过；多主机丢包和全部故障组合未完成 |
| 8.4 DeepAgent、Workspace、Subagent | workspace 根目录、绝对路径/`..`/符号链接校验、文件大小/数量/总字节数 policy 和显式 Subagent 委派已实现 | Runtime Workspace acceptance 已通过真实 API、独立 Worker、PostgreSQL/Redis 的写入、Worker replacement、双 Thread 隔离、跨 tenant `404` 和不可用根 fail-closed；同端口 API restart 复跑未恢复监听；Subagent 真实委派与缩权测试通过；生产 Sandbox、真实 cleanup 调度和 provider 原子配额仍未完成 |
| 8.5 RuntimeContext、认证、权限 | 签名 Context、Principal、issuer/audience、模型/工具 policy 校验已实现 | 代码基本完成；真实 platform JWT 跨 Worker/租户仍未完成 |
| 8.6 Langfuse/OTLP 观测、脱敏 | metadata allowlist、摘要/hash、trace context、稳定 `event_dropped` Counter 和 fail-soft 基础逻辑已实现 | 本地 401/429/5xx/timeout/flush failure 矩阵和真实 smoke 已通过；真实服务端最终查询、SDK queue saturation、OTLP 和跨服务传播仍未完成 |
| 8.7 部署、升级、性能、回滚 | lockfile、migration、health/readiness、runbook、graceful shutdown、backup/restore、性能基线和 rollback dry-run 已有 | 三版本隔离安装、隔离 backup/restore、4 并发性能基线和不触碰数据卷的 rollback dry-run 已通过；真实发布回滚演练未完成 |

其中 `platform-api` 的 runtime route、灰度比例、legacy/GraphHarbor 选择和 rollback
属于 `ai-agent-platform` 控制面适配，不属于 GraphHarbor 通用项目。GraphHarbor 不应
增加 `runtime_route`、legacy upstream 或平台灰度配置。

### 8.8 Runtime MCP 真实恢复证据（2026-09-01）

Runtime 新增了 R6 专用 `mcp_probe`、独立 Streamable HTTP FastMCP provider 和
`scripts/r6_mcp_acceptance.py`。验收使用真实 GraphHarbor API、独立 Worker、PostgreSQL、Redis
和独立 MCP provider，不调用模型，避免模型波动掩盖资源恢复问题。

| 场景 | 证据位置 | 结果 |
|---|---|---|
| MCP discovery 与 tool invocation | `src/runtime_service/graphs/mcp_probe.py`；`scripts/r6_mcp_server.py`；`scripts/r6_mcp_acceptance.py` | `mcp_read` discovery、调用和结果持久化通过 |
| Worker 替换后重连 | `scripts/r6_mcp_acceptance.py` | 同一 Thread 使用同一 serialized binding，Run `success` |
| MCP provider 重启后恢复 | `scripts/r6_mcp_acceptance.py` | 新 MCP session discovery/call 通过 |
| 缺 binding、provider 不可达 | 同上；GraphHarbor `runtime_events` 终态记录 | 两个 Run 均为 `error`，稳定错误为 `runtime.mcp.recovery_failed` |
| 终态唯一性 | `_database_evidence()`；PostgreSQL `runtime_events` | 5 个 Run 各只有 1 个 terminal event |

这条证据证明本项目的 MCP adapter 与 GraphHarbor Thread metadata binding 在本地真实跨进程链路
上成立，不等于任意远程 MCP provider 的凭据、网络、租约和 SLA 已验收；生产远程 provider
故障矩阵仍保持未完成。

### 8.9 Durable Core 历史复核（post17，2026-09-02）

本节保留早期批次记录，不是当前版本真源。在 Runtime Service 的全新 `r6-verify` Compose 环境中，使用已发布的
`graphharbor==0.13.0.post17` / `graphharbor-runtime==0.13.0.post17`，API、独立 Worker、PostgreSQL
和 Redis 均正常运行。Compose 的 API/Worker 通过 `RUNTIME_GRAPH_CONFIG` 选择
`/app/langgraph.r6.json`，生产默认仍指向 `/app/langgraph.json`。

| 验收面 | 证据 | 结果 |
|---|---|---|
| Durable Core | `tests/durable -m durable`（timeout 专项单独关闭） | `14 passed, 1 skipped`；唯一 skip 为 timeout 专项 |
| Compose Worker lifecycle | `tests/durable/test_worker_lifecycle.py` | restart 与 SIGTERM 各 `1 passed`；使用 `recovery_demo` 并断言 checkpoint marker |
| 非优雅 Worker 接管 | `scripts/r6_worker_fault_injection.py --worker-signal SIGKILL` | checkpoint 恢复、`success`、唯一 terminal event |
| 优雅 Worker 接管 | 同脚本 `--worker-signal SIGTERM` | `shutdown_requeue=1`、checkpoint 恢复、唯一 terminal event |
| timeout 终态 | `timeout_demo` + `GRAPHHARBOR_RUN_TIMEOUT_SECONDS=10` | 唯一 `timeout/timeout` 终态 |

这组证据确认 GraphHarbor 可以承担本项目 R6 的通用 Agent Server/Durable Core 边界，但不把
GraphHarbor 变成 Runtime 专用 Server。Runtime 私有 Principal、Policy、Agent、Tool、MCP、Workspace
装配仍由本项目负责。生产 Sandbox、任意远程 MCP、Exporter queue saturation、真实发布回滚和
Platform 灰度切流仍未验收，因此整体生产替代继续保持 `not_ready`。

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
2. 完成 platform-issued JWT、RuntimeContext 的正式跨 Worker/tenant/project 验收。
3. 完成 DeepAgent Backend/Sandbox/Subagent 的跨 Worker 恢复、越界拒绝和资源清理；Thread
   Workspace 的 marker 恢复和隔离已有真实验收，不重复建设。
4. 完成生产 Langfuse/OTLP 查询、字段脱敏及 exporter 401/429/5xx/timeout/队列满故障矩阵。
5. 通过第二主机或受控故障代理补充跨网络丢包、多主机重连、无丢失和无重复验收；当前独立
   Docker bridge network 的 SSE 断线、重连和 cursor 已通过。
6. 完成真实发布回滚演练；migration、隔离 backup/restore、性能基线和 Python
   3.11/3.12/3.13 wheel 隔离安装与启动已经通过。

`ai-agent-platform` 另行负责 platform-api 的 route ownership、灰度和 rollback；这些不
应回写为 GraphHarbor 的通用实现任务。只有 GraphHarbor 自身硬门槛与平台集成门槛全部
通过，并获得 owner approval，才可以把状态改为 `ready_for_cutover`。

## 11. 2026-08-31 复核与交接状态

### 11.1 GraphHarbor 本地状态

GraphHarbor 当前使用已发布的 `0.13.0.post20` 双包；PyPI 可见且 Runtime 已完成版本真源切换。
GraphHarbor 的源码、测试和发布工作在其独立仓库维护，Runtime Service 不依赖开发机源码路径。

`post20` 正式镜像已完成独立 PostgreSQL/Redis/API/Worker 的 Durable、Worker takeover、Workspace、
MCP、API restart 和修复后 bridge SSE 验收。正式 acceptance 已通过，但外部资源、观测、回滚和 Platform
切流门槛仍未完成，因此不能把正式 acceptance 通过升级为生产切流通过。

关键本地证据：

- `graphharbor/docs/current-capability-assessment.md`
- `graphharbor/artifacts/compatibility-result.json`
- `graphharbor/artifacts/fault-injection-result.json`
- `graphharbor/artifacts/official-langgraph-dev-p0-comparison.json`
- `graphharbor/openspec/changes/graphharbor-runtime-service-cutover/verification.md`
- `graphharbor/artifacts/cutover-gates.json`
- `graphharbor/artifacts/cutover-readiness.json`

当前 readiness artifact 仍为 `not_ready`，正式切换 gate 仍未全部通过，`owner_approved=false`。
这是因为生产切流 hard gate 尚未闭合，不代表 `post20` 正式包或 R6 formal acceptance 未完成。

### 11.2 ai-agent-platform 本地状态

`ai-agent-platform` 当前基线 revision 为 `f959679`。
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

## 12. R6 实现对齐目录（2026-09-01）

本目录按 31 号文档的 Harness 协议记录当前事实。`✅` 只表示该原子要求已有真实、可失败且
可重复的证据；`partial`、`not-executed`、`blocked` 和 `deferred` 均为 `❌`。GraphHarbor
只承担通用 Agent Server 协议、持久化和 Worker 生命周期；Runtime 私有 Principal、Policy、
Agent、Tool、MCP 和 Workspace 装配继续由 `apps/runtime-service` 负责。

| Requirement ID | 要求 | 实现位置 | 测试/验证位置 | 当前证据 | Status | 是否实现 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `30-R6-001` | GraphHarbor 不解析 Runtime 私有结构，只透传通用 custom-auth user | `graphharbor/libs/langgraph-runtime-pg/src/langgraph_runtime_pg/auth.py`；`production_worker.py` | `graphharbor/libs/langgraph-runtime-pg/tests/test_production_contract.py`；`test_public_runtime.py` | 签名 user facts 恢复为 `configurable.langgraph_auth_user`，64 KiB/JSON/一致性校验通过 | `implemented-chain` | ✅ | Platform 正式 JWT 仍属 P1 |
| `30-R6-002` | 外部 `langgraph.json` 和 per-Run async factory 可加载 | `graphharbor/libs/langgraph-runtime-pg/src/langgraph_runtime_pg/graph_registry.py` | GraphRegistry probe；最终 wheel API/Worker smoke | `reference_agent` 真实模型执行成功；R6 专项配置中的注册 graph 可加载 | `implemented-chain` | ✅ | 生产配置仍只注册冻结的 `reference_agent` |
| `30-R6-003` | `sync/async/exit` durability 与 interrupt 参数进入真实 graph | `graph_executor.py`；`core_api.py`；`production_worker.py` | GraphHarbor full suite；Runtime durable suite | GraphHarbor `132 passed`；最新 Runtime durable `14 passed, 1 skipped`，真实 Runtime 已覆盖 sync/async/exit 和 ordered HITL；timeout 专项单独验收通过 | `implemented-chain` | ✅ | 无 |
| `30-R6-004` | Thread 重用、Run 完成和 checkpoint 可查询 | 同上；PostgreSQL Checkpointer | `tests/durable/test_agent_server_durable.py` | 两次 Run 使用同一 Thread，均 success 且 checkpoint 存在 | `implemented-chain` | ✅ | 无 |
| `30-R6-005` | 多次 interrupt 顺序恢复，非法 checkpoint fail-closed | `graph_executor.py`；`core_api.py` | `test_two_sequential_workflow_interrupts_resume_in_order`；`test_invalid_checkpoint_is_rejected` | 错误 interrupt ID 不重复 prepare；missing/foreign checkpoint 返回稳定错误 | `implemented-chain` | ✅ | 跨 Worker HITL 组合仍未执行 |
| `30-R6-006` | Worker SIGTERM/SIGKILL 从 checkpoint 接管并保持唯一终态 | `production_worker.py`；`run_store.py` | `apps/runtime-service/scripts/r6_worker_fault_injection.py` | 已发布 `post20` 镜像下，在停止常驻 Worker、保证单一消费者后，两种信号均从 `marker=checkpointed` 恢复为 success；SIGTERM 有 `shutdown_requeue=1`；terminal event 均为 1 | `implemented-chain` | ✅ | 未覆盖生产发布/回滚 |
| `30-R6-007` | 迟到 finalize、重复 queue 和 cancel race 只产生一个终态 | `run_store.py`；PostgreSQL 唯一索引 | `graphharbor/tests/acceptance_app/run_terminal_idempotency.py` | one claim、late finalize lost lease、terminal event=1、lease removed | `implemented-chain` | ✅ | 无 |
| `30-R6-008` | SSE cursor 单调、可 replay、去重、过期明确、断线不取消 | `redis_stream.py`；`core_api.py` | `apps/runtime-service/tests/durable/test_agent_server_durable.py`；`scripts/r6_network_sse_acceptance.sh`；`scripts/r6_network_sse_acceptance.py`；GraphHarbor protocol tests | Durable suite 已验证单调 cursor、`since` replay、去重、`cursor_expired` + `run_snapshot` 和 observer disconnect；修复后的 bridge Harness 已在发布 `post20` 镜像中通过 API/Worker readiness、唯一 Worker、cursor `4`、后续事件 `2` 和最终 `success` | `implemented-chain` | ✅ | 未覆盖第二主机/受控故障代理的跨网络丢包；不影响本地 formal acceptance 结论 |
| `30-R6-009` | cancel、timeout、Tool failure 收敛到唯一终态 | GraphHarbor `production_worker.py`、Run state；Runtime `failure_demo`/`timeout_demo` | cancel durable test；`test_unrecoverable_input_is_reported_as_run_failure`；`test_run_timeout_is_reported_once`；GraphHarbor timeout contract | 真实 API/独立 Worker/PG/Redis 下 failure 与 timeout `2 passed`；PG 分别为 `error/business_error`、`timeout/timeout`，terminal event 均为 1；cancel 幂等证据已通过 | `implemented-chain` | ✅ | 无 |
| `30-R6-010` | Thread Workspace 跨 Worker 恢复且跨 Thread/tenant 隔离 | `apps/runtime-service/src/runtime_service/services/workspace_demo/agent.py`；`graphs/workspace_demo.py` | `apps/runtime-service/scripts/r6_workspace_acceptance.py`；`tests/services/test_workspace_demo.py`；`scripts/r6_api_restart_probe.py` | 已发布 PyPI `post20` 下 Workspace 写入、Worker replacement、API `SIGTERM -> restart`、Thread/tenant 隔离和不可用根 fail-closed 均通过；业务 Run 各只有一个 terminal event | `implemented-chain` | ✅ | 不扩展为具体 Sandbox provider |
| `30-R6-016` | Backend/MCP/Sandbox 在 Worker 重启后可恢复并失败闭合 | Runtime `backend_demo`、MCP loader 和 Sandbox adapter；失败在资源恢复边界闭合 | `tests/services/test_resource_reconnect.py`；`tests/durable/test_backend_isolation.py` | Workspace 配额检查与写入已按 Thread 锁串行；MCP 本地 provider 有跨 Worker/provider 重启证据；Sandbox 403 已稳定 fail-closed；真实 provider 跨 Worker 恢复/cleanup 未执行 | `partial` | ❌ | 需要真实 Sandbox/远程 MCP provider、cleanup、配额和各资源失败矩阵 |
| `30-R6-011` | migration 幂等、并发串行、三套 schema readiness | `database.py`；`migrate.py`；Alembic `env.py` | GraphHarbor persistence/full suite；隔离数据库重复 migration；`scripts/r6_postgres_backup_restore.sh` | PostgreSQL 16.9 非 superuser role 下通过，无 Alembic drift；只读 dump 在临时 `pgvector/pg16` 实例恢复并可查询 | `implemented-chain` | ✅ | downgrade 和生产灾备演练未完成 |
| `30-R6-012` | 锁定可安装发布物并验证支持的 Python 版本 | `apps/runtime-service/pyproject.toml`；`uv.lock`；`deploy/Dockerfile` | PyPI install/startup matrix；Runtime package smoke | `0.13.0.post20` 双包已从 PyPI 安装，锁文件 source 为 registry，Docker build 确认 API/Worker 镜像内双包版本一致 | `implemented-chain` | ✅ | Runtime 生产 rollout 仍未执行 |
| `30-R6-013` | Langfuse/OTLP 字段、脱敏及 exporter 故障不影响 Run | `apps/runtime-service/src/runtime_service/observability/langfuse.py` | `tests/observability/test_langfuse.py`；`tests/observability/test_graph_tracing.py`；真实 Langfuse smoke | 本地 callback/flush 故障矩阵、正式 SDK queue-full 非阻塞测试和稳定 `event_dropped` Counter 已接入；真实 smoke 已查询最终 Trace/Observation，原始 Run 语义保持 | `partial` | ❌ | 真实服务端故障响应矩阵、独立 generic OTLP destination 和跨服务 propagation 尚未验收 |
| `30-R6-017` | 固定并发下记录 Run、首事件、完成和 checkpoint 延迟 | `scripts/r6_performance_baseline.py` | `scripts/r6_performance_baseline.py --runs 4` | 4 并发真实 API/Worker `disconnect_demo` 全部 success；首事件 p50/p95 `508.63/535.72 ms`，完成 p50/p95 `15648.47/15664.91 ms`，checkpoint p50/p95 `27.39/42.80 ms` | `implemented-chain` | ✅ | 未定义 SLO；queue lag 和 DB/Redis watermark 未由公共 API 暴露 |
| `30-R6-014` | Platform gateway 灰度、route ownership 和立即回滚 | `platform-api` 后续 governed change | 未执行 | R6 明确不修改 Platform；默认流量未切换 | `deferred` | ❌ | 由 P1/正式 cutover change 承担 |
| `30-R6-015` | 所有 hard gate 通过后才允许生产切流 | GraphHarbor `artifacts/cutover-gates.json`；OpenSpec verification | readiness 检查 | 当前保持 `not_ready`、`owner_approved=false` | `blocked` | ❌ | 完成所有剩余硬门槛并再次获得 owner 批准 |

### 12.1 Closure gate 对齐结果（2026-09-02）

| Gate | 是否实现 | 证据 | 结论 |
| --- | --- | --- | --- |
| `6.2` RuntimeContext producer/consumer | ✅ | GraphHarbor `auth.py`、`graph_executor.py`；`test_production_contract.py` | 严格拒绝未知 claims，并保持 Run/Thread/tenant/project 绑定 |
| `6.3` 显式端口 restart | ✅（本地修复 artifact） | `langhost/cli.py`、`test_cli.py`；Runtime `scripts/r6_api_restart_probe.py` | 同一容器内第一次 SIGTERM 后，第二次 serve 在端口 `18124` 就绪；探针返回 `status=passed` |
| `6.4` correlation/exporter fail-soft | ✅（focused） | GraphHarbor `test_production_contract.py`、`test_observability.py`；Runtime `tests/observability/` | API、queue、Worker 关联字段和 exporter/queue drop 语义已有局部闭合证据 |
| `6.5` 正式 R6 acceptance | ✅ | OpenSpec `verification.md`；`scripts/r6_network_sse_acceptance.sh` | 修复后只执行一次；API/Worker readiness、唯一 Worker、bridge SSE cursor/replay 和最终 `success` 均通过 |

### 12.2 post20 正式验收结果（Harness 修复前，2026-09-02）

本次使用已发布 `post20` 双包、镜像 `aitestlab-runtime-service:r6-post20`、独立 Compose project
`r6-verify-post20-20260902`、API `18134` 和独立 PG/Redis/Workspace 数据边界。readiness 通过后，
Durable smoke、单一消费者拓扑下的 Worker `SIGTERM/SIGKILL` 接管、Workspace、MCP 和 API 同端口
restart 均通过。Worker 故障结果均从 `marker=checkpointed` 恢复为 `success`，且 terminal event 唯一；
SIGTERM 记录 `shutdown_requeue=1`。

bridge network SSE 未通过本批次有效门禁：客户端建连时 Worker 尚未恢复，未收到 cursor；该结果标记
为 Harness `blocked`，没有重试。另有两次无效尝试已记录在 OpenSpec verification：一次漏传容器内
`RUNTIME_DURABLE_URL`，一次让常驻 Worker 与故障注入 Worker 共用 PostgreSQL。新 Harness
`scripts/r6_network_sse_acceptance.sh` 已固化 API `/ready`、唯一 Worker 和真实 Worker 功能探针门禁，
该历史批次中，修复后尚未执行新的正式验收，`6.5` 当时保持 blocked；当前结果见第 12.3 节。

本轮可重复命令和完整结果记录在两个 active change 的 `verification.md`。隔离基础设施、模型
凭据和数据库密码不写入文档；skip 仍按未执行处理。当前结论是：GraphHarbor 通用 Durable
Core 已获得真实 PostgreSQL/Redis/API/Worker 证据，跨网络 SSE、备份恢复和性能基线也有本地证据；
Runtime 生产资源、观测服务端故障、发布回滚和 Platform 切流尚未闭合，因此本历史批次只能标记为“部分通过”，不能结案。

### 12.3 post20 修复后正式验收结果（2026-09-02）

修复后的 `scripts/r6_network_sse_acceptance.sh` 使用已发布 `post20` 镜像，仅执行一次正式 bridge SSE
acceptance。API 与 Worker readiness、唯一 Worker 和真实 `recovery_demo` 功能探针通过后，两个独立 SDK
客户端完成断线、`Last-Event-ID` 恢复和最终 Run 收敛：

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
旧 `post19` 环境未触碰。由此 `30-R6-008` 和 `6.5` 均已完成；`6.6` 仍需 owner acceptance、spec sync
和 archive。外部 Sandbox/远程 MCP、观测服务端故障、真实 rollback 和 Platform 灰度仍使生产替代保持
`not_ready`。

## 13. 本轮讨论的边界结论（2026-09-02）

### 13.1 观测链路是否需要修改 GraphHarbor

结论不是“把 Langfuse 塞进 GraphHarbor”，而是把通用传输契约验收闭合。Runtime Service 和
GraphHarbor 的职责如下：

| 能力 | 责任方 | 是否需要触及 GraphHarbor | 说明 |
| --- | --- | --- | --- |
| `run_id`、`thread_id`、`graph_id`、`request_id` 的关联 | GraphHarbor + Runtime 集成 | 需要验证，缺失时才改 GraphHarbor | API 写入、Redis 排队、Worker 执行和事件必须保持同一关联字段 |
| `RunnableConfig.metadata/tags/context/callbacks` 的通用透传 | GraphHarbor | 需要 | 这是 per-Run factory 和跨 Worker 恢复的通用能力，不属于 Langfuse 私有逻辑 |
| API 到 Worker 的 trace context / correlation 传播 | GraphHarbor 的传输边界 + Runtime 适配 | 需要验证 | 只传播已批准的关联值，不能把公网 `traceparent` 变成可信身份 |
| Worker、队列、lease、checkpoint、Run 终态指标 | GraphHarbor | 需要 | 应提供通用结构化日志和指标，不定义本项目的 Tool 或 Model 字段 |
| Langfuse Client、metadata allowlist、脱敏和 exporter fail-soft | Runtime Service | 不需要 | 由 `runtime_service/observability/langfuse.py` 负责，不能复制到通用 Server |
| Model/Tool/Subagent 的业务语义、Tool Policy 和成本字段 | Runtime Service | 不需要 | GraphHarbor 只透传安全摘要，不能推断本项目的模型目录和权限 |
| Platform Audit、Trace 查询、灰度和 route ownership | `platform-api` / Platform | 不需要 | 这是控制面能力，不是通用 Agent Server 能力 |

因此，`runtime-service` **需要与 GraphHarbor 对齐通用的关联字段、Context 和生命周期指标，
但不需要把 Runtime 专属的 Langfuse 业务实现改进 GraphHarbor**。当前 GraphHarbor 已有
`langgraph_runtime_pg/observability.py` 和 `metrics.py`，Runtime 已有 Langfuse Callback 和
脱敏；`30-R6-013` 仍为 `partial`，原因是生产 exporter 故障矩阵、generic OTLP destination
和跨服务传播尚未完成。只有在这些契约的最小复现证明 GraphHarbor 丢字段、无法恢复或无法
暴露通用指标时，才在 GraphHarbor 仓库创建独立的 B3 change；不能因为观测还不够生产化就
增加 `LangfuseProvider`、Model Catalog 或 Runtime 专用字段。

### 13.2 Workspace、Backend、Sandbox、MCP 的定义和边界

这四个词不在同一抽象层：Workspace 是资源边界，Backend 是文件操作接口，Sandbox 是隔离
执行资源，MCP 是外部工具连接协议。

| 概念 | 是什么 | Runtime Service 负责什么 | GraphHarbor 只需负责什么 | 是否应在 GraphHarbor 解决 |
| --- | --- | --- | --- | --- |
| Workspace | 一个 Thread 可访问的受控文件路径空间，例如 `tenant/project/thread` | 路径解析、租户隔离、配额、TTL、清理、符号链接和客户端路径拒绝 | 保存/传递不透明的 binding，保证 Thread、Checkpoint 和 Worker 恢复时不串线 | 不实现业务 Workspace；只提供通用 metadata/context 和 Run 恢复载体 |
| Backend | Agent 读写文件、列目录、搜索、编辑和执行的具体适配器 | 选择 `StateBackend`、`FilesystemBackend`、Sandbox Backend，限制 Tool 和路径 | 按 Run 调用 graph factory，保留 `RunnableConfig`，在异常/cancel/shutdown 时释放 graph 资源 | 不建设 Backend Registry、DSL 或业务 Provider 编排 |
| Sandbox | 隔离的文件系统和命令执行环境，可带网络、CPU、生命周期限制 | 选择 Provider、创建/重连/销毁、ID 绑定、配额、网络和安全策略 | Worker 替换后仍能使用同一不透明 binding；资源不可用时形成唯一失败终态 | 不实现具体 Sandbox Provider；只有通用资源生命周期缺口才改 |
| MCP | Agent 与外部 Tool Server 之间的协议，包含 discovery、session 和 tool call | URL/凭据解析、名称冲突、required/optional、Tool Policy、session 生命周期和错误分类 | 允许 graph factory 每次 Run 重建 client，传播 binding，并持久化 Tool/MCP 失败事件 | 不实现 MCP Server、凭据中心或项目 Tool Registry |

跨 Worker 时只允许恢复可信的资源绑定，不允许把凭据、客户端对象、绝对路径或 Python 对象
写入 `RuntimeContext`、Checkpoint message 或客户端输入：

```text
Thread metadata / trusted persistence
  -> opaque workspace or sandbox binding
  -> Service-private factory creates Backend / MCP client
  -> GraphHarbor runs the graph and preserves Run/Event/Checkpoint semantics
```

GraphHarbor 的边界是“可恢复的通用执行载体”，不是“知道如何创建当前项目的文件系统、
Sandbox 或 MCP Provider”。

### 13.3 Open SWE 可借鉴的具体方案

Open SWE 对四类资源有可借鉴的实现，但它是 Coding Agent，不能整体搬进 GraphHarbor 或
Runtime Service：

| Open SWE 位置 | 可以借鉴 | 不应复制 |
| --- | --- | --- |
| `agent/server.py:ensure_sandbox_for_thread` | Thread metadata 持久化 `sandbox_id`；进程缓存只加速；Worker 重建从 binding 重连；区分“已删除”和“暂时不可达” | GitHub/Slack/Linear/PR 等 Coding Agent 控制面和全局 Sandbox Provider |
| `agent/utils/sandbox_state.py` | 用稳定的 Thread 级 proxy 表达 Sandbox，支持异步重连和替换 | Open SWE 的全局 proxy/cache 作为本项目公共 Registry |
| `CompositeBackend` | 默认 Workspace/Sandbox 与 `/skills/`、`/user-skills/`、`/organization-skills/` 分路 | 同时引入所有 Skill 来源、动态插件和用户组织管理 API |
| `ReadOnlyBackend` | Bundled Skill 由代码级只读边界保护，不能只依赖 Prompt | 把 Open SWE 的专用 Skill 管理流程复制为 Runtime 平台能力 |
| `agent/server.py:get_agent` 与 Subagent 配置 | Agent 组合根显式声明 Backend、Skill、Model、Tool 和 Subagent；子 Agent 主动缩权 | Git identity、repository checkout、任意 Shell 和完整 Coding Agent Tool 集 |
| `agent/utils/langfuse.py` | graph 入口注入 Callback、metadata 脱敏、exporter 不阻塞 Run | LangSmith/Langfuse 专属字段变成 GraphHarbor 公共 API |
| `MultiServerMCPClient` 的 async 生命周期 | discovery、调用和退出时关闭 session | module import 时 `asyncio.run()` 创建全局 MCP 单例 |

本项目已有的 `20-runtime-backend-workspace-skills-and-subagents-design.md` 将这些借鉴项
映射到 Service `agent.py`；GraphHarbor 只提供通用 graph 生命周期和 Durable Run，不承担
Open SWE 的业务资源编排。

### 13.4 `ai-test-agent-system-platform` 的参考价值

`/Users/lijiaxin/Downloads/ai-test-agent-system-platform` 对 Runtime 的 Agent 组合有参考
价值，对 GraphHarbor Core 没有直接替代价值。

| 参考位置 | 可用内容 | 采用条件 |
| --- | --- | --- |
| `start_server_postgres.py`、`langgraph.json` | 通过 `.env` 显式配置 `DATABASE_URI`、`REDIS_URI`，使用外部 PostgreSQL/Redis，并用 config 文件注册 graph | 迁移到本项目时必须改为显式的 Runtime 配置检查、独立数据库和独立 Redis namespace |
| 各 Agent 的 `FilesystemBackend`、`CompositeBackend`、`LocalShellBackend` | 说明如何在 Service 组合根挂载 Workspace、Skills 和受限执行后端 | `LocalShellBackend` 只能用于受控本地开发；生产必须接隔离 Sandbox 和路径/权限策略 |
| 各 Agent 的 `MultiServerMCPClient`、`load_mcp_tools` | MCP discovery、工具装配和调用流程的示例 | 必须改为 per-Run/per-Worker 生命周期、凭据服务端解析、冲突拒绝和故障分类 |
| `backend/app/utils/filesystem.py` | Service 层文件系统适配和路径规整的参考 | 不能绕过 Runtime Workspace policy 或共享宿主绝对路径 |

不能直接复制的部分：依赖官方 `langgraph_api.server:app` 的启动方式；module import 阶段的
`asyncio.run()`；大量 module-level Agent/MCP 单例；Windows 硬编码路径；权限过宽的本地
Shell；monkey patch；以及缺少 Worker lease/recovery、终态幂等、SSE replay 和 Context 签名
的实现。其 README 中的凭据示例也不能进入当前仓库。

结论：该项目可以作为 `runtime-service` 的 Backend/MCP/Agent 装配参考，不能作为 GraphHarbor
Durable Server 的实现来源，也不能证明无授权官方 Server 的生产能力。

### 13.5 本地 PostgreSQL/Redis、发布和回滚的决策入口

- 本地 PostgreSQL/Redis 账号可以使用，但必须是专用数据库用户、专用数据库和独立 Redis
  DB/namespace；不能使用未验证的 `postgres:postgres@localhost/langgraph` 默认值，也不能
  清理业务数据库。
- 最快的本地路径是 API/Worker 直接在宿主进程运行，显式设置 `DATABASE_URI`、`REDIS_URI`
  并先执行连接、权限和 migration 预检。容器 API/Worker 连接宿主资源需要独立 Compose
  host-infra 模式；当前 Compose 仍会启动自己的 `postgres`/`redis` 并通过 `depends_on`
  绑定它们，不能仅修改 host 变量就声称完成切换。
- GraphHarbor 可以直接构建并发布两个锁步包，发布凭据可由
  `~/.my_best/.env` 中的 `UV_PUBLISH_TOKEN` 注入当前 shell；不能打印 token。仓库现有
  Trusted Publishing/OIDC workflow 与 token 发布是两种互斥路径，不能混用或用本地 token
  假装通过 OIDC 门禁。
- 发布前必须通过版本一致性、lock、lint、build、wheel import、完整测试和目标 index 可见性
  检查；两个包一旦有一个成功发布，同版本不能覆盖，另一包失败必须递增版本或修复发布流程。
- 回滚是 Runtime API/Worker 回退到已验证旧镜像并保留 PostgreSQL/Redis 数据，不是向 PyPI
  重传旧版本。migration 不可逆时由数据库 owner 按备份恢复；回滚后必须验证 readiness、最小
  Run、Checkpoint 和 SSE replay。Platform 灰度和 route rollback 不归 GraphHarbor。

详细操作门禁统一收敛到：

- `docs/solve_problem/r6-validation-harness-and-failure-prevention.md`
- `apps/runtime-service/deploy/README.md`
- `docs/runbooks/container-update-runbook.md`
