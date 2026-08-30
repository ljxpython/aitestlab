from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from langgraph.prebuilt.tool_node import ToolCallRequest

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.services.test_case_service_v2.tool_argument_alias_middleware import (  # noqa: E402
    ToolArgumentAliasMiddleware,
)


def test_read_file_path_alias_maps_to_file_path() -> None:
    middleware = ToolArgumentAliasMiddleware()
    observed_requests: list[ToolCallRequest] = []
    request = ToolCallRequest(
        tool_call={
            "name": "read_file",
            "args": {"path": "/skills/requirement-analysis/SKILL.md"},
            "id": "call-1",
            "type": "tool_call",
        },
        tool=None,
        state={},
        runtime=None,
    )

    def handler(next_request: ToolCallRequest) -> str:
        observed_requests.append(next_request)
        return "ok"

    result = middleware.wrap_tool_call(request, handler)

    assert result == "ok"
    assert observed_requests[0].tool_call["args"]["file_path"] == "/skills/requirement-analysis/SKILL.md"


def test_non_read_file_tool_call_is_unchanged() -> None:
    middleware = ToolArgumentAliasMiddleware()
    observed_requests: list[ToolCallRequest] = []
    request = ToolCallRequest(
        tool_call={
            "name": "query_project_knowledge",
            "args": {"project_id": "p1", "query": "q"},
            "id": "call-2",
            "type": "tool_call",
        },
        tool=None,
        state={},
        runtime=None,
    )

    def handler(next_request: ToolCallRequest) -> str:
        observed_requests.append(next_request)
        return "ok"

    result = middleware.wrap_tool_call(request, handler)

    assert result == "ok"
    assert observed_requests[0].tool_call["args"] == {"project_id": "p1", "query": "q"}
