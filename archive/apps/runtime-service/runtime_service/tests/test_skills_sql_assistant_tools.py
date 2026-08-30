from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, SystemMessage

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.agents.skills_sql_assistant_agent import (  # noqa: E402
    tools as sql_tools,
)
from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.runtime.runtime_request_resolver import (  # noqa: E402
    ResolvedRuntimeSettings,
)

skills_sql_graph_module = importlib.import_module(
    "runtime_service.agents.skills_sql_assistant_agent.graph"
)


def _invoke_tool(tool_obj: Any, args: dict[str, Any]) -> Any:
    return getattr(tool_obj, "invoke")(args)


def test_load_skill_sales_analytics() -> None:
    text = _invoke_tool(sql_tools.load_skill, {"skill_name": "sales_analytics"})
    assert "Loaded skill: sales_analytics" in text
    assert "customers" in text
    assert "orders" in text


def test_load_skill_unknown() -> None:
    text = _invoke_tool(sql_tools.load_skill, {"skill_name": "unknown_skill"})
    assert "not found" in text
    assert "sales_analytics" in text
    assert "inventory_management" in text


def test_skill_middleware_registers_load_tool() -> None:
    middleware = sql_tools.SkillMiddleware()
    assert sql_tools.load_skill in middleware.tools


def test_skill_middleware_wrap_model_call_adds_skill_catalog() -> None:
    middleware = sql_tools.SkillMiddleware()
    request = ModelRequest(
        model=object(),
        messages=[],
        system_message=SystemMessage(content="Base prompt"),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        system_prompt = updated_request.system_prompt or ""
        assert "Base prompt" in system_prompt
        assert "## Available Skills" in system_prompt
        assert "sales_analytics" in system_prompt
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_skill_middleware_awrap_model_call_adds_skill_catalog() -> None:
    middleware = sql_tools.SkillMiddleware()
    request = ModelRequest(
        model=object(),
        messages=[],
        system_message=SystemMessage(content="Base prompt"),
    )

    async def handler(updated_request: ModelRequest) -> ModelResponse:
        system_prompt = updated_request.system_prompt or ""
        assert "Base prompt" in system_prompt
        assert "## Available Skills" in system_prompt
        assert "inventory_management" in system_prompt
        return ModelResponse(result=[AIMessage(content="ok")])

    response = asyncio.run(middleware.awrap_model_call(request, handler))

    assert response.result[0].text == "ok"


def test_build_skills_sql_assistant_agent_runnable() -> None:
    class DummyModel:
        def bind(self, **kwargs: Any) -> Any:
            del kwargs
            return self

    agent = sql_tools.build_skills_sql_assistant_agent(DummyModel())
    assert hasattr(agent, "invoke")


def test_langgraph_registers_skills_sql_assistant_demo() -> None:
    langgraph_file = _PROJECT_ROOT / "runtime_service" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "skills_sql_assistant_demo" in data["graphs"]


def test_skills_sql_graph_exports_static_graph_symbol() -> None:
    assert hasattr(skills_sql_graph_module, "graph")
    assert not hasattr(skills_sql_graph_module, "make_graph")
    assert hasattr(skills_sql_graph_module.graph, "invoke")


def test_skills_sql_graph_public_tools_delegate_to_shared_registry(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_build_runtime_tools(
        *,
        enable_tools: bool,
        requested_tool_names: list[str] | None,
    ) -> list[str]:
        captured["enable_tools"] = enable_tools
        captured["requested_tool_names"] = requested_tool_names
        return ["public_tool"]

    monkeypatch.setattr(
        skills_sql_graph_module,
        "build_runtime_tools",
        fake_build_runtime_tools,
    )

    settings = ResolvedRuntimeSettings(
        context=RuntimeContext(),
        model="runtime-model",
        system_prompt="",
        enable_tools=True,
        requested_public_tool_names=["word_count"],
    )

    resolved_tools = skills_sql_graph_module._resolve_public_tools(settings)

    assert resolved_tools == ["public_tool"]
    assert captured == {
        "enable_tools": True,
        "requested_tool_names": ["word_count"],
    }
