"""Service-private MCP client and policy checks for the demo."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from runtime_service.runtime import RuntimeResolutionError

_SERVER = Path(__file__).with_name("fake_server.py")


async def load_mcp_tools(
    *,
    allowed_names: tuple[str, ...] = ("mcp_read",),
    conflict: bool = False,
    required: bool = True,
) -> list[BaseTool]:
    """Load tools through the official MCP adapter, then enforce local policy."""

    connections: Mapping[str, dict[str, object]] = {
        "runtime_demo": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(_SERVER)],
        }
    }
    if conflict:
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
        if not required:
            return []
        raise RuntimeResolutionError("runtime.mcp.required_unavailable") from exc
    names = [tool.name for tool in tools]
    if len(names) != len(set(names)):
        raise RuntimeResolutionError("runtime.tool.name_conflict", "tool_name")
    if any(name not in allowed_names for name in names):
        raise RuntimeResolutionError("runtime.tool.not_allowed", "tool_name")
    return tools


__all__ = ["load_mcp_tools"]
