from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from langgraph_sdk import get_client


pytestmark = [pytest.mark.integration, pytest.mark.durable]


def _thread_id() -> str:
    return str(uuid.uuid4())


async def _stream_run(client, thread_id: str, assistant_id: str, **kwargs: object):
    payload = dict(kwargs)
    input_data = payload.pop(
        "input", {"messages": [{"role": "user", "content": "durable"}]}
    )
    parts = []
    async for part in client.runs.stream(
        thread_id,
        assistant_id,
        input=input_data,
        stream_mode=payload.pop("stream_mode", ["values", "updates"]),
        stream_resumable=True,
        on_disconnect="continue",
        durability="sync",
        **payload,
    ):
        parts.append(part)
    return parts


def _status(run: object) -> str:
    return run.get("status", "") if isinstance(run, dict) else run.status


def test_sync_run_reuses_thread_and_persists_checkpoint(
    durable_url: str, durable_assistant_id: str
) -> None:
    asyncio.run(_test_sync_run(durable_url, durable_assistant_id))


async def _test_sync_run(base_url: str, assistant_id: str) -> None:
    durable_client = get_client(url=base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        first = await _stream_run(durable_client, thread_id, assistant_id)
        second = await _stream_run(
            durable_client,
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "second run"}]},
        )
        assert first and second
        first_run_id = next(part.data["run_id"] for part in first if part.event == "metadata")
        second_run_id = next(part.data["run_id"] for part in second if part.event == "metadata")
        assert _status(await durable_client.runs.get(thread_id, first_run_id)) == "success"
        assert _status(await durable_client.runs.get(thread_id, second_run_id)) == "success"
        state = await durable_client.threads.get_state(thread_id)
        checkpoint = state.get("checkpoint") if isinstance(state, dict) else state.checkpoint
        assert checkpoint
    finally:
        await durable_client.aclose()


def test_interrupt_before_and_resume_keep_thread_scope(
    durable_url: str, durable_assistant_id: str
) -> None:
    asyncio.run(_test_interrupt_before_and_resume(durable_url, durable_assistant_id))

async def _test_interrupt_before_and_resume(base_url: str, assistant_id: str) -> None:
    durable_client = get_client(url=base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        parts = await _stream_run(
            durable_client,
            thread_id,
            assistant_id,
            interrupt_before=[os.getenv("RUNTIME_DURABLE_INTERRUPT_NODE", "model")],
        )
        assert any("__interrupt__" in str(part.data) for part in parts)
        resumed = await _stream_run(
            durable_client,
            thread_id,
            assistant_id,
            input=None,
            command={"resume": True},
        )
        assert resumed
    finally:
        await durable_client.aclose()


def test_resumable_stream_replays_without_duplicate_event_ids(
    durable_url: str, durable_assistant_id: str
) -> None:
    asyncio.run(_test_resumable_stream(durable_url, durable_assistant_id))

async def _test_resumable_stream(base_url: str, assistant_id: str) -> None:
    durable_client = get_client(url=base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        parts = await _stream_run(durable_client, thread_id, assistant_id)
        run_id = next(part.data["run_id"] for part in parts if part.event == "metadata")
        ids = [part.id for part in parts if part.id]
        assert ids == list(dict.fromkeys(ids))
        replay = []
        async for part in durable_client.runs.join_stream(
            thread_id, run_id, last_event_id=ids[-1] if ids else None
        ):
            replay.append(part)
        assert all(part.id not in ids for part in replay if part.id)
    finally:
        await durable_client.aclose()


def test_cancel_is_idempotent(durable_url: str, durable_assistant_id: str) -> None:
    asyncio.run(_test_cancel(durable_url, durable_assistant_id))

async def _test_cancel(base_url: str, assistant_id: str) -> None:
    durable_client = get_client(url=base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        run = await durable_client.runs.create(
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "cancel"}]},
            stream_mode=["values"],
            stream_resumable=True,
            durability="sync",
            after_seconds=5,
        )
        run_id = run.get("run_id") if isinstance(run, dict) else run.run_id
        await durable_client.runs.cancel(thread_id, run_id, wait=True)
        await durable_client.runs.cancel(thread_id, run_id, wait=True)
        result = await durable_client.runs.get(thread_id, run_id)
        assert _status(result) in {"cancelled", "canceled", "interrupted"}
    finally:
        await durable_client.aclose()


def test_invalid_checkpoint_is_rejected(durable_url: str, durable_assistant_id: str) -> None:
    asyncio.run(_test_invalid_checkpoint(durable_url, durable_assistant_id))

async def _test_invalid_checkpoint(base_url: str, assistant_id: str) -> None:
    durable_client = get_client(url=base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        with pytest.raises(Exception):
            await durable_client.runs.wait(
                thread_id,
                assistant_id,
                input={"messages": [{"role": "user", "content": "invalid checkpoint"}]},
                checkpoint_id="missing-r6-checkpoint",
                durability="sync",
            )
    finally:
        await durable_client.aclose()


def test_unrecoverable_input_is_reported_as_run_failure(
    durable_url: str, durable_assistant_id: str
) -> None:
    failure_assistant = os.getenv("RUNTIME_DURABLE_FAILURE_ASSISTANT_ID")
    if not failure_assistant:
        pytest.skip("RUNTIME_DURABLE_FAILURE_ASSISTANT_ID is required for failure tests")
    asyncio.run(_test_failure(durable_url, failure_assistant))


async def _test_failure(base_url: str, assistant_id: str) -> None:
    durable_client = get_client(url=base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        with pytest.raises(Exception):
            await durable_client.runs.wait(
                thread_id,
                assistant_id,
                input={"unexpected": "invalid"},
                durability="sync",
            )
        runs = await durable_client.runs.list(thread_id)
        assert runs
        assert _status(runs[0]) in {"error", "failed"}
    finally:
        await durable_client.aclose()
