from __future__ import annotations

import asyncio

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage
from support import BindableFakeChatModel, BindableFakeMessagesChatModel

from runtime_service.observability import langfuse
from runtime_service.runtime import RuntimeContext
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.services.deep_agent_demo import agent as deep_agent
from runtime_service.services.reference_agent import agent as reference_agent


class _CaptureCallback(BaseCallbackHandler):
    def __init__(self) -> None:
        self.events: list[str] = []
        self.metadata: list[dict[str, object]] = []

    def on_chain_start(self, *args: object, **kwargs: object) -> None:
        metadata = kwargs.get("metadata")
        if isinstance(metadata, dict):
            self.metadata.append(metadata)

    def on_chat_model_start(self, *args: object, **kwargs: object) -> None:
        self.events.append("model")

    def on_tool_start(self, *args: object, **kwargs: object) -> None:
        self.events.append("tool_start")

    def on_tool_end(self, *args: object, **kwargs: object) -> None:
        self.events.append("tool_end")


class _FailingExporterCallback(BaseCallbackHandler):
    def on_chat_model_start(self, *args: object, **kwargs: object) -> None:
        raise OSError("Langfuse endpoint unavailable")


class _FailingModel(BindableFakeChatModel):
    def _call(self, *args: object, **kwargs: object) -> str:
        raise ValueError("original model failure")


def _failing_exporter() -> BaseCallbackHandler:
    return langfuse._FailSoftCallback(_FailingExporterCallback())


def test_real_agent_propagates_model_and_tool_callbacks(monkeypatch) -> None:
    capture = _CaptureCallback()
    monkeypatch.setattr(langfuse, "_new_callback", lambda: capture)
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_reference",
                        "args": {"topic": "runtime"},
                        "id": "reference-call",
                    }
                ],
            ),
            AIMessage(content="done"),
        ]
    )
    config = {
        "metadata": {
            "run_id": "run-trace-1",
            "thread_id": "thread-trace-1",
            "request_id": "request-trace-1",
        },
        "configurable": {
            "_runtime_model": model,
            "thread_id": "thread-trace-1",
        },
    }

    graph = asyncio.run(reference_agent.get_agent(config))
    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "read runtime"}]},
            context=RuntimeContext(),
        )
    )

    assert result["messages"][-1].content == "done"
    assert capture.events.count("model") == 2
    assert capture.events == ["model", "tool_start", "tool_end", "model"]


def test_deep_agent_propagates_callbacks_into_subagent(monkeypatch) -> None:
    capture = _CaptureCallback()
    monkeypatch.setattr(langfuse, "_new_callback", lambda: capture)
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {
                            "description": "Summarize runtime",
                            "subagent_type": "summarizer",
                        },
                        "id": "task-call",
                    }
                ],
            ),
            AIMessage(content="subagent result"),
            AIMessage(content="parent result"),
        ]
    )
    graph = asyncio.run(
        deep_agent.get_agent(
            {
                "metadata": {"run_id": "run-subagent-1", "thread_id": "thread-subagent-1"},
                "configurable": {
                    "_runtime_test_model": model,
                    "_runtime_test_local_auth": True,
                },
            }
        )
    )

    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "delegate this"}]},
            context=RuntimeContext(),
        )
    )

    tool_messages = [
        message for message in result["messages"] if isinstance(message, ToolMessage)
    ]
    assert tool_messages
    assert tool_messages[-1].content == "subagent result"
    assert result["messages"][-1].content == "parent result"
    assert capture.events.count("model") >= 3
    assert "tool_start" in capture.events


def test_exporter_callback_failure_does_not_change_agent_result(monkeypatch) -> None:
    before = langfuse.get_observability_metrics().get("export_error", 0)
    monkeypatch.setattr(
        langfuse,
        "_new_callback",
        lambda: langfuse._FailSoftCallback(_FailingExporterCallback()),
    )
    graph = asyncio.run(
        reference_agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": BindableFakeMessagesChatModel(responses=[AIMessage(content="done")]),
                }
            }
        )
    )

    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]},
            context=RuntimeContext(),
        )
    )

    assert result["messages"][-1].content == "done"
    assert langfuse.get_observability_metrics().get("export_error", 0) > before


def test_exporter_failure_preserves_original_model_error(monkeypatch) -> None:
    monkeypatch.setattr(langfuse, "_new_callback", _failing_exporter)
    graph = asyncio.run(
        reference_agent.get_agent(
            {"configurable": {"_runtime_model": _FailingModel(responses=["unused"])}}
        )
    )

    with pytest.raises(ValueError, match="original model failure"):
        asyncio.run(
            graph.ainvoke(
                {"messages": [{"role": "user", "content": "hello"}]},
                context=RuntimeContext(),
            )
        )


def test_exporter_failure_preserves_timeout_and_cancel(monkeypatch) -> None:
    monkeypatch.setattr(langfuse, "_new_callback", _failing_exporter)

    async def invoke() -> None:
        graph = await reference_agent.get_agent(
            {
                "configurable": {
                    "_runtime_model": BindableFakeChatModel(
                        responses=["late"], sleep=0.2
                    )
                }
            }
        )
        await graph.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]},
            context=RuntimeContext(),
        )

    with pytest.raises(TimeoutError):
        asyncio.run(asyncio.wait_for(invoke(), timeout=0.01))

    async def cancel() -> None:
        task = asyncio.create_task(invoke())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())


def test_exporter_failure_preserves_workflow_interrupt(monkeypatch) -> None:
    from runtime_service.services.workflow_demo.agent import get_agent

    monkeypatch.setattr(langfuse, "_new_callback", _failing_exporter)
    graph = asyncio.run(get_agent({}))
    paused = graph.invoke(
        {"message": "hello", "requires_confirmation": True},
        {"configurable": {"thread_id": "r5-interrupt"}},
    )
    assert paused["__interrupt__"][0].value["kind"] == "workflow_confirmation"


def test_exporter_failure_preserves_tool_error_semantics(monkeypatch) -> None:
    monkeypatch.setattr(langfuse, "_new_callback", _failing_exporter)
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "read_reference", "args": {}, "id": "bad-tool"}],
            ),
            AIMessage(content="done"),
        ]
    )
    graph = asyncio.run(
        reference_agent.get_agent({"configurable": {"_runtime_model": model}})
    )
    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "read"}]},
            context=RuntimeContext(),
        )
    )
    tool_messages = [
        message for message in result["messages"] if isinstance(message, ToolMessage)
    ]
    assert tool_messages
    assert result["messages"][-1].content == "done"


def test_concurrent_real_graphs_keep_principal_and_run_metadata_isolated(monkeypatch) -> None:
    captures: list[_CaptureCallback] = []

    def new_callback() -> _CaptureCallback:
        callback = _CaptureCallback()
        captures.append(callback)
        return callback

    monkeypatch.setattr(langfuse, "_new_callback", new_callback)

    def config(index: int) -> dict[str, object]:
        return {
            "metadata": {
                "run_id": f"run-{index}",
                "thread_id": f"thread-{index}",
                "request_id": f"request-{index}",
            },
            "configurable": {
                "_runtime_model": BindableFakeMessagesChatModel(
                    responses=[AIMessage(content=f"done-{index}")]
                ),
                "langgraph_auth_user": {
                    "runtime_principal": {
                        "user_id": f"user-{index}",
                        "tenant_id": f"tenant-{index}",
                        "project_id": f"project-{index}",
                        "role": "developer",
                        "permissions": ["runtime.tool.read"],
                    },
                    "runtime_policy": {
                        "version": f"policy-{index}",
                        "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
                        "allowed_tool_names": ["read_reference"],
                    },
                    "runtime_scope": {
                        "tenant_id": f"tenant-{index}",
                        "project_id": f"project-{index}",
                    },
                    "runtime_context_hash": runtime_context_hash(None),
                },
            },
        }

    async def run(index: int) -> str:
        graph = await reference_agent.get_agent(config(index))
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]},
            context=RuntimeContext(),
        )
        return str(result["messages"][-1].content)

    async def run_all() -> list[str]:
        return list(await asyncio.gather(run(1), run(2)))

    assert asyncio.run(run_all()) == ["done-1", "done-2"]
    observed = {
        (
            str(metadata.get("run_id")),
            str(metadata.get("thread_id")),
            str(metadata.get("langfuse_user_id")),
        )
        for capture in captures
        for metadata in capture.metadata
        if metadata.get("langfuse_user_id")
    }
    assert observed == {
        ("run-1", "thread-1", "user-1"),
        ("run-2", "thread-2", "user-2"),
    }
