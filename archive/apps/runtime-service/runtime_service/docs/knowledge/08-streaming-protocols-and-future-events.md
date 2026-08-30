# LangGraph 流式协议与事件能力对照（历史补充）

> 本文保留用于解释本地流格式与远程协议的层次差异。涉及版本基线、Protocol v2、Durable Run、
> 发布或迁移决策时，必须以 [`09-langgraph-runtime-upgrade-and-event-migration.md`](09-langgraph-runtime-upgrade-and-event-migration.md)
> 为准；本文任何历史版本或“保留 legacy fallback”表述均不构成现行实施依据。

## 1. 先区分三个不是一回事的版本

| 名称 | 所在层 | 作用 |
| --- | --- | --- |
| `graph.stream(..., version="v2")` | 本地 Python graph API | 统一普通流式 chunk 的返回格式 |
| `graph.stream_events(..., version="v3")` | 本地 Python graph API | 提供消息、状态、子图和中断等事件投影 |
| Agent Protocol v2 | 远程 HTTP/SSE 协议 | 通过命令和事件订阅驱动远程运行 |

它们不能互相替代。尤其是 Agent Protocol v2 不是 `graph.stream(..., version="v2")`，也不是 `graph.stream_events(..., version="v3")`。

## 2. 本地 graph API

当前锁文件固定 `langgraph==1.2.11`，因此支持：

```python
graph.stream(input, stream_mode="updates", subgraphs=True, version="v2")
graph.stream_events(input, version="v3")
```

### 2.1 `stream` 的 v1 与 v2

`stream` / `astream` 默认仍为 `v1`。其 chunk 形状会随单、多 `stream_mode` 以及 `subgraphs` 是否开启而变化，常见为元组。

`version="v2"` 后，无论 mode 和子图设置如何，均返回统一的 `StreamPart`：

```python
{
    "type": "updates",
    "ns": ("subgraph_node:<task_id>",),
    "data": {"node": {"key": "value"}},
}
```

其中根图的 `ns` 为 `()`；非空 `ns` 表示子图来源。只需要统一 chunk 格式和子图路径时，优先选 v2，改动最小。

### 2.2 `stream_events` 的 v3

`stream_events(..., version="v3")` 返回的是可按事件类型消费的 run stream：

```python
stream = graph.stream_events(input, version="v3")

for message in stream.messages:
    print(message.text)

for subgraph in stream.subgraphs:
    print(subgraph.graph_name, subgraph.path)

if stream.interrupted:
    print(stream.interrupts)
```

它适合需要展示以下能力的产品层：

- 消息与 token 投影
- 子图或子 agent 生命周期
- HITL 中断与恢复状态
- 最终输出和全量状态快照

v3 不是 v2 的强制升级。已有消费者若只处理 `updates`、`messages`、`tasks`，先迁移到 `astream(..., version="v2")` 即可。

## 3. 本仓库当前状态

### 3.1 本地直接调用已收敛到 v2

`runtime_service` 的业务调试流消费者使用：

```python
async for part in agent.astream(
    input,
    stream_mode=["messages", "updates"],
    version="v2",
):
    ...
```

因此消费者读取 `part["type"]`、`part["ns"]` 与 `part["data"]`，不再依赖 v1 元组形状。
`astream_events(version="v3")` 仅在最小 harness 中验证内部投影，不能当作浏览器 HTTP 协议。

### 3.2 前端不是直接调用本地 graph

前端经 `platform-api` 调用 LangGraph SDK 的：

```python
client.runs.stream(thread_id, assistant_id, ...)
```

该 SDK 方法本身带有 `version` 参数，当前 SDK 默认值为 `"v1"`，并支持 `stream_subgraphs`。因此，远程普通 run 流不需要、也不存在 `client.runs.stream_event()` 或 `client.runs.stream_events()` 方法。

远程 SDK 的 `version` 和本地 `graph.stream(..., version=...)` 都涉及流格式，但必须对目标 Agent Server 做端到端兼容验证，不能只凭客户端 SDK 签名切换。

Agent Server 的实际部署基线必须由锁文件、固定镜像 digest 与实际 `/info` 输出共同证明；历史文档中的
`langgraph-api==0.11.1` 不能作为当前基线，也不得把本地 `version="v2"` 当作远程 Protocol v2 的验收。

## 4. 当前已有的事件订阅通道

`platform-api` 已公开并转发：

```text
POST /api/langgraph/threads/{thread_id}/commands
POST /api/langgraph/threads/{thread_id}/stream/events
```

后者是 Agent Protocol v2 的线程级 SSE 订阅端点：客户端先建立订阅，再通过 `commands` 发送 `run.start` 或 `input.respond`。它不是 `runs.stream` 的改名，也不是本地 Python 的 `stream_events` 对象。

该通道已由 Agent Web 以 Bearer `fetch + ReadableStream` 接入，使用 body `since` 主动重连；真实 Agent
Server 的 checkpoint、interrupt、replay 和 durability E2E 仍未完成，不能以本地 fixture 代替。

## 5. 推荐演进顺序

1. 本地调试和测试：将确有流式消费的 `astream` 调用迁至 `version="v2"`，修改消费者为读取 `part["type"]`、`part["ns"]`、`part["data"]`。
2. 正式 Agent Web：通过 `/threads/{thread_id}/commands` 与 `/threads/{thread_id}/stream/events` 操作和观察
   Durable Run；不用 `runs.stream` 作为新页面 fallback。
3. 远程普通流的历史消费者和 legacy 页面维持原状，直至共享环境复验、灰度与退役获得单独批准。
4. Protocol v2 event stream 稳定后，再决定是否接入官方 `useStream`；现阶段保持 gateway 与单一
   `RunEventsController` 状态模型。

legacy `runs.stream` 仍由旧页面使用，但它不是 Agent Web 的 fallback；退役必须另行获得批准。

## 6. Aegra 的位置

Aegra 已实现 Agent Protocol v2 的：

```text
POST /threads/{thread_id}/commands
POST /threads/{thread_id}/stream/events
```

并在该协议路径内部通过 `graph.astream_events(..., version="v3")` 产出事件。因此它能承载事件投影、子图事件和 HITL 所需的协议模型。

但 Aegra 对外发送的是 Agent Protocol v2 SSE 帧，不会把 Python 的 `stream.messages` 或 `stream.subgraphs` 对象原样交给浏览器。此外，它与本仓库现有 runtime contract 仍存在认证回调和若干 API 覆盖缺口；不能因为这一条事件能力就直接替换当前运行时。

## 7. 参考

- https://docs.langchain.com/oss/python/langgraph/streaming#stream-output-format-v2
- https://docs.langchain.com/oss/python/langgraph/event-streaming
- https://docs.langchain.com/langsmith/agent-server-api/streaming/protocol-v2-event-stream-sse
- https://docs.langchain.com/langsmith/agent-server-api/streaming/protocol-v2-command
