from __future__ import annotations

from collections.abc import Mapping
import sys
from pathlib import Path
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolCallRequest
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.services.test_case_service.tool_runtime_context_middleware import (  # noqa: E402
    ToolRuntimeContextSanitizerMiddleware,
)


@tool("no_context_tool", description="Tool that does not accept runtime context.")
def _no_context_tool(
    value: str,
    runtime: ToolRuntime[None, dict[str, Any]],
) -> str:
    return value


@tool("context_tool", description="Tool that accepts runtime context.")
def _context_tool(
    value: str,
    runtime: ToolRuntime[RuntimeContext | Mapping[str, Any] | None, dict[str, Any]],
) -> str:
    return value


def _build_runtime() -> ToolRuntime[Any, dict[str, Any]]:
    return ToolRuntime(
        state={},
        context=RuntimeContext(project_id="project-1"),
        config={},
        stream_writer=lambda *_args, **_kwargs: None,
        tool_call_id="tool-call-1",
        store=None,
    )


def test_sanitizer_strips_context_for_no_context_tool() -> None:
    middleware = ToolRuntimeContextSanitizerMiddleware()
    observed_contexts: list[Any] = []

    request = ToolCallRequest(
        tool_call={
            "name": "no_context_tool",
            "args": {"value": "ok"},
            "id": "call-1",
            "type": "tool_call",
        },
        tool=_no_context_tool,
        state={},
        runtime=_build_runtime(),
    )

    def handler(next_request: Any) -> str:
        observed_contexts.append(next_request.runtime.context)
        return "ok"

    result = middleware.wrap_tool_call(request, handler)

    assert result == "ok"
    assert observed_contexts == [None]


def test_sanitizer_keeps_context_for_context_aware_tool() -> None:
    middleware = ToolRuntimeContextSanitizerMiddleware()
    observed_contexts: list[Any] = []

    request = ToolCallRequest(
        tool_call={
            "name": "context_tool",
            "args": {"value": "ok"},
            "id": "call-2",
            "type": "tool_call",
        },
        tool=_context_tool,
        state={},
        runtime=_build_runtime(),
    )

    def handler(next_request: Any) -> str:
        observed_contexts.append(next_request.runtime.context)
        return "ok"

    result = middleware.wrap_tool_call(request, handler)

    assert result == "ok"
    assert len(observed_contexts) == 1
    assert isinstance(observed_contexts[0], RuntimeContext)
    assert observed_contexts[0].project_id == "project-1"
