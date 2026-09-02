from __future__ import annotations

import asyncio

import pytest

from runtime_service.graphs.workspace_demo import get_agent
from runtime_service.runtime import RuntimeAuthError, RuntimeResolutionError
from runtime_service.runtime.resolver import runtime_context_hash


def _config(
    thread_id: str, *, tenant_id: str = "tenant", project_id: str = "project"
) -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            "langgraph_auth_user": {
                "runtime_principal": {
                    "user_id": "user",
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "role": "developer",
                    "permissions": ["runtime.tool.write"],
                },
                "runtime_policy": {
                    "version": "workspace-test-v1",
                    "allowed_model_ids": ["runtime:workspace-demo"],
                    "allowed_tool_names": [],
                },
                "runtime_scope": {"tenant_id": tenant_id, "project_id": project_id},
                "runtime_context_hash": runtime_context_hash(None),
            },
        },
        "metadata": {
            "__graphharbor_thread_metadata": {
                "runtime_resource_bindings": {
                    "schema": "runtime-resource-bindings/v1",
                    "workspace": {
                        "provider": "graphharbor_workspace",
                        "resource_id": thread_id,
                        "tenant_id": tenant_id,
                        "project_id": project_id,
                        "thread_id": thread_id,
                    },
                }
            }
        },
    }


def test_workspace_rebuilds_for_same_thread_and_isolates_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("GRAPHHARBOR_WORKSPACE_ROOT", str(tmp_path))
    config_a = _config("thread-a")
    graph = asyncio.run(get_agent(config_a))
    asyncio.run(graph.ainvoke({"operation": "write", "content": "a"}, config_a))
    rebuilt = asyncio.run(get_agent(config_a))
    result = asyncio.run(rebuilt.ainvoke({"operation": "read"}, config_a))
    assert result["observed"] == "a"

    config_b = _config("thread-b")
    with pytest.raises(
        RuntimeResolutionError, match="runtime.workspace.recovery_failed"
    ):
        asyncio.run(rebuilt.ainvoke({"operation": "read"}, config_b))


def test_workspace_recovery_fails_closed_without_absolute_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GRAPHHARBOR_WORKSPACE_ROOT", "relative-workspaces")
    graph = asyncio.run(get_agent(_config("thread-a")))
    with pytest.raises(
        RuntimeResolutionError, match="runtime.workspace.recovery_failed"
    ):
        asyncio.run(
            graph.ainvoke({"operation": "write", "content": "x"}, _config("thread-a"))
        )


def test_workspace_requires_verified_principal(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("GRAPHHARBOR_WORKSPACE_ROOT", str(tmp_path))
    graph = asyncio.run(get_agent({}))
    with pytest.raises(RuntimeAuthError, match="runtime.auth.invalid_principal"):
        asyncio.run(
            graph.ainvoke({"operation": "write"}, {"configurable": {"thread_id": "x"}})
        )


@pytest.mark.parametrize(
    "path", ["relative.txt", "/../escape.txt", "/safe\\escape.txt"]
)
def test_workspace_rejects_unsafe_virtual_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path, path: str
) -> None:
    monkeypatch.setenv("GRAPHHARBOR_WORKSPACE_ROOT", str(tmp_path))
    graph = asyncio.run(get_agent(_config("thread-a")))
    with pytest.raises(
        RuntimeResolutionError, match="runtime.workspace.recovery_failed"
    ):
        asyncio.run(
            graph.ainvoke({"operation": "write", "path": path}, _config("thread-a"))
        )
