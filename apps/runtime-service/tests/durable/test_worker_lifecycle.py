from __future__ import annotations

import asyncio
import os
import subprocess
import time
import uuid

import pytest
from langgraph_sdk import get_client


pytestmark = [pytest.mark.integration, pytest.mark.durable]


def _thread_id() -> str:
    return str(uuid.uuid4())


def _compose_file() -> str:
    value = os.getenv("RUNTIME_DURABLE_COMPOSE_FILE")
    if not value:
        pytest.skip("RUNTIME_DURABLE_COMPOSE_FILE is required for worker lifecycle tests")
    return value


def test_worker_restart_recovers_scheduled_run(durable_url: str, durable_assistant_id: str) -> None:
    asyncio.run(_test_worker_restart(durable_url, durable_assistant_id, _compose_file()))


async def _test_worker_restart(base_url: str, assistant_id: str, compose_file: str) -> None:
    client = get_client(url=base_url)
    thread_id = _thread_id()
    try:
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        run = await client.runs.create(
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "restart"}]},
            after_seconds=2,
            stream_mode=["values"],
            durability="sync",
        )
        run_id = run.get("run_id") if isinstance(run, dict) else run.run_id
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "restart", "runtime-service"],
            check=True,
            timeout=120,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            current = await client.runs.get(thread_id, run_id)
            status = current.get("status") if isinstance(current, dict) else current.status
            if status in {"success", "error", "failed", "cancelled", "canceled"}:
                assert status in {"success", "error", "failed"}
                return
            await asyncio.sleep(1)
        raise AssertionError("scheduled Run did not reach a terminal state after worker restart")
    finally:
        await client.aclose()


def test_sigterm_drain_keeps_run_recoverable(durable_url: str, durable_assistant_id: str) -> None:
    asyncio.run(_test_sigterm(durable_url, durable_assistant_id, _compose_file()))


async def _test_sigterm(base_url: str, assistant_id: str, compose_file: str) -> None:
    client = get_client(url=base_url)
    thread_id = _thread_id()
    try:
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        run = await client.runs.create(
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "sigterm"}]},
            after_seconds=2,
            stream_mode=["values"],
            durability="sync",
        )
        run_id = run.get("run_id") if isinstance(run, dict) else run.run_id
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "kill", "-s", "SIGTERM", "runtime-service"],
            check=True,
            timeout=120,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            current = await client.runs.get(thread_id, run_id)
            status = current.get("status") if isinstance(current, dict) else current.status
            if status in {"success", "error", "failed", "cancelled", "canceled"}:
                return
            await asyncio.sleep(1)
        raise AssertionError("Run did not become terminal after SIGTERM drain")
    finally:
        await client.aclose()
