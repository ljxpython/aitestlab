from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("LearningTextServer")


@mcp.tool()
def reverse_text(text: str) -> str:
    """反转输入字符串。"""

    return text[::-1]


@mcp.tool()
def text_length(text: str) -> int:
    """返回字符串长度。"""

    return len(text)


if __name__ == "__main__":
    mcp.run(transport="stdio")
