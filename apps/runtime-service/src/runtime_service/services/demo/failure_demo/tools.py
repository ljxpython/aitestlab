"""Tools owned by the failure demo Service."""

import asyncio

from langchain.tools import tool


@tool
def unrecoverable_tool(reason: str) -> str:
    """Raise a terminal Tool error for durable failure acceptance tests."""

    del reason
    raise RuntimeError("runtime.demo.unrecoverable_tool")


@tool
async def slow_tool(delay_seconds: float = 30) -> str:
    """Sleep long enough for the Agent Server run deadline to expire."""

    await asyncio.sleep(delay_seconds)
    return "completed"


__all__ = ["slow_tool", "unrecoverable_tool"]
