from __future__ import annotations

import asyncio
import contextlib
import os
import uuid

import pytest

from .local_auth import get_authenticated_client


pytestmark = [pytest.mark.integration, pytest.mark.durable]


def _thread_id() -> str:
    return str(uuid.uuid4())


async def _stream_run(client, thread_id: str, assistant_id: str, **kwargs: object):
    payload = dict(kwargs)
    input_data = payload.pop(
        "input", {"messages": [{"role": "user", "content": "durable"}]}
    )
    durability = payload.pop("durability", "sync")
    parts = []
    async for part in client.runs.stream(
        thread_id,
        assistant_id,
        input=input_data,
        stream_mode=payload.pop("stream_mode", ["values", "updates"]),
        stream_resumable=True,
        on_disconnect="continue",
        durability=durability,
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


@pytest.mark.parametrize("durability", ["async", "exit"])
def test_async_and_exit_runs_persist_terminal_state(
    durable_url: str, durable_assistant_id: str, durability: str
) -> None:
    asyncio.run(_test_durability_mode(durable_url, durable_assistant_id, durability))


async def _test_durability_mode(
    base_url: str, assistant_id: str, durability: str
) -> None:
    durable_client = get_authenticated_client(base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        parts = await _stream_run(
            durable_client,
            thread_id,
            assistant_id,
            durability=durability,
            input={"messages": [{"role": "user", "content": durability}]},
        )
        assert parts
        run_id = next(part.data["run_id"] for part in parts if part.event == "metadata")
        assert _status(await durable_client.runs.get(thread_id, run_id)) == "success"
        state = await durable_client.threads.get_state(thread_id)
        checkpoint = state.get("checkpoint") if isinstance(state, dict) else state.checkpoint
        assert checkpoint
    finally:
        await durable_client.aclose()


async def _test_sync_run(base_url: str, assistant_id: str) -> None:
    durable_client = get_authenticated_client(base_url)
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
    durable_client = get_authenticated_client(base_url)
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


def test_two_sequential_workflow_interrupts_resume_in_order(
    durable_url: str, durable_workflow_assistant_id: str
) -> None:
    asyncio.run(
        _test_two_sequential_workflow_interrupts(
            durable_url, durable_workflow_assistant_id
        )
    )


async def _test_two_sequential_workflow_interrupts(
    base_url: str, assistant_id: str
) -> None:
    durable_client = get_authenticated_client(base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        first = await _stream_run(
            durable_client,
            thread_id,
            assistant_id,
            input={
                "message": "durable workflow",
                "route": "reject",
                "requires_confirmation": True,
            },
        )
        assert any("workflow_confirmation" in str(part.data) for part in first)

        second = await _stream_run(
            durable_client,
            thread_id,
            assistant_id,
            input=None,
            command={"resume": {"missing-interrupt-id": "approve"}},
        )
        assert any("workflow.invalid_resume" in str(part.data) for part in second)
        state = await durable_client.threads.get_state(thread_id)
        state_values = state.get("values", {}) if isinstance(state, dict) else state.values
        state_interrupts = (
            state.get("interrupts", []) if isinstance(state, dict) else state.interrupts
        )
        assert state_values["prepared_count"] == 1
        assert state_interrupts
        interrupt = state_interrupts[0]
        interrupt_id = interrupt.get("id") if isinstance(interrupt, dict) else interrupt.id

        completed = await _stream_run(
            durable_client,
            thread_id,
            assistant_id,
            input=None,
            command={"resume": {interrupt_id: "approve"}},
        )
        assert any("workflow approved: durable workflow" in str(part.data) for part in completed)
        final_state = await durable_client.threads.get_state(thread_id)
        final_values = (
            final_state.get("values", {})
            if isinstance(final_state, dict)
            else final_state.values
        )
        assert final_values["prepared_count"] == 1
        assert final_values["confirmation"] == "approve"
    finally:
        await durable_client.aclose()


def test_resumable_stream_replays_without_duplicate_event_ids(
    durable_url: str, durable_assistant_id: str
) -> None:
    asyncio.run(_test_resumable_stream(durable_url, durable_assistant_id))

async def _test_resumable_stream(base_url: str, assistant_id: str) -> None:
    durable_client = get_authenticated_client(base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        parts = await _stream_run(durable_client, thread_id, assistant_id)
        run_id = next(part.data["run_id"] for part in parts if part.event == "metadata")
        ids = [int(part.id) for part in parts if part.id]
        assert ids == sorted(set(ids))
        assert ids
        replay = []
        async for part in durable_client.runs.join_stream(
            thread_id, run_id, last_event_id=str(ids[0])
        ):
            replay.append(part)
        replay_ids = [int(part.id) for part in replay if part.id]
        assert replay_ids == [event_id for event_id in ids if event_id > ids[0]]

        second = await _stream_run(
            durable_client,
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "cursor gap"}]},
        )
        second_run_id = next(
            part.data["run_id"] for part in second if part.event == "metadata"
        )
        expired = [
            part
            async for part in durable_client.runs.join_stream(
                thread_id, second_run_id, last_event_id=str(ids[0])
            )
        ]
        assert any(
            part.event == "error"
            and isinstance(part.data, dict)
            and part.data.get("detail") == "cursor_expired"
            and part.data.get("recovery") == "run_snapshot"
            for part in expired
        )
    finally:
        await durable_client.aclose()


def test_sse_disconnect_does_not_cancel_run(
    durable_url: str, durable_disconnect_assistant_id: str
) -> None:
    asyncio.run(_test_sse_disconnect(durable_url, durable_disconnect_assistant_id))


async def _test_sse_disconnect(base_url: str, assistant_id: str) -> None:
    durable_client = get_authenticated_client(base_url)
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        run = await durable_client.runs.create(
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "reply with disconnect-ok"}]},
            stream_mode=["values", "updates"],
            stream_resumable=True,
            durability="sync",
        )
        run_id = run.get("run_id") if isinstance(run, dict) else run.run_id
        async with contextlib.aclosing(
            durable_client.runs.join_stream(thread_id, run_id)
        ) as stream:
            first = await anext(stream)
            assert first.event == "metadata"
        observed = await durable_client.runs.get(thread_id, run_id)
        assert _status(observed) in {"pending", "running", "success"}
        await durable_client.runs.join(thread_id, run_id)
        assert _status(await durable_client.runs.get(thread_id, run_id)) == "success"
    finally:
        await durable_client.aclose()


def test_cancel_is_idempotent(durable_url: str, durable_assistant_id: str) -> None:
    asyncio.run(_test_cancel(durable_url, durable_assistant_id))

async def _test_cancel(base_url: str, assistant_id: str) -> None:
    durable_client = get_authenticated_client(base_url)
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
    durable_client = get_authenticated_client(base_url)
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
    durable_url: str, durable_failure_assistant_id: str
) -> None:
    asyncio.run(_test_failure(durable_url, durable_failure_assistant_id))


async def _test_failure(base_url: str, assistant_id: str) -> None:
    durable_client = get_authenticated_client(
        base_url,
        permissions=["runtime.tool.write"],
        allowed_model_ids=["runtime:failure-demo"],
        allowed_tool_names=["unrecoverable_tool"],
    )
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        run = await durable_client.runs.create(
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "fail"}]},
            stream_mode=["values", "updates"],
            stream_resumable=True,
            durability="sync",
        )
        run_id = run.get("run_id") if isinstance(run, dict) else run.run_id
        await durable_client.runs.join(thread_id, run_id)
        runs = await durable_client.runs.list(thread_id)
        matching = [
            item
            for item in runs
            if (item.get("run_id") if isinstance(item, dict) else item.run_id) == run_id
        ]
        assert len(matching) == 1
        assert _status(matching[0]) in {"error", "failed"}
    finally:
        await durable_client.aclose()


def test_run_timeout_is_reported_once(
    durable_url: str,
    durable_timeout_assistant_id: str,
    durable_timeout_enabled: None,
) -> None:
    asyncio.run(_test_timeout(durable_url, durable_timeout_assistant_id))


async def _test_timeout(base_url: str, assistant_id: str) -> None:
    durable_client = get_authenticated_client(
        base_url,
        permissions=["runtime.tool.write"],
        allowed_model_ids=["runtime:timeout-demo"],
        allowed_tool_names=["slow_tool"],
    )
    thread_id = _thread_id()
    try:
        await durable_client.threads.create(thread_id=thread_id, if_exists="raise")
        run = await durable_client.runs.create(
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "timeout"}]},
            stream_mode=["values", "updates"],
            stream_resumable=True,
            durability="sync",
        )
        run_id = run.get("run_id") if isinstance(run, dict) else run.run_id
        await durable_client.runs.join(thread_id, run_id)
        runs = await durable_client.runs.list(thread_id)
        matching = [
            item
            for item in runs
            if (item.get("run_id") if isinstance(item, dict) else item.run_id) == run_id
        ]
        assert len(matching) == 1
        assert _status(matching[0]) == "timeout"
    finally:
        await durable_client.aclose()
