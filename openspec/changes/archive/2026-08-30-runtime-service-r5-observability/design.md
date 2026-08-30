## Context

R4 已完成 Runtime Agent Service 的显式 Tool、MCP、Backend、Skills 和 Subagents 接入，当前
仍缺少统一的 Agent Trace、结构化日志和运行指标。Open SWE 的
`agent/utils/langfuse.py` 展示了一个足够薄的接入方式：使用 LangChain Callback 自动捕获
Model、Tool 和嵌套 Runnable，再通过 `RunnableConfig` 的 metadata 关联 Session、User 和
Trace。

本变更只负责 `apps/runtime-service`。Runtime Service 仍以每个 Service 的
`async def get_agent(config: RunnableConfig) -> Pregel` 为组合根，不引入通用 Builder、Factory、
Provider、Registry 或 Observability Middleware。

## Goals / Non-Goals

**Goals:**

- 用 Langfuse Callback 捕获 Model、Tool 和 Subagent 的执行时间线、耗时、Token 和错误。
- 在 `get_agent()` 返回 Graph 前，将可信的 `run_id`、`thread_id`、`graph_id` 和已决议 Runtime
  摘要绑定到当前 Run。
- 保留调用方已有的 callbacks、metadata 和 tags，不覆盖、不改变 Agent 业务语义。
- 默认关闭 Langfuse；显式启用但配置不完整时 fail-closed；运行期网络、导出和 flush 故障
  fail-soft。
- 只记录安全 metadata 和低基数 tags，禁止上传完整 Prompt、响应、Tool 参数、凭据和私有源码。
- 为并发 Run、Subagent 传播、脱敏和 Langfuse 故障建立契约测试。

**Non-Goals:**

- 不实现 Platform API、Run Explorer、数据库事件表或 Langfuse 查询代理。
- 不把 Langfuse 当作 Durable Run、SSE、Checkpoint、Audit 或权限的事实源。
- 不复制 Open SWE 的 `traced_graph_factory()`、LangSmith tracing context 或其身份字段读取方式。
- 不实现正文采集、动态采样、跨进程 OTel parent 或自研 exporter。
- 不在每个 Tool、Model 或 Subagent 中手写重复埋点。

## Decisions

### 1. 采用 Open SWE 的薄 Callback 适配，但保持 Runtime 入口不变

`observability/langfuse.py` 只提供进程级初始化、单次 Run Callback 创建、metadata 合并和
有界关闭。Service 仍然直接构造原始 LangChain/LangGraph/Deep Agents Graph：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    graph = create_agent(
        model=model,
        tools=TOOLS,
        middleware=MIDDLEWARE,
        context_schema=RuntimeContext,
        name=GRAPH_ID,
    )
    return with_langfuse_tracing(graph, config, graph_id=GRAPH_ID)
```

不再增加 `build_agent()` 或 `traced_graph_factory()`，避免同一个 Service 出现两种导出契约。

### 2. 环境开关和 SDK 依赖

首期固定使用以下部署环境变量：

```text
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=...
LANGFUSE_TRACING_ENVIRONMENT=...
```

`LANGFUSE_ENABLED` 未设置或不是 `true` 时完全不导入 Langfuse SDK。启用时缺少 key 或
`LANGFUSE_BASE_URL` 视为配置错误，在 Runtime 启动/lifespan 初始化阶段失败；网络不可达不作为
启动探测条件。依赖固定在 `langfuse>=4.14,<5`，并随 lockfile 发布。

首期只支持 metadata 模式：SDK Callback 获得的完整输入输出在发送边界丢弃。未来若要开放
content 采集，必须另起变更，不能通过本次配置偷偷放开。

### 3. Client 和 Callback 生命周期

- Langfuse Client 在应用 lifespan 中懒加载一次，shutdown 时执行一次有界 flush。
- 每次 Graph invocation 创建一个 Callback，避免并发 Run 共享可变的 Run 状态。
- `with_langfuse_tracing()` 只构造绑定配置，不创建 Graph、不选择 Model/Tool、不读取数据库。
- 若当前调用方已经传入 callbacks、metadata 或 tags，新增值与原值合并；同名的 Runtime 可信
  字段不能被调用方覆盖。
- Callback/exporter 抛出的异常被记录为结构化告警并吞掉，不覆盖 Model、Tool、interrupt、
  cancel 或原始 Run 异常。

### 4. Trace metadata 信任边界

只允许以下字段进入根 Trace metadata：

```text
request_id, platform_trace_id, run_id, thread_id, graph_id,
assistant_id, assistant_version, deployment_version,
tenant_id, project_id, user_id, model_id, config_hash,
prompt_version, prompt_hash, policy_version
```

`tenant_id`、`project_id`、`user_id` 只能来自已经验证并解析的 `RuntimePrincipal`；不能从
普通 `RunnableConfig.metadata`、`configurable` 或客户端 header 推断身份。`run_id`、
`thread_id` 等关联 ID 可由 Agent Server 传入，但只用于关联，不用于鉴权。

tags 只放 `environment`、`service`、`graph_id`、`source` 和 `release` 等低基数值；身份和
每次 Run 的高基数 ID 不进入 tags。

### 5. 脱敏和采集边界

实现 Open SWE 中的常见 Header、Bearer、GitHub token、API key、Cookie 和 password pattern
脱敏作为纵深防御，但 metadata 模式不把完整 input/output 交给 exporter。允许记录模型 ID、
Token usage、耗时、工具名称、错误类型和受限长度的安全摘要；不得记录 JWT、密钥、完整 Prompt、
思维链、完整模型响应、完整 Tool 参数/结果或凭据对象。

### 6. 本地调试

Agent 单元测试和 `langgraph.demo.json` 使用 `LANGFUSE_ENABLED=false`，不需要 Platform API。
需要验证真实 Trace 时，开发者从 `~/.my_best/.env` 提供本地 `.env`，使用 `langgraph dev` 和
真实模型 E2E；测试不打印或提交 key。Langfuse 只用于对照时间线，Run 状态和 Agent 输出仍以
Graph/SSE/日志为准。

## Risks / Trade-offs

- [SDK Callback 行为随 Langfuse/LangChain 版本变化] -> 锁定 `<5` 版本，并用真实依赖执行
  Callback、并发和 Subagent 契约测试。
- [脱敏正则漏掉业务 secret] -> metadata 模式默认丢弃正文；正则仅作纵深防御，不宣称完整 DLP。
- [exporter 队列积压影响 Agent 延迟] -> 使用有界异步队列，满时丢弃 Trace 并计数，禁止阻塞主链路。
- [Subagent callback 未传播] -> 同进程调用链验证父 Trace 嵌套；无法可靠传播时降级为带
  `parent_run_id` metadata 的独立 Trace，不伪造父子关系。
- [Langfuse 不可用导致排障信息缺失] -> 结构化日志、Runtime 指标、SSE 和 Durable Run 仍独立工作。

## Migration Plan

1. 增加 `langfuse` 锁定依赖和 `observability/langfuse.py`，默认关闭。
2. 为 `reference_agent` 接入 Callback，并补充 metadata 合并、脱敏、并发和 fail-soft 测试。
3. 验证 `deep_agent_demo`、`mcp_demo` 和 `backend_demo` 的子调用仍沿 LangChain callback 链路出现。
4. 在本地真实模型 E2E 中检查 Session、Trace、Generation 和 Tool Observation；不接入 Platform API。
5. 失败回滚只需关闭 `LANGFUSE_ENABLED` 或移除 Graph 入口绑定，Agent 主链路不改变。

## Open Questions

- Langfuse SDK 当前版本对 `mask_otel_spans` 的具体 API 需要在实现阶段用锁定版本确认；若 API
  不稳定，保留 metadata 丢弃策略，不能退回上传正文。
- Runtime 指标最终接入的进程指标库尚未确定，本次只冻结指标名称和 fail-soft 语义，不新增指标框架。
