from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import jwt
import pytest
from langgraph_sdk import get_client

from runtime_service.runtime.resolver import runtime_context_hash


pytestmark = pytest.mark.integration

APP_ROOT = Path(__file__).resolve().parents[2]
SECRET = "r1-integration-secret-with-at-least-32-bytes"
ISSUER = "runtime-integration"
AUDIENCE = "runtime-service"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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


def _request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: dict[str, object] | None = None,
) -> tuple[int, dict[str, object] | str]:
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=None if body is None else json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        return exc.code, json.loads(raw) if raw else ""


@pytest.fixture
def local_agent_server():
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
            "PLATFORM_RUNTIME_DELEGATION_ISSUER": ISSUER,
            "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": AUDIENCE,
            "LANGCHAIN_TRACING_V2": "false",
        }
    )
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "langgraph",
            "dev",
            "--no-browser",
            "--config",
            "./langgraph.json",
            "--port",
            str(port),
        ],
        cwd=APP_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Agent Server exited with status {process.returncode}")
        try:
            status, _ = _request(base_url, "/info")
            if status == 200:
                break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.25)
    else:
        process.terminate()
        raise AssertionError("Agent Server did not become ready")

    yield base_url

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_agent_server_auth_rejects_anonymous_and_accepts_delegation(
    local_agent_server: str,
) -> None:
    status, _ = _request(local_agent_server, "/threads")
    assert status == 401

    status, _ = _request(local_agent_server, "/threads", token="invalid")
    assert status == 401

    status, payload = _request(
        local_agent_server,
        "/threads",
        method="POST",
        token=_token(),
        body={"thread_id": str(uuid.uuid4())},
    )
    assert status == 200
    assert isinstance(payload, dict)
    assert payload.get("thread_id")


def test_agent_server_auth_executes_real_model_when_enabled(
    local_agent_server: str,
) -> None:
    if os.getenv("RUNTIME_E2E") != "1":
        pytest.skip("set RUNTIME_E2E=1 to run real-model Agent Server execution")
    context = {"temperature": 0}
    asyncio.run(_run_real_model(local_agent_server, context))


async def _run_real_model(base_url: str, context: dict[str, object]) -> None:
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
            input={
                "messages": [
                    {"role": "user", "content": "Reply with exactly: e2e-ok"}
                ]
            },
            context=context,
            stream_mode=["values", "updates"],
            on_disconnect="cancel",
        ):
            parts.append(part)
        assert "e2e-ok" in " ".join(str(part.data) for part in parts).lower()
    finally:
        await client.aclose()
