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
        "r1-integration-secret-with-at-least-32-bytes",
    ),
)
ISSUER = os.getenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-integration")
AUDIENCE = os.getenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")


def _token(context: object | None = None) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "type": "runtime_delegation",
            "sub": "integration-user",
            "tenant_id": "integration-tenant",
            "project_id": "integration-project",
            "role": "developer",
            "permissions": ["runtime.tool.read"],
            "policy_version": "integration-policy-v1",
            "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
            "allowed_tool_names": ["read_reference"],
            "iat": now,
            "exp": now + 60,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "scope": {
                "tenant_id": "integration-tenant",
                "project_id": "integration-project",
            },
            "context_hash": runtime_context_hash(context),
        },
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def durable_url() -> str:
    value = os.getenv("RUNTIME_DURABLE_URL")
    if not value:
        pytest.skip("RUNTIME_DURABLE_URL must point to a running GraphHarbor service")
    return value.rstrip("/")


def test_graphharbor_auth_rejects_anonymous_and_accepts_delegation(
    durable_url: str,
) -> None:
    asyncio.run(_test_auth(durable_url))


async def _test_auth(base_url: str) -> None:
    anonymous = get_client(url=base_url)
    try:
        with pytest.raises(Exception):
            await anonymous.threads.search()
    finally:
        await anonymous.aclose()

    invalid = get_client(url=base_url, headers={"Authorization": "Bearer invalid"})
    try:
        with pytest.raises(Exception):
            await invalid.threads.search()
    finally:
        await invalid.aclose()

    client = get_client(
        url=base_url,
        headers={"Authorization": f"Bearer {_token()}"},
    )
    try:
        thread = await client.threads.create(thread_id=str(uuid.uuid4()), if_exists="raise")
        assert thread
    finally:
        await client.aclose()


def test_graphharbor_runtime_context_unknown_field_fails_closed(
    durable_url: str,
) -> None:
    asyncio.run(_test_unknown_context(durable_url))


def test_graphharbor_invalid_delegation_has_no_persistence(
    durable_url: str,
) -> None:
    """Auth failures must happen before GraphHarbor creates a Thread or Run."""
    asyncio.run(_test_invalid_delegation_no_side_effect(durable_url))


async def _test_invalid_delegation_no_side_effect(base_url: str) -> None:
    thread_id = str(uuid.uuid4())
    scope_claims = jwt.decode(_token(), SECRET, algorithms=["HS256"], options={"verify_signature": False})
    scope_claims["scope"] = {
        "tenant_id": "wrong-tenant",
        "project_id": "integration-project",
    }
    invalid_token = jwt.encode(scope_claims, SECRET, algorithm="HS256")
    client = get_client(url=base_url, headers={"Authorization": f"Bearer {invalid_token}"})
    try:
        with pytest.raises(Exception):
            await client.threads.create(thread_id=thread_id, if_exists="raise")
    finally:
        await client.aclose()

    valid = get_client(url=base_url, headers={"Authorization": f"Bearer {_token()}"})
    try:
        with pytest.raises(Exception):
            await valid.threads.get(thread_id)
    finally:
        await valid.aclose()


async def _test_unknown_context(base_url: str) -> None:
    context = {"future": True}
    client = get_client(
        url=base_url,
        headers={"Authorization": f"Bearer {_token()}"},
    )
    thread_id = str(uuid.uuid4())
    try:
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        run = await client.runs.create(
            thread_id,
            "reference_agent",
            input={"messages": [{"role": "user", "content": "invalid context"}]},
            context=context,
            stream_mode=["values"],
            durability="sync",
        )
        run_id = run.get("run_id") if isinstance(run, dict) else run.run_id
        await client.runs.join(thread_id, run_id)
        observed = await client.runs.get(thread_id, run_id)
        status = observed.get("status") if isinstance(observed, dict) else observed.status
        assert status in {"error", "failed"}
    finally:
        await client.aclose()


def test_graphharbor_agent_server_executes_real_model_when_enabled(
    durable_url: str,
) -> None:
    asyncio.run(_run_real_model(durable_url))


async def _run_real_model(base_url: str) -> None:
    context = {"temperature": 0}
    client = get_client(
        url=base_url,
        headers={"Authorization": f"Bearer {_token(context)}"},
    )
    thread_id = str(uuid.uuid4())
    try:
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        parts = []
        async for part in client.runs.stream(
            thread_id,
            "reference_agent",
            input={"messages": [{"role": "user", "content": "Reply with exactly: e2e-ok"}]},
            context=context,
            stream_mode=["values", "updates"],
            on_disconnect="cancel",
        ):
            parts.append(part)
        assert "e2e-ok" in " ".join(str(part.data) for part in parts).lower()
    finally:
        await client.aclose()
