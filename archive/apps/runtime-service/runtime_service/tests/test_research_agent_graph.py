from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.runtime.runtime_request_resolver import (  # noqa: E402
    ResolvedRuntimeSettings,
)
from runtime_service.middlewares.multimodal import (  # noqa: E402
    MULTIMODAL_PARSER_MODEL_ID_ENV,
)

research_agent_graph = importlib.import_module("runtime_service.agents.research_agent.graph")


def _settings(*, enable_tools: bool = False) -> ResolvedRuntimeSettings:
    return ResolvedRuntimeSettings(
        context=RuntimeContext(),
        model="runtime-model",
        system_prompt="",
        enable_tools=enable_tools,
        requested_public_tool_names=["word_count"],
    )


def test_research_graph_exports_static_graph_symbol() -> None:
    assert hasattr(research_agent_graph, "graph")
    assert not hasattr(research_agent_graph, "make_graph")
    assert hasattr(research_agent_graph.graph, "invoke")


def test_research_graph_middleware_uses_shared_env_default(monkeypatch: Any) -> None:
    monkeypatch.setenv(MULTIMODAL_PARSER_MODEL_ID_ENV, "research_env_default")

    reloaded = importlib.reload(research_agent_graph)
    assert reloaded.RESEARCH_MIDDLEWARE._parser_model_id == "research_env_default"

    monkeypatch.delenv(MULTIMODAL_PARSER_MODEL_ID_ENV, raising=False)
    importlib.reload(reloaded)


def test_research_graph_resolve_required_tools_includes_runtime_and_private_tools(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        research_agent_graph,
        "build_research_runtime_tools",
        lambda: ["runtime_tool"],
    )
    monkeypatch.setattr(
        research_agent_graph,
        "get_research_private_tools",
        lambda config=None: ["private_tool"],
    )

    resolved_tools = research_agent_graph._resolve_required_tools(_settings())

    assert resolved_tools == ["runtime_tool", "private_tool"]


def test_research_graph_aresolve_required_tools_includes_runtime_and_private_tools(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        research_agent_graph,
        "build_research_runtime_tools",
        lambda: ["runtime_tool"],
    )

    async def fake_private_tools(config: dict[str, Any]) -> list[str]:
        del config
        return ["private_tool"]

    monkeypatch.setattr(
        research_agent_graph,
        "aget_research_private_tools",
        fake_private_tools,
    )

    resolved_tools = asyncio.run(
        research_agent_graph._aresolve_required_tools(_settings())
    )

    assert resolved_tools == ["runtime_tool", "private_tool"]


def test_research_graph_resolve_public_tools_uses_shared_registry(
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
        research_agent_graph,
        "build_runtime_tools",
        fake_build_runtime_tools,
    )

    resolved_tools = research_agent_graph._resolve_public_tools(
        _settings(enable_tools=True)
    )

    assert resolved_tools == ["public_tool"]
    assert captured == {
        "enable_tools": True,
        "requested_tool_names": ["word_count"],
    }
