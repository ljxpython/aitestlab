# LangGraph 流式协议与未来事件能力

## 1. 先区分三个不是一回事的版本

| 名称 | 所在层 | 作用 |
| --- | --- | --- |
| `graph.stream(..., version="v2")` | 本地 Python graph API | 统一普通流式 chunk 的返回格式 |
| `graph.stream_events(..., version="v3")` | 本地 Python graph API | 提供消息、状态、子图和中断等事件投影 |
| Agent Protocol v2 | 远程 HTTP/SSE 协议 | 通过命令和事件订阅驱动远程运行 |

它们不能互相替代。尤其是 Agent Protocol v2 不是 `graph.stream(..., version="v2")`，也不是 `graph.stream_events(..., version="v3")`。

## 2. 本地 graph API

当前环境安装 `langgraph==1.2.9`，因此支持：

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

### 3.1 本地直接调用仍是 v1

`runtime_service` 的测试与调试代码仍使用：

```python
async for mode, event in agent.astream(
    input,
    stream_mode=["messages", "updates"],
):
    ...
```

未传 `version="v2"`，因此这是默认 v1 元组格式。当前代码库没有 `stream_events(..., version="v3")` 的业务调用。

### 3.2 前端不是直接调用本地 graph

前端经 `platform-api` 调用 LangGraph SDK 的：

```python
client.runs.stream(thread_id, assistant_id, ...)
```

该 SDK 方法本身带有 `version` 参数，当前 SDK 默认值为 `"v1"`，并支持 `stream_subgraphs`。因此，远程普通 run 流不需要、也不存在 `client.runs.stream_event()` 或 `client.runs.stream_events()` 方法。

远程 SDK 的 `version` 和本地 `graph.stream(..., version=...)` 都涉及流格式，但必须对目标 Agent Server 做端到端兼容验证，不能只凭客户端 SDK 签名切换。

当前运行时锁定 `langgraph-api==0.11.1`。该版本已 EOL；在升级运行时前，不应将 remote `version="v2"` 视作已验收能力。

## 4. 当前已有的事件订阅通道

`platform-api` 已公开并转发：

```text
POST /api/langgraph/threads/{thread_id}/commands
POST /api/langgraph/threads/{thread_id}/stream/events
```

后者是 Agent Protocol v2 的线程级 SSE 订阅端点：客户端先建立订阅，再通过 `commands` 发送 `run.start` 或 `input.respond`。它不是 `runs.stream` 的改名，也不是本地 Python 的 `stream_events` 对象。

该通道是未来实现事件投影、子图生命周期和 HITL 的正确远程协议方向；但当前项目尚未对接到前端，也未针对现有 `langgraph-api==0.11.1` 完成端到端验收。

## 5. 推荐演进顺序

1. 本地调试和测试：将确有流式消费的 `astream` 调用迁至 `version="v2"`，修改消费者为读取 `part["type"]`、`part["ns"]`、`part["data"]`。
2. 远程普通聊天：继续使用 `client.runs.stream(...)`；运行时升级后，单独验证 `version="v2"`、`stream_subgraphs=True`、断线恢复和中断。
3. 前端事件体验：基于 `/threads/{thread_id}/commands` 加 `/threads/{thread_id}/stream/events` 实现，而非新增一个猜测的 SDK 方法。
4. 在协议 v2 事件流稳定后，再决定前端是否接入官方 `useStream`，或维持现有网关和状态管理。

每一步都应保留现有 `runs.stream` 作为回退通道，直到 token、工具调用、子图、HITL 恢复和断线重连均完成端到端验收。

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
