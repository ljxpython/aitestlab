from __future__ import annotations

import asyncio
import os
import time
import uuid

import jwt
import pytest
from langgraph_sdk import get_client

from runtime_service.runtime.resolver import runtime_context_hash


pytestmark = pytest.mark.integration

SECRET = os.getenv(
    "R6_TEST_TOKEN_SECRET",
    os.getenv(
        "PLATFORM_RUNTIME_DELEGATION_SECRET",
        "r2-workflow-integration-secret-with-at-least-32-bytes",
    ),
)
ISSUER = os.getenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-workflow-integration")
AUDIENCE = os.getenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")


def _token() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "type": "runtime_delegation",
            "sub": "workflow-integration-user",
            "tenant_id": "workflow-integration-tenant",
            "project_id": "workflow-integration-project",
            "role": "developer",
            "permissions": [],
            "policy_version": "workflow-integration-policy-v1",
            "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
            "allowed_tool_names": [],
            "iat": now,
            "exp": now + 60,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "scope": {
                "tenant_id": "workflow-integration-tenant",
                "project_id": "workflow-integration-project",
            },
            "context_hash": runtime_context_hash(None),
        },
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def durable_demo_url() -> str:
    value = os.getenv("RUNTIME_DURABLE_DEMO_URL")
    if not value:
        pytest.skip(
            "RUNTIME_DURABLE_DEMO_URL must point to GraphHarbor with workflow_demo registered"
        )
    return value.rstrip("/")


def test_workflow_demo_loads_and_executes_through_graphharbor(
    durable_demo_url: str,
) -> None:
    asyncio.run(_run(durable_demo_url))


async def _run(base_url: str) -> None:
    client = get_client(
        url=base_url,
        headers={"Authorization": f"Bearer {_token()}"},
    )
    thread_id = str(uuid.uuid4())
    try:
        assistants = await client.assistants.search(limit=100)
        assert any(item.get("graph_id") == "workflow_demo" for item in assistants)
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        parts = []
        async for part in client.runs.stream(
            thread_id,
            "workflow_demo",
            input={"message": "hello", "route": "approve"},
            stream_mode=["values", "updates"],
            on_disconnect="cancel",
        ):
            parts.append(part.data)
        assert "workflow approved: hello" in str(parts)
    finally:
        await client.aclose()
