"""Validate R6 Thread Workspace recovery against the published GraphHarbor package."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import tempfile
import time
import uuid
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import httpx
from r6_durable_smoke import _local_token
from r6_worker_fault_injection import (
    DEFAULT_CONFIG,
    _database_evidence,
    _graphharbor_command,
    _start,
    _stop,
    _wait_for,
)


async def _create_run(
    client: httpx.AsyncClient,
    thread_id: str,
    assistant_id: str,
    input_value: dict[str, str],
    timeout: float,
) -> tuple[str, dict[str, Any]]:
    response = await client.post(
        f"/threads/{thread_id}/runs",
        json={"assistant_id": assistant_id, "input": input_value, "durability": "sync"},
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


def _thread_payload(thread_id: str) -> dict[str, object]:
    return {
        "thread_id": thread_id,
        "metadata": {
            "runtime_resource_bindings": {
                "schema": "runtime-resource-bindings/v1",
                "workspace": {
                    "provider": "graphharbor_workspace",
                    "resource_id": thread_id,
                    "tenant_id": "r6-smoke-tenant",
                    "project_id": "r6-smoke-project",
                    "thread_id": thread_id,
                },
            }
        },
    }


async def _run(args: argparse.Namespace, workspace_root: Path) -> dict[str, Any]:
    prefix = f"graphharbor:r6:workspace:{int(time.time())}"
    secret = os.environ.get("PLATFORM_RUNTIME_DELEGATION_SECRET") or (
        "r6-local-only-secret-at-least-32-bytes"
    )
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
            "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET"
        )
        or "r6-local-runtime-context-secret-at-least-32-bytes",
        "GRAPHHARBOR_WORKSPACE_ROOT": str(workspace_root),
    }
    command = _graphharbor_command()
    api = worker = None
    base_url = f"http://127.0.0.1:{args.port}"
    headers = {"Authorization": f"Bearer {_local_token(secret=secret)}"}
    try:
        api = await _start(
            command
            + [
                "serve",
                "--host",
                "0.0.0.0",
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
            await _wait_for(
                client,
                "/ready",
                lambda value: value.get("ready") is True,
                120,
                process=api,
            )
            assistant_response = await client.post(
                "/assistants",
                json={"graph_id": "workspace_demo", "name": "r6-workspace"},
            )
            assistant_response.raise_for_status()
            assistant_id = str(assistant_response.json()["assistant_id"])
            first_thread = str(uuid.uuid4())
            first_thread_response = await client.post(
                "/threads", json=_thread_payload(first_thread)
            )
            first_thread_response.raise_for_status()

            worker = await _start(
                command
                + ["worker", "--config", str(args.config), "--n-jobs-per-worker", "1"],
                env,
            )
            write_run_id, write_run = await _create_run(
                client,
                first_thread,
                assistant_id,
                {"operation": "write", "path": "/r6.txt", "content": "workspace-ok"},
                args.timeout,
            )
            if write_run["status"] != "success":
                raise AssertionError(f"Workspace write failed: {write_run}")

            await _stop(worker, signal.SIGTERM)
            worker = await _start(
                command
                + ["worker", "--config", str(args.config), "--n-jobs-per-worker", "1"],
                env,
            )
            read_run_id, read_run = await _create_run(
                client,
                first_thread,
                assistant_id,
                {"operation": "read", "path": "/r6.txt"},
                args.timeout,
            )
            state_response = await client.get(f"/threads/{first_thread}/state")
            state_response.raise_for_status()
            observed = (state_response.json().get("values") or {}).get("observed")
            if read_run["status"] != "success" or observed != "workspace-ok":
                raise AssertionError(
                    f"Replacement Worker did not reopen Workspace: {read_run}"
                )

            await _stop(api, signal.SIGTERM)
            api = await _start(
                command
                + [
                    "serve",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(args.port),
                    "--config",
                    str(args.config),
                    "--n-jobs-per-worker",
                    "0",
                ],
                env,
            )
            await _wait_for(
                client,
                "/ready",
                lambda value: value.get("ready") is True,
                120,
                process=api,
            )
            state_after_api_restart = await client.get(
                f"/threads/{first_thread}/state"
            )
            state_after_api_restart.raise_for_status()
            observed_after_api_restart = (
                (state_after_api_restart.json().get("values") or {}).get("observed")
            )
            if observed_after_api_restart != "workspace-ok":
                raise AssertionError(
                    "API restart did not preserve the Thread Workspace state"
                )

            second_thread = str(uuid.uuid4())
            second_thread_response = await client.post(
                "/threads", json=_thread_payload(second_thread)
            )
            second_thread_response.raise_for_status()
            isolated_run_id, isolated_run = await _create_run(
                client,
                second_thread,
                assistant_id,
                {"operation": "read", "path": "/r6.txt"},
                args.timeout,
            )
            if isolated_run["status"] != "error":
                raise AssertionError(
                    f"Second Thread observed another Workspace: {isolated_run}"
                )

            other_headers = {
                "Authorization": f"Bearer {_local_token(secret=secret, tenant_id='r6-other-tenant', project_id='r6-other-project', user_id='r6-other-user')}"
            }
            tenant_response = await client.get(
                f"/threads/{first_thread}", headers=other_headers
            )
            if tenant_response.status_code != 404:
                raise AssertionError(
                    f"Cross-tenant Thread lookup was not hidden: {tenant_response.status_code}"
                )

            await _stop(worker, signal.SIGTERM)
            unavailable_root = workspace_root / ".unavailable"
            unavailable_root.write_text("not a directory", encoding="utf-8")
            unavailable_env = {
                **env,
                "GRAPHHARBOR_WORKSPACE_ROOT": str(unavailable_root),
            }
            worker = await _start(
                command
                + ["worker", "--config", str(args.config), "--n-jobs-per-worker", "1"],
                unavailable_env,
            )
            failed_run_id, failed_run = await _create_run(
                client,
                first_thread,
                assistant_id,
                {"operation": "read", "path": "/r6.txt"},
                args.timeout,
            )
            if failed_run["status"] != "error":
                raise AssertionError(
                    f"Unavailable Workspace did not fail closed: {failed_run}"
                )

        evidence = {
            "write": _database_evidence(args.database_uri, write_run_id),
            "reconnect": _database_evidence(args.database_uri, read_run_id),
            "thread_isolation": _database_evidence(args.database_uri, isolated_run_id),
            "recovery_failure": _database_evidence(args.database_uri, failed_run_id),
        }
        if any(item["terminal_event_total"] != 1 for item in evidence.values()):
            raise AssertionError(
                f"Workspace Run emitted duplicate terminal events: {evidence}"
            )
        return {
            "status": "passed",
            "same_thread_reopened": observed == "workspace-ok",
            "api_restart_reopened": observed_after_api_restart == "workspace-ok",
            "second_thread_status": isolated_run["status"],
            "cross_tenant_status": tenant_response.status_code,
            "unavailable_workspace_status": failed_run["status"],
            "database": evidence,
        }
    finally:
        await _stop(worker, signal.SIGTERM)
        await _stop(api, signal.SIGTERM)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-uri", default=os.environ.get("DATABASE_URI"))
    parser.add_argument("--redis-uri", default=os.environ.get("REDIS_URI"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--port", type=int, default=31328)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if not args.database_uri or not args.redis_uri:
        parser.error("DATABASE_URI and REDIS_URI are required")

    temporary = tempfile.TemporaryDirectory(prefix="r6-workspace-")
    context = (
        temporary
        if args.workspace_root is None
        else nullcontext(str(args.workspace_root))
    )
    try:
        with context as root_value:
            root = Path(root_value).resolve()
            root.mkdir(parents=True, exist_ok=True)
            result = asyncio.run(_run(args, root))
    except Exception as exc:  # noqa: BLE001 - CLI must return structured failure evidence.
        print(
            json.dumps({"status": "failed", "failure": f"{type(exc).__name__}: {exc}"})
        )
        return 1
    finally:
        if args.workspace_root is None:
            temporary.cleanup()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
