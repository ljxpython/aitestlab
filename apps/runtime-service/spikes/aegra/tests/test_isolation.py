from __future__ import annotations

import asyncio
import uuid


def test_workspace_markers_are_thread_scoped(client) -> None:
    async def run() -> None:
        thread_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        for thread_id in thread_ids:
            await client.threads.create(thread_id=thread_id, if_exists="raise")
            await client.runs.wait(
                thread_id,
                "spike_workspace",
                input={"marker": thread_id},
                durability="sync",
            )

        states = [await client.threads.get_state(thread_id) for thread_id in thread_ids]
        paths = []
        for state in states:
            values = state.get("values", {}) if isinstance(state, dict) else getattr(state, "values", {})
            paths.append(values.get("path"))
        assert all(paths)
        assert len(set(paths)) == len(thread_ids)

    asyncio.run(run())


def test_deep_agent_backend_checkpoints_are_thread_scoped(client) -> None:
    async def run() -> None:
        thread_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        for thread_id in thread_ids:
            await client.threads.create(thread_id=thread_id, if_exists="raise")
            await client.runs.wait(
                thread_id,
                "backend_demo",
                input={"messages": [{"role": "user", "content": thread_id}]},
                durability="sync",
            )
        checkpoints = []
        for thread_id in thread_ids:
            state = await client.threads.get_state(thread_id)
            checkpoint = state.get("checkpoint") if isinstance(state, dict) else getattr(state, "checkpoint", None)
            checkpoints.append(checkpoint.get("checkpoint_id") if isinstance(checkpoint, dict) else None)
        assert all(checkpoints)
        assert len(set(checkpoints)) == len(thread_ids)

    asyncio.run(run())
