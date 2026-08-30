from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any, cast

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.agents.customer_support_agent import tools as cs_tools  # noqa: E402
from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.runtime.runtime_request_resolver import (  # noqa: E402
    ResolvedRuntimeSettings,
)

customer_support_graph_module = importlib.import_module(
    "runtime_service.agents.customer_support_agent.graph"
)


def _invoke_tool(tool_obj: Any, args: dict[str, Any]) -> Any:
    return getattr(tool_obj, "invoke")(args)


def test_customer_support_step_config_shape() -> None:
    assert set(cs_tools.STEP_CONFIG.keys()) == {
        "warranty_collector",
        "issue_classifier",
        "resolution_specialist",
    }
    assert cs_tools.STEP_CONFIG["issue_classifier"]["requires"] == ["warranty_status"]
    assert cs_tools.STEP_CONFIG["resolution_specialist"]["requires"] == [
        "warranty_status",
        "issue_type",
    ]


def test_customer_support_resolution_tools_stub() -> None:
    solution = _invoke_tool(
        cs_tools.provide_solution, {"solution": "Restart and update firmware"}
    )
    escalation = _invoke_tool(
        cs_tools.escalate_to_human, {"reason": "Hardware damage out of warranty"}
    )
    assert solution == "Solution provided: Restart and update firmware"
    assert (
        escalation
        == "Escalating to human support. Reason: Hardware damage out of warranty"
    )


def test_step_middleware_wrap_model_call_applies_prompt_and_tools() -> None:
    middleware = cs_tools.StepMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        system_message=SystemMessage(content="base"),
        state=cast(
            cs_tools.SupportState,
            {"current_step": "issue_classifier", "warranty_status": "in_warranty"},
        ),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.system_prompt == (
            "base\n\n"
            + cs_tools.ISSUE_CLASSIFIER_PROMPT.format(warranty_status="in_warranty")
        )
        assert updated_request.tools == [cs_tools.record_issue_type]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_step_middleware_awrap_model_call_applies_prompt_and_tools() -> None:
    middleware = cs_tools.StepMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        system_message=SystemMessage(content="base"),
        state=cast(
            cs_tools.SupportState,
            {
                "current_step": "resolution_specialist",
                "warranty_status": "in_warranty",
                "issue_type": "software",
            },
        ),
    )

    async def handler(updated_request: ModelRequest) -> ModelResponse:
        assert (
            updated_request.system_prompt
            == "base\n\n"
            + cs_tools.RESOLUTION_SPECIALIST_PROMPT.format(
                warranty_status="in_warranty",
                issue_type="software",
            )
        )
        assert updated_request.tools == [
            cs_tools.provide_solution,
            cs_tools.escalate_to_human,
        ]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = asyncio.run(middleware.awrap_model_call(request, handler))

    assert response.result[0].text == "ok"


def test_build_customer_support_agent_runnable() -> None:
    class DummyModel:
        def bind(self, **kwargs: Any) -> Any:
            del kwargs
            return self

    agent = cs_tools.build_customer_support_agent(DummyModel())
    assert hasattr(agent, "invoke")


def test_langgraph_registers_customer_support_handoffs_demo() -> None:
    langgraph_file = _PROJECT_ROOT / "runtime_service" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "customer_support_handoffs_demo" in data["graphs"]


def test_customer_support_graph_exports_static_graph_symbol() -> None:
    assert hasattr(customer_support_graph_module, "graph")
    assert not hasattr(customer_support_graph_module, "make_graph")
    assert hasattr(customer_support_graph_module.graph, "invoke")


def test_customer_support_graph_public_tools_delegate_to_shared_registry(
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
        customer_support_graph_module,
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

    resolved_tools = customer_support_graph_module._resolve_public_tools(settings)

    assert resolved_tools == ["public_tool"]
    assert captured == {
        "enable_tools": True,
        "requested_tool_names": ["word_count"],
    }
