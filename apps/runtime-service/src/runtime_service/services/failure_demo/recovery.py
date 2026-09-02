"""Deterministic graph for R6 Worker takeover acceptance."""

from __future__ import annotations

import asyncio
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.pregel import Pregel


class RecoveryState(TypedDict, total=False):
    delay_seconds: float
    marker: str
    marker_attempts: int
    completed: bool


async def persist_marker(state: RecoveryState) -> RecoveryState:
    return {
        "marker": "checkpointed",
        "marker_attempts": int(state.get("marker_attempts", 0)) + 1,
    }


async def finish(state: RecoveryState) -> RecoveryState:
    await asyncio.sleep(float(state.get("delay_seconds", 30)))
    return {
        "marker": str(state.get("marker", "missing")),
        "marker_attempts": int(state.get("marker_attempts", 0)),
        "completed": True,
    }


_builder = StateGraph(RecoveryState)
_builder.add_node("persist_marker", persist_marker)
_builder.add_node("finish", finish)
_builder.add_edge(START, "persist_marker")
_builder.add_edge("persist_marker", "finish")
_builder.add_edge("finish", END)
_graph = _builder.compile()


async def get_agent(_config: RunnableConfig) -> Pregel:
    return _graph


__all__ = ["get_agent"]
