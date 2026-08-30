from __future__ import annotations

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

deepagent_graph = importlib.import_module("runtime_service.agents.deepagent_agent.graph")


def test_deepagent_graph_exports_static_graph_symbol() -> None:
    assert hasattr(deepagent_graph, "graph")
    assert not hasattr(deepagent_graph, "make_graph")
    assert hasattr(deepagent_graph.graph, "invoke")


def test_deepagent_graph_public_tools_delegate_to_shared_registry(
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
        deepagent_graph,
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

    resolved_tools = deepagent_graph._resolve_public_tools(settings)

    assert resolved_tools == ["public_tool"]
    assert captured == {
        "enable_tools": True,
        "requested_tool_names": ["word_count"],
    }
