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

test_case_graph_v2 = importlib.import_module(
    "runtime_service.services.test_case_service_v2.graph"
)


def _settings(
    *, project_id: str | None = None, system_prompt: str = ""
) -> ResolvedRuntimeSettings:
    return ResolvedRuntimeSettings(
        context=RuntimeContext(project_id=project_id),
        model="runtime-model",
        system_prompt=system_prompt,
        enable_tools=False,
        requested_public_tool_names=[],
    )


def test_test_case_v2_graph_exports_static_graph_symbol() -> None:
    assert hasattr(test_case_graph_v2, "graph")
    assert not hasattr(test_case_graph_v2, "make_graph")
    assert hasattr(test_case_graph_v2.graph, "invoke")


def test_test_case_v2_graph_build_system_prompt_uses_runtime_project_id(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_build_test_case_system_prompt(
        *,
        runtime_system_prompt: str | None = None,
        current_project_id: str | None = None,
    ) -> str:
        captured["runtime_system_prompt"] = runtime_system_prompt
        captured["current_project_id"] = current_project_id
        return "resolved prompt"

    monkeypatch.setattr(
        test_case_graph_v2,
        "build_test_case_system_prompt",
        fake_build_test_case_system_prompt,
    )

    prompt = test_case_graph_v2._build_system_prompt(
        _settings(project_id="project-123", system_prompt="runtime prompt")
    )

    assert prompt == "resolved prompt"
    assert captured == {
        "runtime_system_prompt": "runtime prompt",
        "current_project_id": "project-123",
    }


def test_test_case_v2_graph_resolve_required_tools_includes_knowledge_and_service_tools(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        test_case_graph_v2,
        "_resolve_service_config_for_run",
        lambda: "service-config",
    )
    monkeypatch.setattr(
        test_case_graph_v2,
        "get_test_case_knowledge_tools",
        lambda service_config: ["knowledge_tool"],
    )
    monkeypatch.setattr(
        test_case_graph_v2,
        "build_test_case_service_tools",
        lambda service_config: ["service_tool"],
    )

    resolved_tools = test_case_graph_v2._resolve_required_tools(_settings())

    assert resolved_tools == ["knowledge_tool", "service_tool"]


def test_test_case_v2_graph_aresolve_required_tools_includes_knowledge_and_service_tools(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        test_case_graph_v2,
        "_resolve_service_config_for_run",
        lambda: "service-config",
    )

    async def fake_knowledge_tools(service_config: Any) -> list[str]:
        del service_config
        return ["knowledge_tool"]

    monkeypatch.setattr(
        test_case_graph_v2,
        "aget_test_case_knowledge_tools",
        fake_knowledge_tools,
    )
    monkeypatch.setattr(
        test_case_graph_v2,
        "build_test_case_service_tools",
        lambda service_config: ["service_tool"],
    )

    resolved_tools = asyncio.run(
        test_case_graph_v2._aresolve_required_tools(_settings())
    )

    assert resolved_tools == ["knowledge_tool", "service_tool"]
