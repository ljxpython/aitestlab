from __future__ import annotations

import importlib
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.tools.registry import (  # noqa: E402
    get_tool_catalog,
    resolve_requested_tools,
)

assistant_graph_module = importlib.import_module("runtime_service.agents.assistant_agent.graph")


def test_tool_registry_contains_public_capabilities() -> None:
    catalog = get_tool_catalog()
    assert "word_count" in catalog
    assert "utc_now" in catalog
    assert "to_upper" in catalog


def test_empty_tool_request_does_not_select_builtin_or_mcp_tools() -> None:
    assert resolve_requested_tools(None) == ([], [])
    assert resolve_requested_tools([]) == ([], [])


def test_assistant_public_optional_tools_are_declared_in_registry() -> None:
    catalog = get_tool_catalog()
    for tool_name in assistant_graph_module.ASSISTANT_DEFAULTS.public_tool_names:
        assert tool_name in catalog


def test_custom_tools_route_uses_registry_source_of_truth() -> None:
    route_file = (
        Path(__file__).resolve().parents[2]
        / "custom_routes"
        / "tools.py"
    )
    source = route_file.read_text(encoding="utf-8")
    assert "get_tool_catalog" in source


def test_tool_registry_does_not_expose_legacy_appruntimeconfig_entrypoint() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "registry.py"
    ).read_text(encoding="utf-8")
    assert "AppRuntimeConfig" not in source
    assert "def build_tools(" not in source
