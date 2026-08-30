# 10 分钟新增一个可运行 graph（现行标准）

目标：基于当前正式范式，10 分钟内新增一个最小可运行的静态 `create_agent(...)` graph。

## 1) 新建目录与文件

目录：

```text
runtime_service/agents/hello_demo_agent/
  __init__.py
  graph.py
  tools.py
```

`__init__.py`：

```python
from runtime_service.agents.hello_demo_agent.graph import graph
```

`tools.py`：

```python
from langchain_core.tools import tool


@tool("hello_tool", description="Return a short hello message.")
def hello_tool(name: str = "world") -> str:
    return f"hello, {name}"
```

`graph.py`：

```python
from langchain.agents import create_agent

from runtime_service.agents.hello_demo_agent.tools import hello_tool
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
    system_prompt="You are a hello demo agent.",
    enable_tools=False,
)

BASELINE_MODEL = resolve_model_by_id(DEFAULTS.model_id)
REQUIRED_TOOLS = [hello_tool]
PUBLIC_OPTIONAL_TOOLS: list[object] = []

graph = create_agent(
    model=BASELINE_MODEL,
    tools=REQUIRED_TOOLS,
    middleware=[
        RuntimeRequestMiddleware(
            defaults=DEFAULTS,
            required_tools=REQUIRED_TOOLS,
            public_tools=PUBLIC_OPTIONAL_TOOLS,
        ),
        MultimodalMiddleware(),
    ],
    system_prompt=DEFAULTS.system_prompt,
    state_schema=MultimodalAgentState,
    context_schema=RuntimeContext,
    name="hello_demo",
)
```

## 2) 注册到 `langgraph.json`

```json
"hello_demo": {
  "path": "./runtime_service/agents/hello_demo_agent/graph.py:graph",
  "description": "hello_demo 的用途说明"
}
```

## 3) 最小测试

新增 `runtime_service/tests/test_hello_demo_registration.py`：

```python
import json
from pathlib import Path


def test_hello_demo_registered() -> None:
    project_root = Path(__file__).resolve().parents[2]
    langgraph_file = project_root / "runtime_service" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "hello_demo" in data["graphs"]
```

## 4) 最小验证命令

```bash
uv run python -m compileall runtime_service/agents/hello_demo_agent/graph.py
uv run pytest runtime_service/tests/test_hello_demo_registration.py -q
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser
```

## 5) 这份模板的关键点

- graph 静态导出
- 不使用 `make_graph(...)`
- 显式声明 `context_schema=RuntimeContext`
- run-level 动态解析放进 `RuntimeRequestMiddleware`

## 6) 如果要继续演进

- 想走默认 assistant 范式：对照 `agents/assistant_agent/graph.py`
- 想走深任务分解：对照 `agents/deepagent_agent/graph.py`
- 想走显式步骤流：对照 `customer_support_agent`
