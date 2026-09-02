from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

from .local_auth import get_authenticated_client

pytestmark = [pytest.mark.integration, pytest.mark.durable]


def _thread_id() -> str:
    return str(uuid.uuid4())


def _resource_metadata(kind: str, thread_id: str) -> dict[str, object]:
    return {
        "runtime_resource_bindings": {
            "schema": "runtime-resource-bindings/v1",
            kind: {
                "provider": "graphharbor_workspace",
                "resource_id": thread_id,
                "tenant_id": "r6-smoke-tenant",
                "project_id": "r6-smoke-project",
                "thread_id": thread_id,
            },
        }
    }


def test_backend_demo_keeps_thread_checkpoints_isolated(
    durable_url: str, durable_backend_assistant_id: str
) -> None:
    asyncio.run(_test_backend_isolation(durable_url, durable_backend_assistant_id))


async def _test_backend_isolation(base_url: str, assistant_id: str) -> None:
    durable_client = get_authenticated_client(
        base_url,
        permissions=["runtime.tool.read", "runtime.tool.write"],
        allowed_model_ids=["deepseek:DeepSeek-V4-Flash"],
        allowed_tool_names=[
            "delete",
            "edit_file",
            "glob",
            "grep",
            "ls",
            "read_file",
            "write_file",
        ],
    )
    thread_ids = [_thread_id(), _thread_id()]
    try:
        for thread_id in thread_ids:
            await durable_client.threads.create(
                thread_id=thread_id,
                metadata=_resource_metadata("backend", thread_id),
                if_exists="raise",
            )
            run = await durable_client.runs.wait(
                thread_id,
                assistant_id,
                input={"messages": [{"role": "user", "content": thread_id}]},
                durability="sync",
            )
            assert isinstance(run, dict) and run

        states = [
            await durable_client.threads.get_state(thread_id)
            for thread_id in thread_ids
        ]
        checkpoints = [
            state.get("checkpoint") if isinstance(state, dict) else state.checkpoint
            for state in states
        ]
        checkpoint_ids = [
            item.get("checkpoint_id") or item.get("id")
            for item in checkpoints
            if isinstance(item, dict)
        ]
        assert len(checkpoint_ids) == 2
        assert all(isinstance(item, str) and item for item in checkpoint_ids)
        assert len(set(checkpoint_ids)) == 2
    finally:
        await durable_client.aclose()


def test_workspace_reconnect_and_tenant_thread_isolation(
    durable_url: str, durable_workspace_assistant_id: str
) -> None:
    asyncio.run(
        _test_workspace_reconnect_and_isolation(
            durable_url, durable_workspace_assistant_id
        )
    )


async def _test_workspace_reconnect_and_isolation(
    base_url: str, assistant_id: str
) -> None:
    client = get_authenticated_client(base_url)
    other_tenant = get_authenticated_client(
        base_url,
        tenant_id="r6-other-tenant",
        project_id="r6-other-project",
        user_id="r6-other-user",
    )
    first_thread, second_thread = _thread_id(), _thread_id()
    try:
        await client.threads.create(
            thread_id=first_thread,
            metadata=_resource_metadata("workspace", first_thread),
            if_exists="raise",
        )
        await client.threads.create(
            thread_id=second_thread,
            metadata=_resource_metadata("workspace", second_thread),
            if_exists="raise",
        )
        first = await client.runs.wait(
            first_thread,
            assistant_id,
            input={"operation": "write", "path": "/r6.txt", "content": first_thread},
            durability="sync",
        )
        assert first
        rebuilt = await client.runs.wait(
            first_thread,
            assistant_id,
            input={"operation": "read", "path": "/r6.txt"},
            durability="sync",
        )
        rebuilt_values = (
            rebuilt.get("values", {}) if isinstance(rebuilt, dict) else rebuilt.values
        )
        assert rebuilt_values["observed"] == first_thread

        isolated = await client.runs.create(
            second_thread,
            assistant_id,
            input={"operation": "read", "path": "/r6.txt"},
            durability="sync",
        )
        isolated_run_id = (
            isolated.get("run_id") if isinstance(isolated, dict) else isolated.run_id
        )
        await client.runs.join(second_thread, isolated_run_id)
        isolated_run = await client.runs.get(second_thread, isolated_run_id)
        isolated_status = (
            isolated_run.get("status")
            if isinstance(isolated_run, dict)
            else isolated_run.status
        )
        assert isolated_status in {"error", "failed"}

        with pytest.raises(httpx.HTTPStatusError):
            await other_tenant.threads.get(first_thread)
    finally:
        await client.aclose()
        await other_tenant.aclose()
