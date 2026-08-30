from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.agents.personal_assistant_agent import tools as pa_tools  # noqa: E402
from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.runtime.runtime_request_resolver import (  # noqa: E402
    ResolvedRuntimeSettings,
)

personal_assistant_graph_module = importlib.import_module(
    "runtime_service.agents.personal_assistant_agent.graph"
)


def _invoke_tool(tool_obj: Any, args: dict[str, Any]) -> Any:
    return getattr(tool_obj, "invoke")(args)


def test_calendar_tool_stub() -> None:
    result = _invoke_tool(
        pa_tools.create_calendar_event,
        {
            "title": "Design Review",
            "start_time": "2026-02-27T14:00:00",
            "end_time": "2026-02-27T15:00:00",
            "attendees": ["a@example.com", "b@example.com"],
            "location": "Room A",
        },
    )
    assert "Event created: Design Review" in result
    assert "with 2 attendees" in result


def test_email_tool_stub() -> None:
    result = _invoke_tool(
        pa_tools.send_email,
        {
            "to": ["team@example.com"],
            "subject": "Reminder",
            "body": "Please review",
            "cc": ["lead@example.com"],
        },
    )
    assert (
        result
        == "Email sent to team@example.com - Subject: Reminder (cc: lead@example.com)"
    )


def test_slots_tool_stub() -> None:
    result = _invoke_tool(
        pa_tools.get_available_time_slots,
        {
            "attendees": ["team@example.com"],
            "date": "2026-02-27",
            "duration_minutes": 60,
        },
    )
    assert result == ["09:00", "14:00", "16:00"]


def test_message_to_text_handles_rich_content() -> None:
    rich_message = type(
        "Msg", (), {"content": [{"text": "line1"}, {"text": "line2"}]}
    )()
    assert pa_tools._message_to_text(rich_message) == "line1\nline2"


def test_build_personal_assistant_agent_accepts_base_tools() -> None:
    captured: list[dict[str, Any]] = []

    def fake_create_agent(**kwargs: Any) -> dict[str, Any]:
        captured.append(kwargs)
        return {"name": kwargs.get("name"), "tools": kwargs.get("tools", [])}

    original = pa_tools.create_agent
    pa_tools.create_agent = fake_create_agent
    try:
        extra_tool = object()
        result = pa_tools.build_personal_assistant_agent(
            model=object(), base_tools=[extra_tool]
        )
    finally:
        pa_tools.create_agent = original

    assert len(captured) == 3
    supervisor_call = captured[-1]
    assert supervisor_call["name"] == "personal_assistant_supervisor"
    assert extra_tool in supervisor_call["tools"]
    assert len(result["tools"]) == 3


def test_langgraph_registers_personal_assistant_demo() -> None:
    langgraph_file = _PROJECT_ROOT / "runtime_service" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "personal_assistant_demo" in data["graphs"]


def test_personal_assistant_graph_exports_static_graph_symbol() -> None:
    assert hasattr(personal_assistant_graph_module, "graph")
    assert not hasattr(personal_assistant_graph_module, "make_graph")
    assert hasattr(personal_assistant_graph_module.graph, "invoke")


def test_personal_assistant_graph_public_tools_delegate_to_shared_registry(
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
        personal_assistant_graph_module,
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

    resolved_tools = personal_assistant_graph_module._resolve_public_tools(settings)

    assert resolved_tools == ["public_tool"]
    assert captured == {
        "enable_tools": True,
        "requested_tool_names": ["word_count"],
    }
