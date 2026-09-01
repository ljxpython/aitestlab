from __future__ import annotations

import asyncio
from typing import ClassVar

from langchain.agents import create_agent as real_create_agent
from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from runtime_service.services.reference_agent import agent
from runtime_service.runtime.resolver import runtime_context_hash
from support import BindableFakeChatModel


def _auth_user() -> dict[str, object]:
    return {
        "runtime_principal": {
            "user_id": "local-user",
            "tenant_id": "local-tenant",
            "project_id": "reference-project",
            "role": "developer",
            "permissions": ["runtime.tool.read"],
        },
        "runtime_policy": {
            "version": "reference-agent-local-v1",
            "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
            "allowed_tool_names": ["read_reference"],
        },
        "runtime_scope": {"tenant_id": "local-tenant", "project_id": "reference-project"},
        "runtime_context_hash": runtime_context_hash(None),
    }


def test_reference_agent_declares_reliability_middleware_in_order(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        agent,
        "build_model",
        lambda _config: FakeListChatModel(responses=["ok"]),
    )

    def capture_create_agent(**kwargs):
        captured.update(kwargs)
        return real_create_agent(**kwargs)

    monkeypatch.setattr(agent, "create_agent", capture_create_agent)
    asyncio.run(
        agent.get_agent(
            {
                "context": {},
                "configurable": {
                    "langgraph_auth_user": _auth_user(),
                    "_runtime_test_local_auth": True,
                },
            }
        )
    )

    middleware = captured["middleware"]
    assert [type(item).__name__ for item in middleware] == [
        "RuntimeConfigMiddleware",
        "ModelCallLimitMiddleware",
        "ToolCallLimitMiddleware",
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ModelCallTimeoutMiddleware",
    ]


def test_reference_agent_explicitly_composes_model_reliability_adapters(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(agent, "build_model", lambda _config: FakeListChatModel(responses=["ok"]))

    def capture_create_agent(**kwargs):
        captured.update(kwargs)
        return real_create_agent(**kwargs)

    monkeypatch.setattr(agent, "create_agent", capture_create_agent)
    asyncio.run(
        agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": BindableFakeChatModel(responses=["ok"]),
                    "_runtime_fallback_model": BindableFakeChatModel(responses=["fallback"]),
                    "_runtime_model_retry": True,
                }
            }
        )
    )

    middleware = captured["middleware"]
    assert [type(item).__name__ for item in middleware][-5:] == [
        "ToolErrorMiddleware",
        "ToolRetryMiddleware",
        "ModelFallbackMiddleware",
        "ModelRetryMiddleware",
        "ModelCallTimeoutMiddleware",
    ]


class _BindableMessagesListChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class _RetryOnceModel(_BindableMessagesListChatModel):
    attempts: ClassVar[int] = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        type(self).attempts += 1
        if type(self).attempts == 1:
            raise ConnectionError("temporary model outage")
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


class _AlwaysFailModel(_BindableMessagesListChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise ConnectionError("primary model outage")


def _tool_call_response(name: str = "read_reference") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": {"topic": "runtime"}, "id": "call-1", "type": "tool_call"}
        ],
    )


def test_reference_agent_graph_retries_idempotent_tool(monkeypatch) -> None:
    calls = 0

    from langchain.tools import tool

    @tool("read_reference")
    def flaky_read(topic: str) -> str:
        """Read a reference note with one transient failure."""
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("temporary tool outage")
        return f"reference note: {topic}"

    monkeypatch.setattr(agent, "read_reference", flaky_read)
    graph = asyncio.run(
        agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": _BindableMessagesListChatModel(
                        responses=[_tool_call_response(), AIMessage(content="done")]
                    )
                }
            }
        )
    )

    result = asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "read runtime"}]}))

    assert calls == 2
    assert result["messages"][-1].content == "done"


def test_reference_agent_graph_surfaces_recoverable_tool_error_to_model(monkeypatch) -> None:
    from langchain.tools import tool

    @tool("read_reference")
    def invalid_read(topic: str) -> str:
        """Read a reference note with an invalid request."""
        raise ValueError("secret internal detail")

    monkeypatch.setattr(agent, "read_reference", invalid_read)
    graph = asyncio.run(
        agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": _BindableMessagesListChatModel(
                        responses=[_tool_call_response(), AIMessage(content="recovered")]
                    )
                }
            }
        )
    )

    result = asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "read runtime"}]}))

    tool_message = result["messages"][-2]
    assert tool_message.status == "error"
    assert "ValueError" in tool_message.content
    assert "secret internal detail" not in tool_message.content
    assert result["messages"][-1].content == "recovered"


def test_reference_agent_graph_surfaces_tool_error_after_retry_budget(monkeypatch) -> None:
    calls = 0
    from langchain.tools import tool

    @tool("read_reference")
    def unavailable_read(topic: str) -> str:
        """Read a reference note from an unavailable source."""
        nonlocal calls
        calls += 1
        raise ConnectionError("provider detail must stay hidden")

    monkeypatch.setattr(agent, "read_reference", unavailable_read)
    graph = asyncio.run(
        agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": _BindableMessagesListChatModel(
                        responses=[_tool_call_response(), AIMessage(content="recovered")]
                    )
                }
            }
        )
    )

    result = asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "read runtime"}]}))

    tool_message = result["messages"][-2]
    assert calls == 2
    assert tool_message.status == "error"
    assert "ConnectionError" in tool_message.content
    assert "provider detail must stay hidden" not in tool_message.content


def test_reference_agent_graph_does_not_swallow_unknown_tool_error(monkeypatch) -> None:
    from langchain.tools import tool

    @tool("read_reference")
    def broken_read(topic: str) -> str:
        """Read a reference note with an unexpected defect."""
        raise RuntimeError("program defect")

    monkeypatch.setattr(agent, "read_reference", broken_read)
    graph = asyncio.run(
        agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": _BindableMessagesListChatModel(
                        responses=[_tool_call_response()]
                    )
                }
            }
        )
    )

    try:
        asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "read runtime"}]}))
    except RuntimeError as error:
        assert str(error) == "program defect"
    else:
        raise AssertionError("unknown tool errors must propagate")


def test_reference_agent_graph_uses_explicit_model_fallback() -> None:
    fallback = BindableFakeChatModel(responses=["fallback result"])
    graph = asyncio.run(
        agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": _AlwaysFailModel(responses=[]),
                    "_runtime_fallback_model": fallback,
                }
            }
        )
    )

    result = asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "hello"}]}))

    assert result["messages"][-1].content == "fallback result"


def test_reference_agent_graph_retries_model_when_explicitly_enabled() -> None:
    _RetryOnceModel.attempts = 0
    graph = asyncio.run(
        agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": _RetryOnceModel(responses=[AIMessage(content="retry result")]),
                    "_runtime_model_retry": True,
                }
            }
        )
    )

    result = asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "hello"}]}))

    assert _RetryOnceModel.attempts == 2
    assert result["messages"][-1].content == "retry result"


def test_reference_agent_graph_propagates_model_retry_exhaustion() -> None:
    graph = asyncio.run(
        agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": _AlwaysFailModel(responses=[]),
                    "_runtime_model_retry": True,
                }
            }
        )
    )

    try:
        asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "hello"}]}))
    except ConnectionError as error:
        assert str(error) == "primary model outage"
    else:
        raise AssertionError("model retry exhaustion must propagate")
