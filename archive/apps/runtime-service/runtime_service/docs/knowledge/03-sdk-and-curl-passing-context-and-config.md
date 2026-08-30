# 通过 SDK 或 curl 传入 `context` 和 `config`

## 1. 先说结论

在 LangGraph 里，`context` 和 `config` 都可以在调用时传。

常见入口有两类：

1. 直接调用本地 graph
2. 通过 LangGraph SDK / HTTP API 调用远端 graph

你当前最该掌握的是第二类，因为 `runtime_service` 大部分联调都走这个。

## 2. 先分清两种“context”

这是很多人刚接 LangGraph 时最容易搞混的点。

### 2.1 assistant 级 `context`

在 `assistants.create(...)` 或 `assistants.update(...)` 时传。

含义：

- 这是 assistant 的静态上下文
- 更像“给这个 assistant 配一套默认上下文”

SDK 当前签名里就有：

```python
assistants.create(graph_id, config=None, *, context=None, metadata=None, ...)
assistants.update(assistant_id, *, graph_id=None, config=None, context=None, ...)
```

### 2.2 run 级 `context`

在 `runs.create(...)` 或 `runs.stream(...)` 时传。

含义：

- 这是本次 run 的运行时上下文
- 更像“这次执行临时传入什么业务上下文”

SDK 当前签名里也有：

```python
runs.create(thread_id, assistant_id, *, input=None, config=None, context=None, ...)
runs.stream(thread_id, assistant_id, *, input=None, config=None, context=None, ...)
```

一句话：

- assistant 级 `context` 偏静态默认值
- run 级 `context` 偏本次执行 override

## 3. `config` 一般传什么

建议你把 `config` 理解成“执行配置壳子”。

常见传法：

```json
{
  "configurable": {
    "thread_id": "thread-1",
    "model_id": "gpt-4.1"
  },
  "metadata": {
    "source": "web"
  }
}
```

推荐实际放进去的内容：

- `configurable.thread_id`
- 服务私有 override
- `metadata`
- 必要时的 `recursion_limit`

不推荐长期依赖它来承载所有业务上下文。

## 4. 本地 graph 直接调用怎么传

### 4.1 直接 `invoke`

```python
from runtime_service.runtime.context import RuntimeContext

result = graph.invoke(
    {"messages": [{"role": "user", "content": "hello"}]},
    {"configurable": {"thread_id": "thread-1"}},
    context=RuntimeContext(
        user_id="u-1",
        project_id="p-1",
        model_id="openai:gpt-4.1",
    ),
)
```

### 4.2 `stream`

```python
for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "hello"}]},
    {"configurable": {"thread_id": "thread-1"}},
    context=RuntimeContext(
        user_id="u-1",
        project_id="p-1",
    ),
    stream_mode="values",
):
    print(chunk)
```

前提是 graph 本身声明了 `context_schema=RuntimeContext`。

## 5. LangGraph SDK 怎么传

## 5.1 创建 assistant 时传默认 `context`

```python
from langgraph_sdk import get_client

client = get_client(url="http://127.0.0.1:8123")

assistant = await client.assistants.create(
    graph_id="assistant",
    name="assistant-runtime-demo",
    context={
        "project_id": "project-1",
        "model_id": "openai:gpt-4.1",
    },
    config={
        "configurable": {
            "enable_tools": True,
        }
    },
)
```

适合：

- 你想给某个 assistant 固定一套默认模型 / 项目作用域
- 之后每次 run 不必重复传一遍

## 5.2 创建 run 时传本次 `context`

```python
run = await client.runs.create(
    thread_id="thread-1",
    assistant_id="assistant",
    input={
        "messages": [{"role": "user", "content": "帮我分析一下这个需求"}]
    },
    context={
        "user_id": "u-1",
        "project_id": "project-1",
        "model_id": "openai:gpt-4.1",
        "system_prompt": "你是资深测试分析助手",
    },
    config={
        "configurable": {
            "thread_id": "thread-1",
            "test_case_multimodal_parser_model_id": "iflow_qwen3-vl-plus",
        },
        "metadata": {
            "source": "runtime-web"
        }
    },
)
```

这个才是最常见的远端执行姿势。

## 5.3 流式 run

```python
async for part in client.runs.stream(
    thread_id="thread-1",
    assistant_id="assistant",
    input={
        "messages": [{"role": "user", "content": "继续"}]
    },
    context={
        "project_id": "project-1",
        "model_id": "openai:gpt-4.1",
    },
    config={
        "configurable": {
            "thread_id": "thread-1"
        }
    },
    stream_mode="values",
):
    print(part)
```

## 6. 你仓库里已经有的 SDK 样例

你仓库里当前已有 LangGraph SDK 调用样例，不过目前主要集中在 live 测试里，且主要还是 `config` 用得多，`context` 用得偏少。

参考：

- [services_test_case_service_project_scope_live.py](../../tests/services_test_case_service_project_scope_live.py)

例如你现在的 run 创建基本长这样：

```python
run = await client.runs.create(
    thread_id,
    assistant_id,
    input={"messages": [...]},
    config={"configurable": {"model_id": config.model_id}},
)
```

这个能跑，但如果后续要切到更标准的 `context-first`，就应该把公共业务字段逐步迁到 `context`。

## 7. curl 怎么传

下面给的是通用 LangGraph HTTP API 风格示例，字段命名和 SDK 对齐。

### 7.1 创建 assistant

```bash
curl -sS -X POST "http://127.0.0.1:8123/assistants" \
  -H "Content-Type: application/json" \
  -d '{
    "graph_id": "assistant",
    "name": "assistant-runtime-demo",
    "context": {
      "project_id": "project-1",
      "model_id": "openai:gpt-4.1"
    },
    "config": {
      "configurable": {
        "enable_tools": true
      }
    },
    "metadata": {
      "source": "curl-demo"
    }
  }'
```

### 7.2 创建 thread

```bash
curl -sS -X POST "http://127.0.0.1:8123/threads" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "source": "curl-demo",
      "graph_id": "assistant"
    }
  }'
```

### 7.3 创建 run

```bash
curl -sS -X POST "http://127.0.0.1:8123/threads/thread-1/runs" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "assistant",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": "帮我分析一下这个需求"
        }
      ]
    },
    "context": {
      "user_id": "u-1",
      "project_id": "project-1",
      "model_id": "openai:gpt-4.1",
      "system_prompt": "你是资深测试分析助手"
    },
    "config": {
      "configurable": {
        "thread_id": "thread-1",
        "test_case_multimodal_parser_model_id": "iflow_qwen3-vl-plus"
      },
      "metadata": {
        "source": "curl-demo"
      }
    }
  }'
```

### 7.4 resume 中断 run

```bash
curl -sS -X POST "http://127.0.0.1:8123/threads/thread-1/runs" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "assistant",
    "command": {
      "resume": {
        "decisions": [
          {
            "type": "approve"
          }
        ]
      }
    }
  }'
```

## 8. 传参时的推荐规则

建议你后面统一遵守下面这套：

### 规则一

线程类字段仍然放 `config.configurable`：

- `thread_id`
- `checkpoint_id`

### 规则二

公共业务运行参数优先放 `context`：

- `project_id`
- `user_id`
- `tenant_id`
- `model_id`
- `system_prompt`
- `temperature`
- `max_tokens`

### 规则三

服务私有 override 可暂时放 `config.configurable`：

- `test_case_multimodal_parser_model_id`
- `interaction_data_service_url`
- `interaction_data_service_token`

### 规则四

部署默认值和 secrets 不要通过接口传，仍由 `env` 负责。

## 9. 一个非常实际的提醒

只有 graph 显式声明了 `context_schema`，你传进去的 `context` 才真正有规范意义。

如果 graph 根本没接 `context_schema`，那你在 SDK / curl 里再怎么优雅地传 `context`，最后也可能只是“传了，但代码没认真消费”。

这也是你后面要回头规范 assistant graph 的原因。

## 10. 参考资料

- LangGraph Graph API
  - https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph runtime configuration
  - https://docs.langchain.com/oss/python/langgraph/use-graph-api
- LangGraph SDK `assistants.create` / `runs.create` 当前环境签名与 docstring
  - `apps/runtime-service/.venv` 当前安装版本实测
- 本仓库 SDK 样例
  - [services_test_case_service_project_scope_live.py](../../tests/services_test_case_service_project_scope_live.py)
