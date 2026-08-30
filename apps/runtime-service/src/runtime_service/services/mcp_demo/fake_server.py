"""Local stdio MCP server used only by the mcp_demo."""

from mcp.server.fastmcp import FastMCP

server = FastMCP("runtime-demo")


@server.tool()
def mcp_read(topic: str) -> str:
    """Read a note from the local fake MCP server."""

    return f"mcp note: {topic.strip()}"


if __name__ == "__main__":
    server.run("stdio")
