from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from runtime_service.middlewares import ModelCallTimeoutMiddleware, RuntimeConfigMiddleware
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeResolutionError,
    RuntimeAuthError,
    runtime_context_hash,
)
from langchain.agents.middleware import (
    ModelRequest,
    ToolCallRequest,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.messages import ToolMessage
from langchain.tools import tool


@tool
def read_tool(topic: str) -> str:
    """Read a topic."""

    return topic


@tool
def write_tool(topic: str) -> str:
    """Write a topic."""

    return topic


def _middleware(*, builder=None) -> RuntimeConfigMiddleware:
    principal = RuntimePrincipal("u", "t", "p", "developer", ("read_tool",))
    policy = RuntimePolicy("p1", ("test:model",), ("read_tool",))
    defaults = AgentDefaults(
        model_id="test:model",
        system_prompt="prompt",
        prompt_version="v1",
        temperature=0.5,
        optional_tool_names=("read_tool",),
    )
    return RuntimeConfigMiddleware(
        principal=principal,
        policy=policy,
        defaults=defaults,
        base_model=FakeListChatModel(responses=["ok"]),
        model_builder=builder or (lambda _: FakeListChatModel(responses=["override"])),
        local_fallback=True,
    )


def test_runtime_middleware_resolves_context_and_rebuilds_override_model() -> None:
    captured: list[object] = []
    middleware = _middleware(builder=lambda config: captured.append(config) or FakeListChatModel(responses=["ok"]))
    request = ModelRequest(
        model=FakeListChatModel(responses=["base"]),
        messages=[HumanMessage(content="hello")],
        runtime=Runtime(context=RuntimeContext(temperature=0)),
    )
    called: list[ModelRequest] = []

    async def handler(value: ModelRequest):
        called.append(value)
        return "response"

    result = asyncio.run(middleware.awrap_model_call(request, handler))

    assert result == "response"
    assert len(captured) == 1
    assert captured[0].temperature == 0.0  # type: ignore[union-attr]
    assert called[0].model is not request.model


def test_runtime_middleware_rejects_unknown_tool_before_handler() -> None:
    middleware = _middleware()
    request = ToolCallRequest(
        tool_call={"name": "write_tool", "args": {}, "id": "call-1", "type": "tool_call"},
        tool=None,
        state={},
        runtime=Runtime(context=RuntimeContext()),
    )
    called = False

    async def handler(_request):
        nonlocal called
        called = True
        return None

    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(middleware.awrap_tool_call(request, handler))

    assert error.value.code == "runtime.tool.not_allowed"
    assert called is False


def test_runtime_middleware_filters_unknown_tools_before_model_visibility() -> None:
    middleware = _middleware()
    request = ModelRequest(
        model=FakeListChatModel(responses=["ok"]),
        messages=[HumanMessage(content="hello")],
        tools=[read_tool, write_tool],
        runtime=Runtime(context=RuntimeContext()),
    )
    called: list[ModelRequest] = []

    async def handler(value: ModelRequest):
        called.append(value)
        return "response"

    asyncio.run(middleware.awrap_model_call(request, handler))
    assert [item.name for item in called[0].tools] == ["read_tool"]


def _server_runtime(*, context_hash: str | None = None) -> Runtime:
    user = {
        "runtime_principal": {
            "user_id": "server-user",
            "tenant_id": "server-tenant",
            "project_id": "server-project",
            "role": "developer",
            "permissions": ["read_tool"],
        },
        "runtime_policy": {
            "version": "server-policy",
            "allowed_model_ids": ["test:model"],
            "allowed_tool_names": ["read_tool"],
        },
        "runtime_scope": {"tenant_id": "server-tenant", "project_id": "server-project"},
        "runtime_context_hash": context_hash or runtime_context_hash(None),
    }
    return Runtime(
        context=RuntimeContext(),
        server_info=SimpleNamespace(user=user, assistant_id="assistant-a"),
        execution_info=SimpleNamespace(thread_id="thread-a"),
    )


def test_runtime_middleware_uses_verified_server_user_facts() -> None:
    middleware = RuntimeConfigMiddleware(
        principal=RuntimePrincipal("constructor-user", "t", "p", "developer", ()),
        policy=RuntimePolicy("constructor-policy", ("test:model",), ()),
        defaults=AgentDefaults("test:model", "prompt", "v1", optional_tool_names=("read_tool",)),
        base_model=FakeListChatModel(responses=["ok"]),
        local_fallback=False,
    )
    request = ModelRequest(
        model=FakeListChatModel(responses=["ok"]),
        messages=[HumanMessage(content="hello")],
        tools=[read_tool],
        runtime=_server_runtime(),
    )
    called: list[ModelRequest] = []

    async def handler(value: ModelRequest):
        called.append(value)
        return "response"

    asyncio.run(middleware.awrap_model_call(request, handler))
    assert [item.name for item in called[0].tools] == ["read_tool"]


def test_runtime_middleware_rejects_context_hash_mismatch() -> None:
    middleware = _middleware()
    request = ModelRequest(
        model=FakeListChatModel(responses=["ok"]),
        messages=[HumanMessage(content="hello")],
        runtime=_server_runtime(context_hash="sha256:" + "0" * 64),
    )

    async def handler(_request: ModelRequest):
        raise AssertionError("handler must not run")

    with pytest.raises(RuntimeAuthError) as error:
        asyncio.run(middleware.awrap_model_call(request, handler))
    assert error.value.code == "runtime.auth.context_hash_mismatch"


def test_model_call_timeout_propagates_timeout() -> None:
    middleware = ModelCallTimeoutMiddleware(timeout_seconds=0.01)

    async def handler(_request):
        await asyncio.sleep(0.1)
        return "never"

    with pytest.raises(TimeoutError):
        asyncio.run(middleware.awrap_model_call(object(), handler))


def test_model_call_timeout_does_not_swallow_cancellation() -> None:
    middleware = ModelCallTimeoutMiddleware(timeout_seconds=1)

    async def handler(_request):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(middleware.awrap_model_call(object(), handler))


def test_official_tool_error_only_handles_explicit_exception() -> None:
    request = ToolCallRequest(
        tool_call={"name": "read_tool", "args": {}, "id": "call-1", "type": "tool_call"},
        tool=None,
        state={},
        runtime=Runtime(context=RuntimeContext()),
    )
    middleware = ToolErrorMiddleware(
        on_error=lambda exc, _request: "recoverable" if isinstance(exc, ValueError) else None
    )

    async def handled(_request):
        raise ValueError("bad input")

    async def unhandled(_request):
        raise RuntimeError("bug")

    result = asyncio.run(middleware.awrap_tool_call(request, handled))
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert result.content == "recoverable"
    with pytest.raises(RuntimeError):
        asyncio.run(middleware.awrap_tool_call(request, unhandled))


def test_official_tool_retry_is_limited_to_named_tool_and_attempts() -> None:
    request = ToolCallRequest(
        tool_call={"name": "read_tool", "args": {}, "id": "call-1", "type": "tool_call"},
        tool=None,
        state={},
        runtime=Runtime(context=RuntimeContext()),
    )
    middleware = ToolRetryMiddleware(
        max_retries=1,
        tools=["read_tool"],
        retry_on=(ValueError,),
        on_failure="error",
        initial_delay=0,
        jitter=False,
    )
    attempts = 0

    async def handler(_request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError("temporary")
        return ToolMessage(content="ok", tool_call_id="call-1")

    result = asyncio.run(middleware.awrap_tool_call(request, handler))
    assert result.content == "ok"
    assert attempts == 2
