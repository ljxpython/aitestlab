from __future__ import annotations

import asyncio
import importlib
from typing import Any

from runtime_service.mcp.servers import get_mcp_server_specs


async def get_mcp_tools(server_names: list[str]) -> list[Any]:
    if not server_names:
        return []

    mcp_client_module = await asyncio.to_thread(
        importlib.import_module, "langchain_mcp_adapters.client"
    )
    multi_server_mcp_client = getattr(mcp_client_module, "MultiServerMCPClient")

    specs = get_mcp_server_specs()
    selected: dict[str, dict[str, Any]] = {}
    for name in server_names:
        if name not in specs:
            allowed = ", ".join(sorted(specs.keys()))
            raise ValueError(f"Unsupported mcp server '{name}', allowed: {allowed}")
        selected[name] = specs[name]

    client = multi_server_mcp_client(selected)
    return await client.get_tools()
