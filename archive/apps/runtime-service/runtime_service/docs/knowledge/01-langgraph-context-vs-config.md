# LangGraph 中 context、config、configurable 的使用与实践

## 1. 先说结论

LangGraph 官方并没有说 `context` 和 `configurable` 不能共用。

相反，官方当前范式是：

- `context` / `context_schema`：承载业务运行时上下文
- `config`：承载调用控制参数
- `config.configurable`：承载线程、checkpoint、平台注入值，以及少量运行时可配置项
- `ServerRuntime`：只在 graph factory 必须读取服务端上下文时使用

所以真正的问题不是“能不能共用”，而是“各自该装什么，别乱装”。

## 2. 官方语义怎么分

### 2.1 `context`

官方在 Graph API 和 Runtime 文档里把 `context` 定义为“运行时上下文”，特点是：

- 不属于 graph state
- 运行时注入
- 由 `context_schema` 约束结构
- 节点/工具/中间件通过 `runtime.context` 读取

典型适合放进 `context` 的值：

- `user_id`
- `tenant_id`
- `project_id`
- `model_id`
- `system_prompt`
- `temperature`
- `max_tokens`
- `top_p`
- `enable_tools`
- `tools`

一句人话：
这些值决定“这次业务要怎么跑”，但不应该和对话 state 混在一起。

### 2.2 `config`

`config` 来自 `RunnableConfig`，是 LangChain / LangGraph 的调用配置壳子。

典型字段包括：

- `tags`
- `metadata`
- `callbacks`
- `run_name`
- `max_concurrency`
- `recursion_limit`
- `configurable`

一句人话：
`config` 更像“这次执行的控制面板”，不是业务字段大仓库。

### 2.3 `config.configurable`

`configurable` 是 `config` 里最常被滥用的字段。

它在官方栈里依然很常见，尤其用来承载：

- `thread_id`
- `checkpoint_id`
- `assistant_id`
- `graph_id`
- 平台鉴权注入值
- 某些 run 级 override

在 LangGraph SDK 的 `runs.create(...)` 返回样例里，官方自己就会把很多平台字段放进 `config.configurable`。

所以别把它妖魔化。问题不在 `configurable` 本身，问题在于你把什么丢进去。

### 2.4 `ServerRuntime`

`ServerRuntime` 不是普通业务参数容器，它是 graph factory 的服务端上下文。

适合它的场景：

- factory 构图时必须读取 user / store / access context
- 需要按服务端访问上下文装配资源

不适合它的场景：

- 前端传入模型参数
- 一次 run 的业务开关
- 客户端随手传入的租户或项目字段

一句人话：
`ServerRuntime` 是服务端工厂上下文，不是业务配置垃圾桶。

## 3. 官方推荐的基本范式

### 3.1 Graph API / StateGraph

官方推荐先声明 `context_schema`，然后在节点里通过 `runtime.context` 读取：

```python
from dataclasses import dataclass
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime


@dataclass
class Context:
    user_id: str
    model_id: str


def node(state, runtime: Runtime[Context]):
    user_id = runtime.context.user_id
    model_id = runtime.context.model_id
    ...


builder = StateGraph(State, context_schema=Context)
graph = builder.compile()
```

调用时再传：

```python
graph.invoke(
    inputs,
    {"configurable": {"thread_id": "thread-1"}},
    context=Context(user_id="u-1", model_id="gpt-4.1"),
)
```

### 3.2 `create_agent(...)`

`create_agent(...)` 同样支持：

- `context_schema`
- `state_schema`
- `middleware`
- `checkpointer`
- `store`

如果你要让 middleware、动态 prompt、工具 runtime 拿到 typed context，就应该传 `context_schema`。

## 4. 结合本仓库，应该怎么分层

推荐职责划分如下。

### 4.1 `RuntimeContext`

建议承载：

- 身份与租户信息
  - `user_id`
  - `tenant_id`
  - `role`
  - `permissions`
  - `project_id`
- 业务运行参数
  - `environment`
  - `model_id`
  - `system_prompt`
  - `temperature`
  - `max_tokens`
  - `top_p`
  - `enable_tools`
  - `tools`
  - `skills`
  - `subagents`

也就是你现在 [context.py](../../runtime/context.py) 定义的大方向，本质上是对的。

### 4.2 `config.configurable`

建议只保留：

- 平台线程字段
  - `thread_id`
  - `checkpoint_id`
  - `assistant_id`
  - `graph_id`
- 平台鉴权注入字段
  - `langgraph_auth_user_id`
  - `langgraph_auth_user`
- 少量服务私有开关
  - `test_case_multimodal_parser_model_id`
  - `test_case_backend_root_dir`
  - `interaction_data_service_url`
  - `interaction_data_service_token`

也就是说：
公共业务运行参数尽量别长期依赖 `configurable`，但服务私有 override 还可以放。

### 4.3 `env`

只放部署默认值和 secrets：

- `APP_ENV`
- `MODEL_ID`
- `SUPABASE_*`
- 三方 API key
- 服务地址默认值

一句话：
`env` 负责“部署默认值”，不负责“每次 run 的业务输入”。

## 5. 推荐优先级

本仓库建议采用下面这个优先级：

1. 服务端可信注入值
2. `context`
3. 服务私有 `config.configurable`
4. `env`
5. 代码默认值

这比“所有东西都从 `configurable` 读”要干净得多。

## 6. 现在这个仓库哪里有点跑偏

### 6.1 文档主张是 `context-first`

[02-architecture.md](../standards/02-architecture.md) 已经写得很明确：

- 运行时参数统一通过 `context` 传入
- `config` 不承担业务运行时配置主入口职责

这个方向是对的。

### 6.2 旧的 `configurable-first` 路径已经删除

之前仓库里确实存在“从多层混合读取运行时参数”的旧实现，容易把系统拖回 `configurable-first`。

现在这条旧路径已经删除，主路径统一收敛为：

- `RuntimeContext`
- `RuntimeRequestMiddleware`
- `resolve_runtime_settings(...)`

### 6.3 当前推荐样板已经切到静态 graph + typed context

当前 [assistant_agent/graph.py](../../agents/assistant_agent/graph.py)：

- 顶层静态导出 `graph = create_agent(...)`
- 显式传入 `context_schema=RuntimeContext`
- 通过 `RuntimeRequestMiddleware` 统一处理运行时模型 / prompt / tools

这也是当前仓库的正式标准；`research_agent/graph.py`、`test_case_service/graph.py` 已同步采用同一路线。

## 7. 最稳妥的项目落地规则

建议你后续统一成下面这套。

### 规则一

公共业务运行参数优先走 `RuntimeContext`。

### 规则二

`configurable` 只保留线程、平台、鉴权、服务私有 override。

### 规则三

`ServerRuntime` 只有在 factory 期必须读服务端上下文时才用。

### 规则四

业务逻辑、工具、middleware 尽量通过 `runtime.context` 取值，而不是遍地 `read_configurable(config)`。

### 规则五

旧的 `build_runtime_config(...)` 路径已经删除。

当前标准就是：

- 主路径只吃 `context`
- `configurable` 只做平台通道和服务私有字段

## 8. 一个推荐心智模型

可以把三者理解成三层：

- `context`
  - 这次业务要怎么跑
- `config`
  - 这次调用怎么控
- `ServerRuntime`
  - 服务端工厂怎么看你

别把三层搅成一锅粥，后面架构就干净很多。

## 9. 参考资料

- LangGraph Graph API
  - https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph Use Graph API / runtime configuration
  - https://docs.langchain.com/oss/python/langgraph/use-graph-api
- LangGraph Add memory
  - https://docs.langchain.com/oss/python/langgraph/add-memory
- LangSmith / LangGraph graph rebuild at runtime
  - https://docs.langchain.com/langsmith/graph-rebuild
- 本仓库参考实现
  - [context.py](../../runtime/context.py)
  - [runtime_request_resolver.py](../../runtime/runtime_request_resolver.py)
  - [assistant_agent/graph.py](../../agents/assistant_agent/graph.py)
  - [research_agent/graph.py](../../agents/research_agent/graph.py)
