from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import START, StateGraph


class _State(TypedDict):
    text: str


def _append_marker(state: _State) -> _State:
    return {"text": f"{state['text']}!"}


def _graph():
    return StateGraph(_State).add_node("append_marker", _append_marker).add_edge(
        START, "append_marker"
    ).compile()


def test_local_v2_stream_uses_stream_part_shape() -> None:
    async def collect() -> list[dict]:
        return [
            part
            async for part in _graph().astream(
                {"text": "ok"}, stream_mode="updates", version="v2"
            )
        ]

    parts = asyncio.run(collect())

    assert parts == [
        {"type": "updates", "ns": (), "data": {"append_marker": {"text": "ok!"}}}
    ]


def test_local_v3_stream_is_awaitable_internal_projection() -> None:
    async def collect() -> list[dict]:
        stream = await _graph().astream_events({"text": "ok"}, version="v3")
        return [event async for event in stream]

    events = asyncio.run(collect())

    assert [event["seq"] for event in events] == [1, 2]
    assert [event["method"] for event in events] == ["values", "values"]
    assert events[-1]["params"]["data"] == {"text": "ok!"}
