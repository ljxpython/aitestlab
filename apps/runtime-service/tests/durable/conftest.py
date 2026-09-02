from __future__ import annotations

import asyncio
import os

import httpx
import pytest

from .local_auth import _local_token, get_authenticated_client


@pytest.fixture
def durable_url() -> str:
    url = os.getenv("RUNTIME_DURABLE_URL")
    if not url:
        pytest.skip("RUNTIME_DURABLE_URL is required for durable tests")
    return url


@pytest.fixture(scope="session", autouse=True)
def register_r6_assistants() -> None:
    """Register every graph used by the durable suite in a fresh test database."""

    base_url = os.getenv("RUNTIME_DURABLE_URL")
    if not base_url:
        return

    async def register() -> None:
        client = get_authenticated_client(base_url)
        try:
            assistants = await client.assistants.search(limit=100)
        finally:
            await client.aclose()

        existing = {
            item.get("graph_id")
            for item in assistants
            if isinstance(item, dict)
        }
        required = {
            "reference_agent",
            "workflow_demo",
            "backend_demo",
            "workspace_demo",
            "failure_demo",
            "timeout_demo",
            "disconnect_demo",
            "recovery_demo",
        }
        missing = required - existing
        if not missing:
            return
        headers = {"Authorization": f"Bearer {_local_token()}"}
        async with httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=10, trust_env=False
        ) as http:
            for graph_id in sorted(missing):
                response = await http.post(
                    "/assistants",
                    json={"graph_id": graph_id, "name": f"r6-{graph_id}"},
                )
                response.raise_for_status()

    asyncio.run(register())


@pytest.fixture
def durable_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_ASSISTANT_ID", "reference_agent")


@pytest.fixture
def durable_lifecycle_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_LIFECYCLE_ASSISTANT_ID", "recovery_demo")


@pytest.fixture
def durable_failure_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_FAILURE_ASSISTANT_ID", "failure_demo")


@pytest.fixture
def durable_timeout_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_TIMEOUT_ASSISTANT_ID", "timeout_demo")


@pytest.fixture
def durable_timeout_enabled() -> None:
    if os.getenv("RUNTIME_DURABLE_TIMEOUT_ENABLED") != "1":
        pytest.skip(
            "RUNTIME_DURABLE_TIMEOUT_ENABLED=1 is required with a Worker deadline"
        )


@pytest.fixture
def durable_disconnect_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_DISCONNECT_ASSISTANT_ID", "disconnect_demo")


@pytest.fixture
def durable_workflow_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_WORKFLOW_ASSISTANT_ID", "workflow_demo")


@pytest.fixture
def durable_backend_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_BACKEND_ASSISTANT_ID", "backend_demo")


@pytest.fixture
def durable_workspace_assistant_id() -> str:
    return os.getenv("RUNTIME_DURABLE_WORKSPACE_ASSISTANT_ID", "workspace_demo")
