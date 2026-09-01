from __future__ import annotations

import asyncio
import uuid

import pytest
from langgraph_sdk import get_client


pytestmark = [pytest.mark.integration, pytest.mark.durable]


def _thread_id() -> str:
    return str(uuid.uuid4())


def test_backend_demo_keeps_thread_checkpoints_isolated(
    durable_url: str, durable_backend_assistant_id: str
) -> None:
    asyncio.run(_test_backend_isolation(durable_url, durable_backend_assistant_id))


async def _test_backend_isolation(base_url: str, assistant_id: str) -> None:
    durable_client = get_client(url=base_url)
    thread_ids = [_thread_id(), _thread_id()]
    try:
        for thread_id in thread_ids:
            await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
            await durable_client.runs.wait(
                thread_id,
                assistant_id,
                input={"messages": [{"role": "user", "content": thread_id}]},
                durability="sync",
            )

        states = [await durable_client.threads.get_state(thread_id) for thread_id in thread_ids]
        checkpoints = [
            state.get("checkpoint") if isinstance(state, dict) else state.checkpoint
            for state in states
        ]
        checkpoint_ids = [item.get("id") for item in checkpoints if isinstance(item, dict)]
        assert len(checkpoint_ids) == 2
        assert len(set(checkpoint_ids)) == 2
    finally:
        await durable_client.aclose()
