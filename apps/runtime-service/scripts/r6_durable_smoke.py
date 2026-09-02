"""Run one real Agent Server Durable Run without Platform API."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from langgraph_sdk import get_client

from runtime_service.runtime.resolver import runtime_context_hash


def _local_token(
    *,
    secret: str | None = None,
    tenant_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    permissions: list[str] | None = None,
    allowed_tool_names: list[str] | None = None,
) -> str:
    now = datetime.now(UTC)
    tenant = tenant_id or os.getenv("R6_TEST_TENANT", "r6-smoke-tenant")
    project = project_id or os.getenv("R6_TEST_PROJECT", "r6-smoke-project")
    claims = {
        "type": "runtime_delegation",
        "sub": user_id or os.getenv("R6_TEST_USER", "r6-smoke-user"),
        "tenant_id": tenant,
        "project_id": project,
        "role": "developer",
        "permissions": permissions if permissions is not None else ["runtime.tool.read"],
        "policy_version": "r6-smoke-v1",
        "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
        "allowed_tool_names": (
            allowed_tool_names if allowed_tool_names is not None else ["read_reference"]
        ),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iss": os.getenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "platform-api"),
        "aud": os.getenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service"),
        "scope": {
            "tenant_id": tenant,
            "project_id": project,
        },
        "context_hash": runtime_context_hash(None),
    }
    signing_secret = secret or os.getenv(
        "R6_TEST_TOKEN_SECRET",
        os.getenv(
            "PLATFORM_RUNTIME_DELEGATION_SECRET",
            "r6-local-only-secret-at-least-32-bytes",
        ),
    )
    return jwt.encode(
        claims,
        signing_secret,
        algorithm="HS256",
    )


async def main() -> int:
    base_url = os.getenv("RUNTIME_DURABLE_URL", "http://127.0.0.1:8123")
    assistant_id = os.getenv("RUNTIME_DURABLE_ASSISTANT_ID", "reference_agent")
    thread_id = str(uuid.uuid4())
    client = get_client(
        url=base_url,
        headers={"Authorization": f"Bearer {_local_token()}"},
    )
    try:
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        events = []
        async for part in client.runs.stream(
            thread_id,
            assistant_id,
            input={"messages": [{"role": "user", "content": "R6 durable smoke"}]},
            stream_mode=["values", "updates"],
            stream_resumable=True,
            on_disconnect="continue",
            durability="sync",
        ):
            events.append(part)

        metadata = next((part.data for part in events if part.event == "metadata"), {})
        run_id = metadata.get("run_id")
        if not run_id:
            raise RuntimeError("Agent Server stream did not return run_id metadata")

        run = await client.runs.get(thread_id, run_id)
        state = await client.threads.get_state(thread_id)
        status = run.get("status") if isinstance(run, dict) else run.status
        checkpoint = state.get("checkpoint") if isinstance(state, dict) else state.checkpoint
        checkpoint_id = (
            checkpoint.get("checkpoint_id") or checkpoint.get("id")
            if isinstance(checkpoint, dict)
            else checkpoint
        )
        if not checkpoint_id:
            raise RuntimeError("Agent Server state did not return a persisted checkpoint")
        print(
            {
                "thread_id": thread_id,
                "run_id": run_id,
                "run_status": status,
                "checkpoint_id": checkpoint_id,
                "event_count": len(events),
            }
        )
        return 0
    finally:
        await client.aclose()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print(f"R6 durable smoke failed: {exc}", file=sys.stderr)
        raise
