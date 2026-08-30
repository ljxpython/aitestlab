from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.agents.assistant_agent import (  # noqa: E402
    prompts as assistant_prompts,
)
from runtime_service.agents.assistant_agent import tools as assistant_tools  # noqa: E402

assistant_graph_module = importlib.import_module(
    "runtime_service.agents.assistant_agent.graph"
)


def test_langchain_concepts_demo_tools_shape() -> None:
    class DummyModel:
        def bind(self, **kwargs: Any) -> Any:
            del kwargs
            return self

    demo_tools = assistant_tools.build_langchain_concepts_demo_tools(DummyModel())
    tool_names = {getattr(tool_obj, "name", "") for tool_obj in demo_tools}
    assert tool_names == {
        "ask_knowledge_specialist",
        "ask_ops_specialist",
        "ask_email_specialist",
        "request_human_approval",
    }


def test_request_human_approval_tool_message() -> None:
    class DummyModel:
        def bind(self, **kwargs: Any) -> Any:
            del kwargs
            return self

    demo_tools = assistant_tools.build_langchain_concepts_demo_tools(DummyModel())
    tool_map = {getattr(tool_obj, "name", ""): tool_obj for tool_obj in demo_tools}
    result = tool_map["request_human_approval"].invoke(
        {"action": "deploy_canary", "details": "deploy 5% canary"}
    )
    assert "Approval checkpoint reached" in result


def test_resolve_assistant_system_prompt_demo_mode() -> None:
    base = "You are a production assistant."
    prompt = assistant_prompts.resolve_assistant_system_prompt(base, demo_enabled=True)
    assert assistant_prompts.LANGCHAIN_CONCEPTS_DEMO_PROMPT in prompt


def test_langgraph_registers_assistant_graph() -> None:
    langgraph_file = _PROJECT_ROOT / "runtime_service" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "assistant" in data["graphs"]


def test_assistant_graph_exports_static_graph_symbol() -> None:
    assert hasattr(assistant_graph_module, "graph")
    assert not hasattr(assistant_graph_module, "make_graph")
    assert hasattr(assistant_graph_module.graph, "invoke")
