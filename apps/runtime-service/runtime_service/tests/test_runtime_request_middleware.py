from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, ToolCallRequest
from langchain.messages import AIMessage, SystemMessage, ToolMessage
from langchain.tools import ToolRuntime
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.tools import tool
from langgraph.runtime import Runtime

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware  # noqa: E402
from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.runtime.runtime_request_resolver import (  # noqa: E402
    AgentDefaults,
    resolve_runtime_request,
)


@tool("required_tool", description="Required tool for the graph.")
def required_tool() -> str:
    return "required"


@tool("optional_tool_a", description="Optional public tool A.")
def optional_tool_a() -> str:
    return "optional-a"


@tool("optional_tool_b", description="Optional public tool B.")
def optional_tool_b() -> str:
    return "optional-b"


@tool("dynamic_tool", description="Runtime-discovered tool.")
def dynamic_tool() -> str:
    return "dynamic-result"


@tool("dynamic_tool", description="Statically registered tool with the same name.")
def static_dynamic_tool() -> str:
    return "static-result"


class DummyModel:
    def __init__(self) -> None:
        self.bound_kwargs: dict[str, Any] = {}

    def bind(self, **kwargs: Any) -> DummyModel:
        self.bound_kwargs = dict(kwargs)
        return self


class NamedTool:
    def __init__(self, name: str) -> None:
        self.name = name


class ScriptedToolCallingModel(FakeMessagesListChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedToolCallingModel:
        del tools, kwargs
        return self


def _build_tool_runtime(
    context: RuntimeContext | None = None,
) -> ToolRuntime[RuntimeContext, dict[str, Any]]:
    return ToolRuntime(
        state={},
        context=context or RuntimeContext(),
        config={},
        stream_writer=lambda *_args, **_kwargs: None,
        tool_call_id="call-1",
        store=None,
    )


def _build_tool_call_request(
    *,
    tool: Any = None,
    context: RuntimeContext | None = None,
) -> ToolCallRequest:
    return ToolCallRequest(
        tool_call={
            "name": "dynamic_tool",
            "args": {},
            "id": "call-1",
            "type": "tool_call",
        },
        tool=tool,
        state={},
        runtime=_build_tool_runtime(context),
    )


def test_resolve_runtime_request_prefers_context_values(monkeypatch: Any) -> None:
    dummy_model = DummyModel()

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda model_id: dummy_model if model_id == "demo-model" else None,
    )

    resolved = resolve_runtime_request(
        context=RuntimeContext(
            model_id="demo-model",
            system_prompt="context prompt",
            temperature=0.7,
            max_tokens=256,
            top_p=0.8,
            enable_tools=True,
            tools=["optional_tool_b"],
        ),
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
            temperature=0.1,
            enable_tools=True,
            public_tool_names=("optional_tool_a",),
        ),
        required_tools=[required_tool],
        public_tools=[optional_tool_a, optional_tool_b],
    )

    assert resolved.system_prompt == "context prompt"
    assert resolved.tools == [required_tool, optional_tool_b]
    assert resolved.model is dummy_model
    assert dummy_model.bound_kwargs == {
        "temperature": 0.7,
        "max_tokens": 256,
        "top_p": 0.8,
    }


def test_resolve_runtime_request_rejects_unknown_public_tools(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: DummyModel(),
    )

    try:
        resolve_runtime_request(
            context=RuntimeContext(enable_tools=True, tools=["missing_tool"]),
            defaults=AgentDefaults(
                model_id="default-model",
                system_prompt="default prompt",
            ),
            required_tools=[required_tool],
            public_tools=[optional_tool_a],
        )
    except ValueError as exc:
        assert "Unsupported tools" in str(exc)
        assert "missing_tool" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown tool name.")


def test_runtime_request_middleware_wrap_model_call_updates_request(
    monkeypatch: Any,
) -> None:
    dummy_model = DummyModel()

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: dummy_model,
    )

    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
            public_tool_names=("optional_tool_a",),
        ),
        required_tools=[required_tool],
        public_tools=[optional_tool_a, optional_tool_b],
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        system_message=SystemMessage(content="base"),
        tools=[required_tool, optional_tool_a, optional_tool_b],
        runtime=Runtime(
            context=RuntimeContext(
                model_id="demo-model",
                system_prompt="context prompt",
                enable_tools=True,
                tools=["optional_tool_b"],
            )
        ),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.model is dummy_model
        assert updated_request.system_prompt == "context prompt"
        assert updated_request.tools == [required_tool, optional_tool_b]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_runtime_request_middleware_awrap_model_call_updates_request(
    monkeypatch: Any,
) -> None:
    dummy_model = DummyModel()

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: dummy_model,
    )

    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
            public_tool_names=("optional_tool_a",),
        ),
        required_tools=[required_tool],
        public_tools=[optional_tool_a, optional_tool_b],
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        system_message=SystemMessage(content="base"),
        tools=[required_tool, optional_tool_a, optional_tool_b],
        runtime=Runtime(
            context=RuntimeContext(
                model_id="demo-model",
                enable_tools=False,
            )
        ),
    )

    async def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.model is dummy_model
        assert updated_request.system_prompt == "default prompt"
        assert updated_request.tools == [required_tool]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = asyncio.run(middleware.awrap_model_call(request, handler))

    assert response.result[0].text == "ok"


def test_runtime_request_middleware_preserves_registered_deepagent_tools(
    monkeypatch: Any,
) -> None:
    dummy_model = DummyModel()
    read_file = NamedTool("read_file")
    write_todos = NamedTool("write_todos")

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: dummy_model,
    )

    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
        ),
        required_tools=[],
        public_tools=[],
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[read_file, write_todos],
        runtime=Runtime(context=RuntimeContext(enable_tools=False)),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.tools == [read_file, write_todos]
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(request, handler)


def test_runtime_request_middleware_hides_optional_tools_for_empty_allowlist(
    monkeypatch: Any,
) -> None:
    dummy_model = DummyModel()

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: dummy_model,
    )

    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
            public_tool_names=("optional_tool_a",),
        ),
        required_tools=[required_tool],
        public_tools=[optional_tool_a, optional_tool_b],
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[required_tool, optional_tool_a, optional_tool_b],
        runtime=Runtime(context=RuntimeContext(enable_tools=True, tools=[])),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.tools == [required_tool]
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(request, handler)


def test_runtime_request_middleware_wrap_model_call_supports_custom_resolvers(
    monkeypatch: Any,
) -> None:
    dummy_model = DummyModel()
    resolved_required = NamedTool("resolved_required")

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: dummy_model,
    )

    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
            enable_tools=True,
        ),
        required_tools=[],
        public_tools=[],
        required_tool_resolver=lambda settings: [required_tool, resolved_required],
        public_tool_resolver=lambda settings: [optional_tool_b]
        if settings.enable_tools
        else [],
        system_prompt_resolver=lambda settings: f"wrapped:{settings.system_prompt}",
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[required_tool, resolved_required, optional_tool_b],
        runtime=Runtime(
            context=RuntimeContext(
                model_id="demo-model",
                system_prompt="context prompt",
                enable_tools=True,
            )
        ),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.model is dummy_model
        assert updated_request.system_prompt == "wrapped:context prompt"
        assert updated_request.tools == [required_tool, resolved_required, optional_tool_b]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_runtime_request_middleware_awrap_model_call_supports_async_resolvers(
    monkeypatch: Any,
) -> None:
    dummy_model = DummyModel()
    resolved_required = NamedTool("resolved_required_async")

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: dummy_model,
    )

    async def resolve_required(settings: Any) -> list[Any]:
        del settings
        return [required_tool, resolved_required]

    async def resolve_public(settings: Any) -> list[Any]:
        return [optional_tool_a] if settings.enable_tools else []

    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
            enable_tools=True,
        ),
        required_tools=[],
        public_tools=[],
        arequired_tool_resolver=resolve_required,
        apublic_tool_resolver=resolve_public,
        system_prompt_resolver=lambda settings: f"async:{settings.system_prompt}",
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[required_tool, resolved_required, optional_tool_a],
        runtime=Runtime(
            context=RuntimeContext(
                model_id="demo-model",
                system_prompt="context prompt",
                enable_tools=True,
            )
        ),
    )

    async def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.model is dummy_model
        assert updated_request.system_prompt == "async:context prompt"
        assert updated_request.tools == [required_tool, resolved_required, optional_tool_a]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = asyncio.run(middleware.awrap_model_call(request, handler))

    assert response.result[0].text == "ok"


def test_runtime_request_middleware_exposes_authorized_dynamic_tools(
    monkeypatch: Any,
) -> None:
    dummy_model = DummyModel()
    registered_tool = NamedTool("registered_tool")

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: dummy_model,
    )

    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
        ),
        required_tools=[],
        public_tools=[],
        required_tool_resolver=lambda _settings: [dynamic_tool],
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[registered_tool],
        runtime=Runtime(context=RuntimeContext()),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.tools == [registered_tool, dynamic_tool]
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(request, handler)


def test_runtime_request_middleware_keeps_static_tool_on_name_conflict(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: DummyModel(),
    )
    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(model_id="default-model", system_prompt=""),
        required_tools=[],
        public_tools=[],
        required_tool_resolver=lambda _settings: [dynamic_tool],
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[static_dynamic_tool],
        runtime=Runtime(context=RuntimeContext()),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.tools == [static_dynamic_tool]
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(request, handler)


def test_runtime_request_middleware_dynamic_public_tools_follow_allowlist(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: DummyModel(),
    )
    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(model_id="default-model", system_prompt=""),
        required_tools=[],
        public_tools=[],
        public_tool_resolver=lambda settings: [dynamic_tool]
        if "dynamic_tool" in settings.requested_public_tool_names
        else [],
    )

    def resolve_tools(context: RuntimeContext) -> list[Any]:
        request = ModelRequest(
            model=object(),
            messages=[],
            tools=[],
            runtime=Runtime(context=context),
        )
        observed: list[Any] = []
        middleware.wrap_model_call(
            request,
            lambda updated: observed.extend(updated.tools)
            or ModelResponse(result=[AIMessage(content="ok")]),
        )
        return observed

    assert resolve_tools(RuntimeContext(enable_tools=True, tools=[])) == []
    assert resolve_tools(
        RuntimeContext(enable_tools=True, tools=["dynamic_tool"])
    ) == [dynamic_tool]


def test_runtime_request_middleware_wrap_tool_call_binds_dynamic_tool(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: DummyModel(),
    )
    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(model_id="default-model", system_prompt=""),
        required_tools=[],
        public_tools=[],
        required_tool_resolver=lambda _settings: [dynamic_tool],
    )

    def handler(request: ToolCallRequest) -> str:
        assert request.tool is dynamic_tool
        return "ok"

    assert middleware.wrap_tool_call(_build_tool_call_request(), handler) == "ok"


def test_runtime_request_middleware_wrap_tool_call_fails_closed(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: DummyModel(),
    )
    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(model_id="default-model", system_prompt=""),
        required_tools=[],
        public_tools=[],
        required_tool_resolver=lambda _settings: [],
        public_tool_resolver=lambda settings: [dynamic_tool]
        if "dynamic_tool" in settings.requested_public_tool_names
        else [],
    )
    observed: list[Any] = []

    middleware.wrap_tool_call(
        _build_tool_call_request(
            context=RuntimeContext(enable_tools=True, tools=[]),
        ),
        lambda request: observed.append(request.tool) or "unknown",
    )

    assert observed == [None]


def test_runtime_request_middleware_wrap_tool_call_preserves_static_tool() -> None:
    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(model_id="default-model", system_prompt=""),
        required_tools=[],
        public_tools=[],
        required_tool_resolver=lambda _settings: (_ for _ in ()).throw(
            AssertionError("Static tools must not be re-resolved.")
        ),
    )

    def handler(request: ToolCallRequest) -> str:
        assert request.tool is static_dynamic_tool
        return "static"

    assert (
        middleware.wrap_tool_call(
            _build_tool_call_request(tool=static_dynamic_tool),
            handler,
        )
        == "static"
    )


def test_runtime_request_middleware_awrap_tool_call_binds_dynamic_tool(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: DummyModel(),
    )

    async def resolve_required(_settings: Any) -> list[Any]:
        return [dynamic_tool]

    middleware = RuntimeRequestMiddleware(
        defaults=AgentDefaults(model_id="default-model", system_prompt=""),
        required_tools=[],
        public_tools=[],
        arequired_tool_resolver=resolve_required,
    )

    async def handler(request: ToolCallRequest) -> str:
        assert request.tool is dynamic_tool
        return "ok"

    assert (
        asyncio.run(middleware.awrap_tool_call(_build_tool_call_request(), handler))
        == "ok"
    )


def test_runtime_request_middleware_executes_dynamic_tool_in_agent_chain(
    monkeypatch: Any,
) -> None:
    model = ScriptedToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "dynamic_tool",
                        "args": {},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="done"),
        ]
    )
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: model,
    )
    agent = create_agent(
        model=model,
        tools=[required_tool],
        middleware=[
            RuntimeRequestMiddleware(
                defaults=AgentDefaults(model_id="default-model", system_prompt=""),
                required_tools=[],
                public_tools=[],
                required_tool_resolver=lambda _settings: [dynamic_tool],
            )
        ],
        context_schema=RuntimeContext,
    )

    result = agent.invoke(
        {"messages": [{"role": "user", "content": "run the dynamic tool"}]},
        context=RuntimeContext(),
    )

    tool_messages = [
        message for message in result["messages"] if isinstance(message, ToolMessage)
    ]
    assert len(tool_messages) == 1
    assert tool_messages[0].content == "dynamic-result"
