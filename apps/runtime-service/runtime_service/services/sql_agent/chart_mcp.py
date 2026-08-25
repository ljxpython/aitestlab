from __future__ import annotations

import asyncio
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient


async def aget_mcp_server_chart_tools() -> list[Any]:
    client = MultiServerMCPClient(
        {
            "mcp_chart_server": {
                "command": "npx",
                "args": ["-y", "@antv/mcp-server-chart"],
                "transport": "stdio",
            }
        }
    )
    return await client.get_tools()


def get_mcp_server_chart_tools() -> list[Any]:
    # Graph modules can be imported inside the running Agent Server loop. Do
    # not create a coroutine that asyncio.run() cannot own; async resolution
    # happens later through _aget_chart_tools in the middleware path.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(aget_mcp_server_chart_tools())
    return []
