from __future__ import annotations

import asyncio
import json

import pytest
from deepagents.backends.protocol import ExecuteResponse
from langsmith.sandbox import SandboxAuthenticationError

from runtime_service.graphs.sandbox_demo import sandbox_probe
from runtime_service.runtime import RuntimePrincipal, RuntimeResolutionError
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.services.backend_demo import agent as backend_agent
from runtime_service.services.mcp_demo import loader as mcp_loader
from runtime_service.services.mcp_demo.loader import load_mcp_tools
from runtime_service.services.sandbox import reconnect_langsmith_sandbox


def _principal() -> RuntimePrincipal:
    return RuntimePrincipal("user", "tenant", "project", "developer", ())


def _config(
    kind: str, provider: str, resource_id: str = "resource-a"
) -> dict[str, object]:
    allowed_tools = (
        ["delete", "edit_file", "glob", "grep", "ls", "read_file", "write_file"]
        if kind == "backend"
        else []
    )
    permissions = (
        ["runtime.tool.read", "runtime.tool.write"] if kind == "backend" else []
    )
    return {
        "configurable": {
            "thread_id": "thread-a",
            "langgraph_auth_user": {
                "runtime_principal": {
                    "user_id": "user",
                    "tenant_id": "tenant",
                    "project_id": "project",
                    "role": "developer",
                    "permissions": permissions,
                },
                "runtime_policy": {
                    "version": "resource-test-v1",
                    "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
                    "allowed_tool_names": allowed_tools,
                },
                "runtime_scope": {"tenant_id": "tenant", "project_id": "project"},
                "runtime_context_hash": runtime_context_hash(None),
            },
        },
        "metadata": {
            "__graphharbor_thread_metadata": {
                "runtime_resource_bindings": {
                    "schema": "runtime-resource-bindings/v1",
                    kind: {
                        "provider": provider,
                        "resource_id": resource_id,
                        "tenant_id": "tenant",
                        "project_id": "project",
                        "thread_id": "thread-a",
                    },
                }
            }
        },
    }


def test_mcp_reconnect_uses_server_connection_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class FakeClient:
        def __init__(self, connections: dict[str, object], **_: object) -> None:
            seen["connections"] = connections

        async def get_tools(self) -> list[object]:
            return []

    monkeypatch.setattr(mcp_loader, "MultiServerMCPClient", FakeClient)
    monkeypatch.setenv(
        "RUNTIME_MCP_CONNECTIONS_JSON",
        json.dumps(
            {"resource-a": {"transport": "streamable_http", "url": "http://mcp"}}
        ),
    )
    tools = asyncio.run(
        load_mcp_tools(config=_config("mcp", "mcp_http"), principal=_principal())
    )
    assert tools == []
    assert seen["connections"] == {
        "runtime": {"transport": "streamable_http", "url": "http://mcp"}
    }


def test_mcp_reconnect_fails_closed_when_connection_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_MCP_CONNECTIONS_JSON", "{}")
    with pytest.raises(RuntimeResolutionError, match="runtime.mcp.recovery_failed"):
        asyncio.run(
            load_mcp_tools(config=_config("mcp", "mcp_http"), principal=_principal())
        )


def test_backend_reconnect_fails_closed_without_thread_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config("backend", "graphharbor_workspace")
    config["metadata"] = {}
    monkeypatch.setenv("GRAPHHARBOR_WORKSPACE_ROOT", "/tmp/r6-workspaces")
    with pytest.raises(RuntimeResolutionError, match="runtime.backend.recovery_failed"):
        asyncio.run(backend_agent.get_agent(config))


def test_sandbox_reconnect_fails_closed_without_provider_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY_PROD", raising=False)
    with pytest.raises(RuntimeResolutionError, match="runtime.sandbox.recovery_failed"):
        asyncio.run(
            reconnect_langsmith_sandbox(_config("sandbox", "langsmith"), _principal())
        )


def test_sandbox_reconnect_fails_closed_on_provider_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> FailingClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get_sandbox(self, *, name: str) -> object:
            raise SandboxAuthenticationError("provider denied access")

    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setattr(
        "runtime_service.services.sandbox.AsyncSandboxClient", FailingClient
    )
    with pytest.raises(RuntimeResolutionError, match="runtime.sandbox.recovery_failed"):
        asyncio.run(
            reconnect_langsmith_sandbox(_config("sandbox", "langsmith"), _principal())
        )


def test_sandbox_probe_closes_reconnected_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSandbox:
        closed = False

        async def aexecute(self, command: str) -> ExecuteResponse:
            assert command == "printf r6-sandbox-ok"
            return ExecuteResponse(output="r6-sandbox-ok", exit_code=0)

        async def aclose(self) -> None:
            self.closed = True

    sandbox = FakeSandbox()

    async def reconnect(*_: object) -> FakeSandbox:
        return sandbox

    monkeypatch.setattr(
        "runtime_service.graphs.sandbox_demo.reconnect_langsmith_sandbox", reconnect
    )
    result = asyncio.run(sandbox_probe({}, _config("sandbox", "langsmith")))
    assert result == {"observed": "r6-sandbox-ok"}
    assert sandbox.closed
