"""Deterministic graph for SSE disconnect acceptance."""

from __future__ import annotations

import asyncio
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.pregel import Pregel


class DisconnectState(TypedDict, total=False):
    message: str
    result: str


async def finish(state: DisconnectState) -> dict[str, str]:
    await asyncio.sleep(2)
    return {"result": state.get("message", "disconnect") + "-complete"}


_builder = StateGraph(DisconnectState)
_builder.add_node("finish", finish)
_builder.add_edge(START, "finish")
_builder.add_edge("finish", END)
_graph = _builder.compile()


async def get_agent(_config: RunnableConfig) -> Pregel:
    return _graph


__all__ = ["get_agent"]
