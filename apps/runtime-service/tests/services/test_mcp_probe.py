from __future__ import annotations

import asyncio
from typing import Any

from runtime_service.graphs.mcp_probe import mcp_probe
from runtime_service.runtime.resolver import runtime_context_hash


def _config() -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": "thread-a",
            "langgraph_auth_user": {
                "runtime_principal": {
                    "user_id": "user",
                    "tenant_id": "tenant",
                    "project_id": "project",
                    "role": "developer",
                    "permissions": ["runtime.tool.read"],
                },
                "runtime_policy": {
                    "version": "mcp-probe-test-v1",
                    "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
                    "allowed_tool_names": ["mcp_read"],
                },
                "runtime_scope": {"tenant_id": "tenant", "project_id": "project"},
                "runtime_context_hash": runtime_context_hash(None),
            },
        },
        "metadata": {
            "__graphharbor_thread_metadata": {
                "runtime_resource_bindings": {
                    "schema": "runtime-resource-bindings/v1",
                    "mcp": {
                        "provider": "mcp_http",
                        "resource_id": "resource-a",
                        "tenant_id": "tenant",
                        "project_id": "project",
                        "thread_id": "thread-a",
                    },
                }
            }
        },
    }


def test_mcp_probe_calls_only_the_reconnected_authorized_tool(monkeypatch: Any) -> None:
    seen: dict[str, Any] = {}

    class Tool:
        name = "mcp_read"

        async def ainvoke(self, value: dict[str, str]) -> str:
            seen["value"] = value
            return [{"type": "text", "text": "topic: mcp-provider-ok"}]

    async def load(**kwargs: Any) -> list[Tool]:
        seen["kwargs"] = kwargs
        return [Tool()]

    monkeypatch.setattr("runtime_service.graphs.mcp_probe.load_mcp_tools", load)
    result = asyncio.run(mcp_probe({"topic": "topic"}, _config()))

    assert result == {"observed": "topic: mcp-provider-ok"}
    assert seen["value"] == {"topic": "topic"}
    assert seen["kwargs"]["config"] is not None
