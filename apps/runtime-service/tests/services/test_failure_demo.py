from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage

from runtime_service.graphs.failure_demo import (
    get_agent,
    get_disconnect_agent,
    get_recovery_agent,
    get_timeout_agent,
)
from runtime_service.runtime import RuntimeAuthError
from runtime_service.runtime.resolver import runtime_context_hash


def test_failure_demo_requires_verified_principal() -> None:
    with pytest.raises(RuntimeAuthError, match="runtime.auth.missing_principal"):
        asyncio.run(get_agent({}))


def _config(model_id: str, tool_name: str) -> dict[str, object]:
    return {
        "configurable": {
            "langgraph_auth_user": {
                "runtime_principal": {
                    "user_id": "user",
                    "tenant_id": "tenant",
                    "project_id": "project",
                    "role": "developer",
                    "permissions": ["runtime.tool.write"],
                },
                "runtime_policy": {
                    "version": "failure-demo-local-v1",
                    "allowed_model_ids": [model_id],
                    "allowed_tool_names": [tool_name],
                },
                "runtime_scope": {"tenant_id": "tenant", "project_id": "project"},
                "runtime_context_hash": runtime_context_hash(None),
            }
        }
    }


def test_failure_demo_tool_is_terminal() -> None:
    config = _config("runtime:failure-demo", "unrecoverable_tool")
    graph = asyncio.run(get_agent(config))
    with pytest.raises(RuntimeError, match="runtime.demo.unrecoverable_tool"):
        asyncio.run(graph.ainvoke({"messages": [AIMessage(content="trigger")]}, config))


def test_timeout_demo_remains_cancellable() -> None:
    config = _config("runtime:timeout-demo", "slow_tool")
    graph = asyncio.run(get_timeout_agent(config))
    with pytest.raises(TimeoutError):
        asyncio.run(
            asyncio.wait_for(
                graph.ainvoke({"messages": [AIMessage(content="trigger")]}, config),
                timeout=0.01,
            )
        )


def test_disconnect_demo_completes_deterministically() -> None:
    graph = asyncio.run(get_disconnect_agent({}))
    result = asyncio.run(graph.ainvoke({"message": "disconnect"}))
    assert result["result"] == "disconnect-complete"


def test_recovery_demo_persists_marker_once() -> None:
    graph = asyncio.run(get_recovery_agent({}))
    result = asyncio.run(graph.ainvoke({"delay_seconds": 0}))
    assert result == {
        "delay_seconds": 0,
        "marker": "checkpointed",
        "marker_attempts": 1,
        "completed": True,
    }
