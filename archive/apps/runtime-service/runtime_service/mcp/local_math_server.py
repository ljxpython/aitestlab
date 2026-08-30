from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("LearningMathServer")


@mcp.tool()
def add(a: float, b: float) -> float:
    """计算两个数字的和。"""

    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """计算两个数字的乘积。"""

    return a * b


@mcp.tool()
def square(n: float) -> float:
    """计算一个数字的平方。"""

    return n * n


if __name__ == "__main__":
    mcp.run(transport="stdio")
