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
from collections.abc import Iterator

import jwt
import pytest
from langgraph_sdk import get_client

from runtime_service.runtime.resolver import runtime_context_hash


pytestmark = pytest.mark.integration

APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SECRET = "r2-workflow-integration-secret-with-at-least-32-bytes"
ISSUER = "runtime-workflow-integration"
AUDIENCE = "runtime-service"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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


def _request(base_url: str, path: str) -> tuple[int, dict[str, object] | str]:
    request = urllib.request.Request(f"{base_url}{path}")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        return exc.code, json.loads(raw) if raw else ""


@pytest.fixture
def local_demo_agent_server() -> Iterator[str]:
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
            "./langgraph.demo.json",
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
        raise AssertionError("Demo Agent Server did not become ready")

    yield base_url

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_workflow_demo_loads_and_executes_through_demo_agent_server(
    local_demo_agent_server: str,
) -> None:
    status, payload = _request(local_demo_agent_server, "/info")
    assert status == 200
    assert payload["langgraph_py_version"] == "1.2.11"

    async def run() -> list[object]:
        client = get_client(
            url=local_demo_agent_server,
            headers={"Authorization": f"Bearer {_token()}"},
        )
        thread_id = str(uuid.uuid4())
        parts: list[object] = []
        try:
            assistants = await client.assistants.search(limit=100)
            assert any(item.get("graph_id") == "workflow_demo" for item in assistants)
            await client.threads.create(thread_id=thread_id, if_exists="raise")
            async for part in client.runs.stream(
                thread_id,
                "workflow_demo",
                input={"message": "hello", "route": "approve"},
                stream_mode=["values", "updates"],
                on_disconnect="cancel",
            ):
                parts.append(part.data)
        finally:
            await client.aclose()
        return parts

    parts = asyncio.run(run())
    assert "workflow approved: hello" in json.dumps(parts)
