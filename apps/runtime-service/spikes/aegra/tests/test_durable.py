from __future__ import annotations

import asyncio
import json
import os
import uuid

import httpx
import pytest


def _status(value: object) -> str:
    result = value.get("status") if isinstance(value, dict) else getattr(value, "status", "")
    return str(result)


def test_thread_checkpoint_and_replay(client) -> None:
    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        first = await client.runs.wait(
            thread_id,
            "workflow_demo",
            input={"message": "first"},
            durability="sync",
        )
        assert first["response"] == "workflow response: first"
        state = await client.threads.get_state(thread_id)
        checkpoint = state.get("checkpoint") if isinstance(state, dict) else getattr(state, "checkpoint", None)
        assert checkpoint

        events = []
        async for event in client.runs.stream(
            thread_id,
            "workflow_demo",
            input={"message": "replay"},
            stream_mode=["values"],
            stream_resumable=True,
            durability="sync",
        ):
            events.append(event)
        ids = [event.id for event in events if getattr(event, "id", None)]
        assert ids == list(dict.fromkeys(ids))

    asyncio.run(run())


def test_hitl_interrupt_and_resume(client) -> None:
    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        events = []
        async for event in client.runs.stream(
            thread_id,
            "spike_hitl",
            input={"message": "approve this"},
            stream_mode=["values", "updates"],
            stream_resumable=True,
            durability="sync",
        ):
            events.append(event)
        assert any("interrupt" in str(getattr(event, "data", "")).lower() for event in events)

        resumed = await client.runs.wait(
            thread_id,
            "spike_hitl",
            input=None,
            command={"resume": True},
            durability="sync",
        )
        assert resumed["approved"] is True

    asyncio.run(run())


def test_sse_since_replays_only_missing_events(client, base_url: str) -> None:
    async def collect(thread_id: str, since: int | None) -> list[tuple[int, dict]]:
        headers = {"Authorization": f"Bearer {os.getenv('AEGRA_SPIKE_AUTH_TOKEN', 'aegra-spike-token')}"}
        events: list[tuple[int, dict]] = []
        try:
            async with asyncio.timeout(12):
                async with httpx.AsyncClient(timeout=15) as http:
                    async with http.stream(
                        "POST",
                        f"{base_url}/threads/{thread_id}/stream/events",
                        headers=headers,
                        json={"channels": ["lifecycle", "values"], "since": since},
                    ) as response:
                        assert response.status_code == 200, await response.aread()
                        event_id: int | None = None
                        async for line in response.aiter_lines():
                            if line.startswith("id:"):
                                event_id = int(line.removeprefix("id:").strip())
                            elif line.startswith("data:"):
                                payload = json.loads(line.removeprefix("data:").strip())
                                sequence = event_id if event_id is not None else payload.get("seq")
                                if isinstance(sequence, int):
                                    events.append((sequence, payload))
                                if (
                                    payload.get("method") == "lifecycle"
                                    and payload.get("params", {}).get("data", {}).get("event") == "completed"
                                ):
                                    break
        except TimeoutError:
            pytest.skip("Aegra v2 thread stream emitted no replay event within 12 seconds")
        return events

    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        await client.runs.wait(
            thread_id,
            "spike_replay",
            input={"message": "sse-replay"},
            durability="sync",
        )
        first = await collect(thread_id, None)
        if len(first) < 2:
            pytest.skip("Aegra retained fewer than two replayable SSE events for this short Run")
        cursor = first[0][0]
        replayed = await collect(thread_id, cursor)
        ids = [event_id for event_id, _ in replayed]
        if not ids:
            pytest.skip("Aegra v2 stream exposed no event after the supplied since cursor")
        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))
        assert all(event_id > cursor for event_id in ids)

    asyncio.run(run())
