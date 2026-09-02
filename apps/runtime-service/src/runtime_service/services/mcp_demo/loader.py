"""Service-private MCP client and policy checks for the demo."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from runtime_service.runtime import (
    RuntimePrincipal,
    RuntimeResolutionError,
    resolve_resource_binding,
)

_SERVER = Path(__file__).with_name("fake_server.py")


async def load_mcp_tools(
    *,
    allowed_names: tuple[str, ...] = ("mcp_read",),
    conflict: bool = False,
    required: bool = True,
    config: Mapping[str, object] | None = None,
    principal: RuntimePrincipal | None = None,
) -> list[BaseTool]:
    """Load tools through the official MCP adapter, then enforce local policy."""

    connections: Mapping[str, dict[str, object]] = {
        "runtime_demo": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(_SERVER)],
        }
    }
    reconnecting = config is not None or principal is not None
    if reconnecting:
        if config is None or principal is None:
            raise RuntimeResolutionError("runtime.mcp.recovery_failed")
        binding = resolve_resource_binding(config, principal, "mcp")
        if binding.provider != "mcp_http":
            raise RuntimeResolutionError("runtime.mcp.recovery_failed")
        try:
            configured = json.loads(
                os.environ.get("RUNTIME_MCP_CONNECTIONS_JSON", "{}")
            )
            connection = configured[binding.resource_id]
            if (
                not isinstance(connection, dict)
                or connection.get("transport") != "streamable_http"
            ):
                raise ValueError("MCP connection must be streamable_http")
            connections = {"runtime": connection}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeResolutionError("runtime.mcp.recovery_failed") from exc
    elif conflict:
        connections = {
            **connections,
            "runtime_demo_copy": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(_SERVER)],
            },
        }
    client = MultiServerMCPClient(dict(connections), tool_name_prefix=False)
    try:
        tools = await client.get_tools()
    except Exception as exc:
        if not required and not reconnecting:
            return []
        code = (
            "runtime.mcp.recovery_failed"
            if reconnecting
            else "runtime.mcp.required_unavailable"
        )
        raise RuntimeResolutionError(code) from exc
    names = [tool.name for tool in tools]
    if len(names) != len(set(names)):
        raise RuntimeResolutionError("runtime.tool.name_conflict", "tool_name")
    if any(name not in allowed_names for name in names):
        raise RuntimeResolutionError("runtime.tool.not_allowed", "tool_name")
    return tools


__all__ = ["load_mcp_tools"]
