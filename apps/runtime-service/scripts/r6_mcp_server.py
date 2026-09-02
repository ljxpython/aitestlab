"""Deterministic Streamable HTTP MCP provider for the R6 acceptance harness."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "runtime-r6-mcp",
    instructions="R6-only deterministic provider; never use this fixture in production.",
    host="127.0.0.1",
    port=int(os.environ.get("R6_MCP_PORT", "31330")),
    streamable_http_path="/mcp",
    stateless_http=True,
)


@mcp.tool()
def mcp_read(topic: str) -> str:
    """Return a deterministic fact for the Runtime MCP recovery probe."""

    return f"{topic}: mcp-provider-ok"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
