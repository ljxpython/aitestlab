# runtime_service 智能体脚手架模板（现行标准）

本文提供当前正式推荐的三种模板：

- 模板 A：静态 `create_agent(...)`
- 模板 B：静态 `builder.compile()`
- 模板 C：静态 `create_deep_agent(...)`

共同原则：

- graph 顶层静态导出
- 显式声明 `context_schema=RuntimeContext`
- run-level 动态行为通过 `RuntimeRequestMiddleware`
- graph-required tools 静态写死
- public optional tools 静态声明全集，运行时再筛选

## 0. 新增 agent 的最小目录

```text
runtime_service/agents/<your_agent>/
  __init__.py
  graph.py
  tools.py
  prompts.py
```

`__init__.py` 最小内容：

```python
from runtime_service.agents.<your_agent>.graph import graph
```

## 1) 模板 A：静态 `create_agent(...)`（默认推荐）

适合：

- 单智能体
- 线性对话流程
- 工具调用
- 多模态 / HITL / runtime 参数切换

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware

from runtime_service.middlewares.multimodal import (
    MultimodalAgentState,
    MultimodalMiddleware,
)
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.runtime.runtime_request_resolver import AgentDefaults


DEFAULTS = AgentDefaults(
    model_id="your_default_model_id",
    system_prompt="your default system prompt",
    enable_tools=True,
    public_tool_names=("word_count", "utc_now"),
)

BASELINE_MODEL = resolve_model_by_id(DEFAULTS.model_id)

REQUIRED_TOOLS = [
    required_tool_a,
    required_tool_b,
]

PUBLIC_OPTIONAL_TOOLS = [
    optional_tool_a,
    optional_tool_b,
]

graph = create_agent(
    model=BASELINE_MODEL,
    tools=[*REQUIRED_TOOLS, *PUBLIC_OPTIONAL_TOOLS],
    middleware=[
        RuntimeRequestMiddleware(
            defaults=DEFAULTS,
            required_tools=REQUIRED_TOOLS,
            public_tools=PUBLIC_OPTIONAL_TOOLS,
        ),
        HumanInTheLoopMiddleware(interrupt_on={}),
        MultimodalMiddleware(),
    ],
    system_prompt=DEFAULTS.system_prompt,
    state_schema=MultimodalAgentState,
    context_schema=RuntimeContext,
    name="<your_agent_name>",
)
```

要求：

- 不默认写 `make_graph(...)`
- 不在 graph 里自己解析 `config/configurable/env`
- `RuntimeRequestMiddleware` 放在前面

## 2) 模板 B：静态 `builder.compile()`

适合：

- 显式状态流
- handoff / 条件推进
- 流程本身就是主要设计对象

```python
from langgraph.graph import StateGraph

from runtime_service.runtime.context import RuntimeContext


builder = StateGraph(YourState, context_schema=RuntimeContext)

# add nodes / edges ...

graph = builder.compile()
```

要求：

- 流程编排归 graph
- run-level 模型 / 工具 / prompt 控制仍归 `RuntimeRequestMiddleware` 或等价公共解析层

## 3) 模板 C：静态 `create_deep_agent(...)`

适合：

- 复杂多步任务
- 文件系统产物
- deepagent skills / subagents

```python
from deepagents import create_deep_agent

from runtime_service.middlewares.multimodal import MultimodalMiddleware
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.runtime.runtime_request_resolver import AgentDefaults


DEFAULTS = AgentDefaults(
    model_id="your_default_model_id",
    system_prompt="your deepagent prompt",
    enable_tools=True,
    public_tool_names=("word_count",),
)

BASELINE_MODEL = resolve_model_by_id(DEFAULTS.model_id)

REQUIRED_TOOLS = [
    required_tool_a,
]

PUBLIC_OPTIONAL_TOOLS = [
    optional_tool_a,
]

graph = create_deep_agent(
    name="<your_deepagent_name>",
    model=BASELINE_MODEL,
    tools=[*REQUIRED_TOOLS, *PUBLIC_OPTIONAL_TOOLS],
    middleware=[
        RuntimeRequestMiddleware(
            defaults=DEFAULTS,
            required_tools=REQUIRED_TOOLS,
            public_tools=PUBLIC_OPTIONAL_TOOLS,
        ),
        MultimodalMiddleware(),
    ],
    system_prompt=DEFAULTS.system_prompt,
    context_schema=RuntimeContext,
    backend=backend,
    skills=[...],      # 静态
    subagents=[...],   # 静态
)
```

要求：

- `skills/subagents` 静态配置
- 不进入公开 runtime contract

## 4) 三种模板的共同要求

1. graph 顶层静态导出
2. 显式接入 `context_schema=RuntimeContext`
3. 用 `RuntimeRequestMiddleware` 做 run-level 动态解析
4. graph-required tools 静态写死
5. public optional tools 静态声明全集，再运行时筛选
6. `langgraph.json` 中必须写 `description`

## 5) 不推荐的做法

- 默认从 `make_graph(...)` 起手
- graph 内部自己反复拼 runtime 解析逻辑
- 动态向 graph 注入任意工具实现
- 把 `skills/subagents` 当公开 run 参数开放
