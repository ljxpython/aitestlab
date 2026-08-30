# runtime_service 智能体脚手架模板（可直接复制）

本文提供三种当前可直接复用的脚手架模板：

- 模板 A：`create_agent`
- 模板 B：`LangGraph graph`
- 模板 C：`deepagent`

三种模板都应建立在同一套 runtime contract 上，而不是各自维护一套配置解析逻辑。

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

## 1) 模板 A：create_agent（推荐默认）

适合：

- 单智能体
- 工具调用
- HITL
- 多模态输入

当前参考范例：

- `runtime_service/agents/assistant_agent/graph.py`

```python
from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime

from runtime_service.middlewares.multimodal import MultimodalAgentState, MultimodalMiddleware
from runtime_service.runtime.modeling import apply_model_runtime_params, resolve_model
from runtime_service.runtime.options import build_runtime_config, merge_trusted_auth_context
from runtime_service.tools.registry import build_tools


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)

    tools = await build_tools(options)
    # 本地必备工具按需追加
    # tools.extend([...])

    return create_agent(
        model=model,
        tools=tools,
        middleware=[HumanInTheLoopMiddleware(interrupt_on={}), MultimodalMiddleware()],
        system_prompt=options.system_prompt,
        state_schema=MultimodalAgentState,
        name="<your_agent_name>",
    )


graph = make_graph
```

## 2) 模板 B：LangGraph graph（流程/状态流）

适合：

- 显式状态流
- step / handoff / 条件推进
- 需要让流程结构成为主要设计对象

当前参考范例：

- `runtime_service/agents/customer_support_agent/graph.py`
- `runtime_service/agents/customer_support_agent/tools.py`

```python
from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime

from runtime_service.runtime.modeling import apply_model_runtime_params, resolve_model
from runtime_service.runtime.options import build_runtime_config, merge_trusted_auth_context
from runtime_service.tools.registry import build_tools


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)
    base_tools = await build_tools(options)

    # 返回你自己的流程式 graph / agent builder
    return build_your_graph_agent(model, base_tools)


graph = make_graph
```

说明：

- 这里的关键不是 API 名字，而是“流程结构由 graph 侧主导”。
- 即使内部仍然复用 `create_agent(...)`，也应保持统一的 runtime 配置解析链路。

## 3) 模板 C：deepagent（复杂任务分解）

适合：

- 复杂任务分解
- skills / subagents
- 文件系统产物输出

当前参考范例：

- `runtime_service/agents/deepagent_agent/graph.py`

```python
from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime

from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import apply_model_runtime_params, resolve_model
from runtime_service.runtime.options import build_runtime_config, merge_trusted_auth_context
from runtime_service.tools.registry import build_tools


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    tools = await build_tools(options)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)

    return create_deep_agent(
        name="<your_deepagent_name>",
        model=model,
        tools=tools,
        system_prompt=options.system_prompt,
        context_schema=RuntimeContext,
        skills=[],
        subagents=[],
    )


graph = make_graph
```

## 4) 三种模板的共同要求

无论使用哪种模板，都应满足：

1. 使用统一工厂函数签名
2. 复用 `build_runtime_config(...)`
3. 平台工具优先走 `build_tools(options)`
4. graph 注册写入 `runtime_service/langgraph.json`
5. 若需要鉴权模式，再确认 `langgraph_auth.json`

## 5) 新 agent 落地清单

1. 先选最接近的模板
2. 复制后只改业务必要部分
3. 注册 graph id 和 `description`
4. 跑 `uv run python -m compileall runtime_service`
5. 补最小 pytest 或注册检查测试

## 6) 不推荐的做法

- 先写一层新的抽象模板，再套业务
- 为了形式统一强行把所有场景写成一种模板
- 绕开 `build_runtime_config(...)` 自己重新拼配置
- 把 `graph_legacy.py` 当作默认新模板
