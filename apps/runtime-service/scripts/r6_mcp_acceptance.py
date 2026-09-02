"""Validate real Streamable HTTP MCP discovery and recovery across Workers."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from r6_durable_smoke import _local_token
from r6_worker_fault_injection import (
    DEFAULT_CONFIG,
    _database_evidence,
    _start,
    _stop,
    _wait_for,
)

ROOT = Path(__file__).resolve().parents[1]
MCP_SERVER = ROOT / "scripts" / "r6_mcp_server.py"


def _thread_payload(thread_id: str, resource_id: str) -> dict[str, object]:
    return {
        "thread_id": thread_id,
        "metadata": {
            "runtime_resource_bindings": {
                "schema": "runtime-resource-bindings/v1",
                "mcp": {
                    "provider": "mcp_http",
                    "resource_id": resource_id,
                    "tenant_id": "r6-mcp-tenant",
                    "project_id": "r6-mcp-project",
                    "thread_id": thread_id,
                },
            }
        },
    }


async def _run_case(
    client: httpx.AsyncClient,
    thread_id: str,
    assistant_id: str,
    topic: str,
    timeout: float,
) -> tuple[str, dict[str, Any]]:
    response = await client.post(
        f"/threads/{thread_id}/runs",
        json={
            "assistant_id": assistant_id,
            "input": {"topic": topic},
            "durability": "sync",
        },
    )
    response.raise_for_status()
    run_id = str(response.json()["run_id"])
    run = await _wait_for(
        client,
        f"/threads/{thread_id}/runs/{run_id}",
        lambda value: value.get("status") in {"success", "error", "interrupted"},
        timeout,
    )
    return run_id, run


async def _wait_for_mcp(url: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(url)
                if response.status_code not in {404, 502, 503}:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
    raise TimeoutError(f"timed out waiting for MCP provider: {url}")


def _contains(value: object, needle: str) -> bool:
    return needle in json.dumps(value, ensure_ascii=False, sort_keys=True)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    prefix = f"graphharbor:r6:mcp:{int(time.time())}"
    secret = os.environ.get(
        "PLATFORM_RUNTIME_DELEGATION_SECRET",
        "r6-local-only-secret-at-least-32-bytes",
    )
    mcp_url = f"http://127.0.0.1:{args.mcp_port}/mcp"
    env = {
        **os.environ,
        "DATABASE_URI": args.database_uri,
        "REDIS_URI": args.redis_uri,
        "GRAPHHARBOR_REDIS_PREFIX": prefix,
        "GRAPHHARBOR_ENV": "development",
        "LG_RUNTIME_PG_AUTO_MIGRATE": "false",
        "PLATFORM_RUNTIME_DELEGATION_SECRET": secret,
        "PLATFORM_RUNTIME_DELEGATION_ISSUER": os.environ.get(
            "PLATFORM_RUNTIME_DELEGATION_ISSUER", "platform-api"
        ),
        "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": os.environ.get(
            "PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service"
        ),
        "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": os.environ.get(
            "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET",
            "r6-local-runtime-context-secret-at-least-32-bytes",
        ),
        "RUNTIME_MCP_CONNECTIONS_JSON": json.dumps(
            {"mcp-provider": {"transport": "streamable_http", "url": mcp_url}}
        ),
        "R6_MCP_PORT": str(args.mcp_port),
    }
    command = [sys.executable, "-m", "langhost.cli"]
    mcp = api = worker = replacement = None
    base_url = f"http://127.0.0.1:{args.port}"
    headers = {
        "Authorization": f"Bearer {_local_token(secret=secret, tenant_id="r6-mcp-tenant", project_id="r6-mcp-project", permissions=["runtime.tool.read"], allowed_tool_names=["mcp_read"])}"
    }
    try:
        mcp = await _start([sys.executable, str(MCP_SERVER)], env)
        await _wait_for_mcp(mcp_url)
        api = await _start(
            command
            + [
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.port),
                "--config",
                str(args.config),
                "--n-jobs-per-worker",
                "0",
            ],
            env,
        )
        async with httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=10, trust_env=False
        ) as client:
            await _wait_for(client, "/ready", lambda value: value.get("ready") is True, 60)
            assistant_response = await client.post(
                "/assistants", json={"graph_id": "mcp_probe", "name": "r6-mcp-probe"}
            )
            assistant_response.raise_for_status()
            assistant_id = str(assistant_response.json()["assistant_id"])
            thread_id = str(uuid.uuid4())
            thread_response = await client.post(
                "/threads", json=_thread_payload(thread_id, "mcp-provider")
            )
            thread_response.raise_for_status()

            worker = await _start(
                command + ["worker", "--config", str(args.config), "--n-jobs-per-worker", "1"],
                env,
            )
            first_id, first = await _run_case(
                client, thread_id, assistant_id, "initial", args.timeout
            )
            if first.get("status") != "success":
                raise AssertionError(f"initial MCP call failed: {first}")
            state = await client.get(f"/threads/{thread_id}/state")
            state.raise_for_status()
            if (state.json().get("values") or {}).get("observed") != "initial: mcp-provider-ok":
                raise AssertionError(f"MCP tool result was not persisted: {state.json()}")

            await _stop(worker, signal.SIGTERM)
            worker = None
            replacement = await _start(
                command + ["worker", "--config", str(args.config), "--n-jobs-per-worker", "1"],
                env,
            )
            replacement_id, replacement_run = await _run_case(
                client, thread_id, assistant_id, "after-worker-replacement", args.timeout
            )
            if replacement_run.get("status") != "success":
                raise AssertionError(f"MCP Worker replacement failed: {replacement_run}")

            await _stop(mcp, signal.SIGTERM)
            mcp = await _start([sys.executable, str(MCP_SERVER)], env)
            await _wait_for_mcp(mcp_url)
            provider_restart_id, provider_restart_run = await _run_case(
                client, thread_id, assistant_id, "after-provider-restart", args.timeout
            )
            if provider_restart_run.get("status") != "success":
                raise AssertionError(
                    f"MCP provider restart recovery failed: {provider_restart_run}"
                )

            missing_thread = str(uuid.uuid4())
            missing_response = await client.post("/threads", json={"thread_id": missing_thread})
            missing_response.raise_for_status()
            missing_id, missing_run = await _run_case(
                client, missing_thread, assistant_id, "missing-binding", args.timeout
            )
            if missing_run.get("status") != "error":
                raise AssertionError(f"Missing MCP binding did not fail closed: {missing_run}")

            unavailable_thread = str(uuid.uuid4())
            unavailable_response = await client.post(
                "/threads",
                json=_thread_payload(unavailable_thread, "unavailable-provider"),
            )
            unavailable_response.raise_for_status()
            unavailable_id, unavailable_run = await _run_case(
                client, unavailable_thread, assistant_id, "unavailable-provider", args.timeout
            )
            if unavailable_run.get("status") != "error":
                raise AssertionError(
                    f"Unavailable MCP provider did not fail closed: {unavailable_run}"
                )

        evidence = {
            name: _database_evidence(args.database_uri, run_id)
            for name, run_id in {
                "initial": first_id,
                "worker_replacement": replacement_id,
                "provider_restart": provider_restart_id,
                "missing_binding": missing_id,
                "unavailable_provider": unavailable_id,
            }.items()
        }
        if any(item["terminal_event_total"] != 1 for item in evidence.values()):
            raise AssertionError(f"MCP acceptance emitted duplicate terminal events: {evidence}")
        for name in ("missing_binding", "unavailable_provider"):
            if evidence[name]["terminal_error"] != "runtime.mcp.recovery_failed":
                raise AssertionError(
                    f"{name} did not persist the stable MCP recovery error: {evidence[name]}"
                )
        return {
            "status": "passed",
            "discovery_and_call": first.get("status") == "success",
            "worker_replacement": replacement_run.get("status") == "success",
            "provider_restart": provider_restart_run.get("status") == "success",
            "missing_binding": missing_run.get("status"),
            "unavailable_provider": unavailable_run.get("status"),
            "database": evidence,
        }
    finally:
        await _stop(replacement, signal.SIGTERM)
        await _stop(worker, signal.SIGTERM)
        await _stop(mcp, signal.SIGTERM)
        await _stop(api, signal.SIGTERM)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-uri", default=os.environ.get("DATABASE_URI"))
    parser.add_argument("--redis-uri", default=os.environ.get("REDIS_URI"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--port", type=int, default=31329)
    parser.add_argument("--mcp-port", type=int, default=31330)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if not args.database_uri or not args.redis_uri:
        parser.error("DATABASE_URI and REDIS_URI are required")
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - CLI returns structured acceptance evidence.
        print(json.dumps({"status": "failed", "failure": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
