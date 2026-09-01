from __future__ import annotations

import asyncio
import os
import subprocess
import time
import uuid

import pytest


def test_protected_context_does_not_execute(client) -> None:
    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        with pytest.raises(Exception):
            await client.runs.wait(
                thread_id,
                "reference_agent",
                input={"messages": [{"role": "user", "content": "override"}]},
                context={"user_id": "attacker", "tenant_id": "other"},
                durability="sync",
            )

    asyncio.run(run())


def test_unauthorized_model_and_tool_context_is_rejected(client) -> None:
    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        for context in (
            {"model_id": "provider:unauthorized"},
            {"tools": ["admin_tool"]},
        ):
            run_obj = await client.runs.create(
                thread_id,
                "reference_agent",
                input={"messages": [{"role": "user", "content": "reject"}]},
                context=context,
                durability="sync",
            )
            run_id = run_obj.get("run_id") if isinstance(run_obj, dict) else run_obj.run_id
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                current = await client.runs.get(thread_id, run_id)
                status = str(current.get("status") if isinstance(current, dict) else current.status)
                if status in {"error", "failed"}:
                    break
                await asyncio.sleep(1)
            else:
                raise AssertionError("Unauthorized context Run did not fail closed")

    asyncio.run(run())


def test_worker_restart_recovery(client) -> None:
    if os.getenv("AEGRA_SPIKE_WORKER_RESTART") != "1":
        pytest.skip("set AEGRA_SPIKE_WORKER_RESTART=1 for worker restart")

    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        run_obj = await client.runs.create(
            thread_id,
            "reference_agent",
            input={"messages": [{"role": "user", "content": "restart"}]},
            after_seconds=2,
            durability="sync",
        )
        run_id = run_obj.get("run_id") if isinstance(run_obj, dict) else run_obj.run_id
        restart_command = os.getenv("AEGRA_SPIKE_RESTART_COMMAND")
        if not restart_command:
            pytest.skip("set AEGRA_SPIKE_RESTART_COMMAND to restart the local Aegra process")
        subprocess.run(restart_command, shell=True, check=True, timeout=120)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            current = await client.runs.get(thread_id, run_id)
            if str(current.get("status") if isinstance(current, dict) else current.status) in {
                "success",
                "error",
                "failed",
                "interrupted",
            }:
                return
            await asyncio.sleep(2)
        raise AssertionError("Run did not reach a terminal state after worker restart")


def test_backend_scope_survives_worker_restart(client) -> None:
    if os.getenv("AEGRA_SPIKE_BACKEND_RESTART") != "1":
        pytest.skip("set AEGRA_SPIKE_BACKEND_RESTART=1 for backend restart")

    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        run_obj = await client.runs.create(
            thread_id,
            "backend_demo",
            input={"messages": [{"role": "user", "content": "backend restart"}]},
            after_seconds=2,
            durability="sync",
        )
        run_id = run_obj.get("run_id") if isinstance(run_obj, dict) else run_obj.run_id
        command = os.getenv("AEGRA_SPIKE_RESTART_COMMAND")
        if not command:
            pytest.skip("set AEGRA_SPIKE_RESTART_COMMAND to restart Aegra")
        subprocess.run(command, shell=True, check=True, timeout=120)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            current = await client.runs.get(thread_id, run_id)
            status = str(current.get("status") if isinstance(current, dict) else current.status)
            if status in {"success", "error", "failed", "interrupted"}:
                assert status == "success"
                state = await client.threads.get_state(thread_id)
                checkpoint = state.get("checkpoint") if isinstance(state, dict) else getattr(state, "checkpoint", None)
                assert checkpoint
                return
            await asyncio.sleep(2)
        raise AssertionError("Backend Run did not converge after worker restart")

    asyncio.run(run())


def test_graceful_shutdown_handoff(client) -> None:
    """Opt-in proof that SIGTERM drains a queued Run and a new worker finishes it."""

    if os.getenv("AEGRA_SPIKE_GRACEFUL_SHUTDOWN") != "1":
        pytest.skip("set AEGRA_SPIKE_GRACEFUL_SHUTDOWN=1 for graceful shutdown")

    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        run_obj = await client.runs.create(
            thread_id,
            "workflow_demo",
            input={"message": "graceful"},
            after_seconds=2,
            durability="sync",
        )
        run_id = run_obj.get("run_id") if isinstance(run_obj, dict) else run_obj.run_id
        command = os.getenv("AEGRA_SPIKE_GRACEFUL_SHUTDOWN_COMMAND")
        if not command:
            pytest.skip("set AEGRA_SPIKE_GRACEFUL_SHUTDOWN_COMMAND to restart Aegra")
        subprocess.run(command, shell=True, check=True, timeout=120)
        deadline = time.monotonic() + 120
        terminal: list[str] = []
        while time.monotonic() < deadline:
            current = await client.runs.get(thread_id, run_id)
            status = str(current.get("status") if isinstance(current, dict) else current.status)
            if status in {"success", "error", "failed", "interrupted"}:
                terminal.append(status)
                break
            await asyncio.sleep(2)
        assert terminal == ["success"]

        # A second read must not manufacture another terminal transition.
        again = await client.runs.get(thread_id, run_id)
        again_status = str(again.get("status") if isinstance(again, dict) else again.status)
        assert again_status == terminal[0]

    asyncio.run(run())


def test_terminal_run_is_stable_after_cancel(client) -> None:
    """The public API must keep a committed success terminal state immutable."""

    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        run_obj = await client.runs.create(
            thread_id,
            "workflow_demo",
            input={"message": "terminal"},
            durability="sync",
        )
        run_id = run_obj.get("run_id") if isinstance(run_obj, dict) else run_obj.run_id
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            current = await client.runs.get(thread_id, run_id)
            status = str(current.get("status") if isinstance(current, dict) else current.status)
            if status == "success":
                break
            await asyncio.sleep(1)
        else:
            raise AssertionError("Run did not reach success")
        try:
            await client.runs.cancel(thread_id, run_id, wait=True)
        except Exception:
            pass
        current = await client.runs.get(thread_id, run_id)
        status = str(current.get("status") if isinstance(current, dict) else current.status)
        assert status == "success"

    asyncio.run(run())
