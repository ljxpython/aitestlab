from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, ToolCallRequest
from langchain.messages import AIMessage, SystemMessage, ToolMessage
from langchain.tools import ToolRuntime
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.tools import tool
from langgraph.runtime import Runtime
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware  # noqa: E402
from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.runtime.runtime_request_resolver import (  # noqa: E402
    AgentDefaults,
    resolve_runtime_request,
    resolve_trusted_runtime_context,
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


_TRUSTED_CONTEXT = RuntimeContext(
    user_id="user-1",
    tenant_id="tenant-1",
    role="project_editor",
    permissions=["runtime:write"],
    project_id="project-1",
)
_TRUSTED_USER = {
    "identity": _TRUSTED_CONTEXT.user_id,
    "tenant_id": _TRUSTED_CONTEXT.tenant_id,
    "role": _TRUSTED_CONTEXT.role,
    "permissions": _TRUSTED_CONTEXT.permissions,
    "project_id": _TRUSTED_CONTEXT.project_id,
}
_CURRENT_RUNTIME_OPTIONS: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _CURRENT_RUNTIME_OPTIONS.clear()
    monkeypatch.setattr(
        "runtime_service.middlewares.runtime_request.get_config",
        lambda: {
            "configurable": {
                "platform_runtime": dict(_CURRENT_RUNTIME_OPTIONS),
            }
        },
    )


def _set_runtime_options(**options: Any) -> None:
    _CURRENT_RUNTIME_OPTIONS.clear()
    _CURRENT_RUNTIME_OPTIONS.update(options)


def _config(**options: Any) -> dict[str, Any]:
    return {"configurable": {"platform_runtime": options}}


def _build_runtime(
    context: RuntimeContext | None = None,
) -> Runtime[RuntimeContext]:
    return Runtime(
        context=context or RuntimeContext(),
        server_info=SimpleNamespace(user=_TRUSTED_USER),
    )


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
        server_info=SimpleNamespace(user=_TRUSTED_USER),
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


def test_resolve_runtime_request_prefers_platform_runtime_values(monkeypatch: Any) -> None:
    dummy_model = DummyModel()

    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda model_id: dummy_model if model_id == "demo-model" else None,
    )

    resolved = resolve_runtime_request(
        runtime=_build_runtime(),
        config=_config(
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
            runtime=_build_runtime(),
            config=_config(enable_tools=True, tools=["missing_tool"]),
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


def test_resolver_rejects_legacy_context_without_agent_server_user() -> None:
    runtime = Runtime(context=_TRUSTED_CONTEXT)

    with pytest.raises(ValueError, match="Agent Server runtime user"):
        resolve_trusted_runtime_context(runtime)


def test_resolver_allows_explicit_internal_trusted_context() -> None:
    runtime = Runtime(context=_TRUSTED_CONTEXT)

    assert resolve_trusted_runtime_context(
        runtime,
        allow_internal_context=True,
    ) == _TRUSTED_CONTEXT


def test_resolver_allows_explicit_local_debug_config(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: DummyModel(),
    )

    resolved = resolve_runtime_request(
        runtime=Runtime(context=_TRUSTED_CONTEXT),
        config={
            "configurable": {
                "platform_local_debug": True,
                "platform_runtime": {"model_id": "debug-model"},
            }
        },
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
        ),
        required_tools=[],
        public_tools=[],
    )

    assert resolved.context == _TRUSTED_CONTEXT
    assert resolved.options.model_id == "debug-model"


def test_authenticated_user_wins_over_local_debug_context(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_model_by_id",
        lambda _model_id: DummyModel(),
    )
    conflicting_context = RuntimeContext(
        user_id="attacker",
        tenant_id="attacker",
        role="admin",
        permissions=["*"],
        project_id="attacker-project",
    )

    resolved = resolve_runtime_request(
        runtime=_build_runtime(conflicting_context),
        config={
            "configurable": {
                "platform_local_debug": True,
                "platform_runtime": {},
            }
        },
        defaults=AgentDefaults(
            model_id="default-model",
            system_prompt="default prompt",
        ),
        required_tools=[],
        public_tools=[],
    )

    assert resolved.context == _TRUSTED_CONTEXT


def test_resolver_rejects_identity_fields_in_platform_runtime() -> None:
    with pytest.raises(ValueError, match="trusted identity fields: project_id"):
        resolve_runtime_request(
            runtime=_build_runtime(),
            config=_config(project_id="client-project"),
            defaults=AgentDefaults(
                model_id="default-model",
                system_prompt="default prompt",
            ),
            required_tools=[],
            public_tools=[],
        )


def test_resolver_rejects_unconfigured_model() -> None:
    with pytest.raises(ValueError, match="config is incomplete"):
        resolve_runtime_request(
            runtime=_build_runtime(),
            config=_config(model_id="definitely-not-configured"),
            defaults=AgentDefaults(
                model_id="default-model",
                system_prompt="default prompt",
            ),
            required_tools=[],
            public_tools=[],
        )


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
    _set_runtime_options(
        model_id="demo-model",
        system_prompt="context prompt",
        enable_tools=True,
        tools=["optional_tool_b"],
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        system_message=SystemMessage(content="base"),
        tools=[required_tool, optional_tool_a, optional_tool_b],
        runtime=_build_runtime(),
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
    _set_runtime_options(model_id="demo-model", enable_tools=False)
    request = ModelRequest(
        model=object(),
        messages=[],
        system_message=SystemMessage(content="base"),
        tools=[required_tool, optional_tool_a, optional_tool_b],
        runtime=_build_runtime(),
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
        runtime=_build_runtime(),
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
    _set_runtime_options(enable_tools=True, tools=[])
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[required_tool, optional_tool_a, optional_tool_b],
        runtime=_build_runtime(),
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
    _set_runtime_options(
        model_id="demo-model",
        system_prompt="context prompt",
        enable_tools=True,
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[required_tool, resolved_required, optional_tool_b],
        runtime=_build_runtime(),
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
    _set_runtime_options(
        model_id="demo-model",
        system_prompt="context prompt",
        enable_tools=True,
    )
    request = ModelRequest(
        model=object(),
        messages=[],
        tools=[required_tool, resolved_required, optional_tool_a],
        runtime=_build_runtime(),
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
        runtime=_build_runtime(),
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
        runtime=_build_runtime(),
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

    def resolve_tools(options: dict[str, Any]) -> list[Any]:
        _set_runtime_options(**options)
        request = ModelRequest(
            model=object(),
            messages=[],
            tools=[],
            runtime=_build_runtime(),
        )
        observed: list[Any] = []
        middleware.wrap_model_call(
            request,
            lambda updated: observed.extend(updated.tools)
            or ModelResponse(result=[AIMessage(content="ok")]),
        )
        return observed

    assert resolve_tools({"enable_tools": True, "tools": []}) == []
    assert resolve_tools(
        {"enable_tools": True, "tools": ["dynamic_tool"]}
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
        _build_tool_call_request(),
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
    monkeypatch.setattr(
        "runtime_service.runtime.runtime_request_resolver.resolve_trusted_runtime_context",
        lambda _runtime, **_kwargs: _TRUSTED_CONTEXT,
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
        config=_config(),
    )

    tool_messages = [
        message for message in result["messages"] if isinstance(message, ToolMessage)
    ]
    assert len(tool_messages) == 1
    assert tool_messages[0].content == "dynamic-result"
