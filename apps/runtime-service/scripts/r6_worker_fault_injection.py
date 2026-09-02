"""Run Runtime R6 Worker takeover against the published GraphHarbor package."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
from langgraph_runtime_pg.database import to_psycopg_uri
from r6_durable_smoke import _local_token

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "langgraph.r6.json"


def _graphharbor_command() -> list[str]:
    executable = shutil.which("graphharbor")
    return [executable] if executable else [sys.executable, "-m", "langhost.cli"]


async def _start(command: list[str], env: dict[str, str]) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        *command,
        cwd=ROOT,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )


async def _stop(process: asyncio.subprocess.Process | None, sig: signal.Signals) -> None:
    if process is None or process.returncode is not None:
        return
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=15)
    except TimeoutError:
        os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


async def _wait_for(
    client: httpx.AsyncClient,
    path: str,
    predicate,
    timeout: float,
    process: asyncio.subprocess.Process | None = None,
) -> dict:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        if process is not None and process.returncode is not None:
            output = b""
            if process.stderr is not None:
                output = await process.stderr.read()
            detail = output.decode(errors="replace").strip()[-4000:]
            raise RuntimeError(
                f"server process exited with code {process.returncode}: {detail}"
            )
        try:
            response = await client.get(path)
            response.raise_for_status()
            last = response.json()
            if predicate(last):
                return last
        except httpx.HTTPError as exc:
            last = {"error": f"{type(exc).__name__}: {exc}"}
        await asyncio.sleep(0.5)
    raise TimeoutError(f"timed out waiting for {path}: {last}")


def _database_evidence(database_uri: str, run_id: str) -> dict[str, Any]:
    with psycopg.connect(to_psycopg_uri(database_uri)) as connection:
        run = connection.execute(
            "SELECT status, retry_count FROM runs WHERE run_id = %s", (run_id,)
        ).fetchone()
        events = connection.execute(
            """
            SELECT COUNT(*), COUNT(*) FILTER (WHERE terminal),
                   COUNT(*) FILTER (WHERE payload->>'reason' = 'shutdown_requeue')
            FROM runtime_events WHERE run_id = %s
            """,
            (run_id,),
        ).fetchone()
        terminal_error = connection.execute(
            """
            SELECT payload->'error'->>'message'
            FROM runtime_events
            WHERE run_id = %s AND terminal
            ORDER BY sequence DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
    if run is None or events is None:
        raise AssertionError(f"run {run_id} disappeared during fault injection")
    return {
        "status": run[0],
        "retry_count": run[1],
        "event_total": events[0],
        "terminal_event_total": events[1],
        "shutdown_requeue_total": events[2],
        "terminal_error": terminal_error[0] if terminal_error else None,
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    prefix = f"graphharbor:r6:worker:{args.worker_signal.lower()}:{int(time.time())}"
    env = {
        **os.environ,
        "DATABASE_URI": args.database_uri,
        "REDIS_URI": args.redis_uri,
        "GRAPHHARBOR_REDIS_PREFIX": prefix,
        "GRAPHHARBOR_ENV": "development",
        "LG_RUNTIME_PG_AUTO_MIGRATE": "false",
        "GRAPHHARBOR_REAPER_INTERVAL_SECONDS": "0.5",
        "GRAPHHARBOR_LEASE_SECONDS": str(args.lease_seconds),
        "PLATFORM_RUNTIME_DELEGATION_SECRET": os.environ.get(
            "PLATFORM_RUNTIME_DELEGATION_SECRET",
            "r6-local-only-secret-at-least-32-bytes",
        ),
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
    }
    command = _graphharbor_command()
    api = worker = replacement = None
    base_url = f"http://127.0.0.1:{args.port}"
    headers = {
        "Authorization": f"Bearer {_local_token(secret=env['PLATFORM_RUNTIME_DELEGATION_SECRET'])}"
    }
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
                60,
                process=api,
            )

            assistant_response = await client.post(
                "/assistants", json={"graph_id": "recovery_demo", "name": "r6-recovery"}
            )
            assistant_response.raise_for_status()
            thread_response = await client.post("/threads", json={})
            thread_response.raise_for_status()
            assistant = assistant_response.json()
            thread = thread_response.json()
            run_response = await client.post(
                f"/threads/{thread['thread_id']}/runs",
                json={
                    "assistant_id": assistant["assistant_id"],
                    "input": {"delay_seconds": args.run_delay},
                    "durability": "sync",
                },
            )
            run_response.raise_for_status()
            run_id = str(run_response.json()["run_id"])

            worker = await _start(
                command
                + ["worker", "--config", str(args.config), "--n-jobs-per-worker", "1"],
                env,
            )
            await _wait_for(
                client,
                f"/threads/{thread['thread_id']}/runs/{run_id}",
                lambda value: value.get("status") == "running",
                30,
            )
            await _wait_for(
                client,
                f"/threads/{thread['thread_id']}/state",
                lambda value: (value.get("values") or {}).get("marker") == "checkpointed",
                30,
            )

            await _stop(worker, getattr(signal, args.worker_signal))
            worker = None
            replacement = await _start(
                command
                + ["worker", "--config", str(args.config), "--n-jobs-per-worker", "1"],
                env,
            )
            final = await _wait_for(
                client,
                f"/threads/{thread['thread_id']}/runs/{run_id}",
                lambda value: value.get("status") in {"success", "error", "interrupted"},
                args.timeout,
            )
            state_response = await client.get(f"/threads/{thread['thread_id']}/state")
            state_response.raise_for_status()
            state = state_response.json().get("values")

        database = _database_evidence(args.database_uri, run_id)
        expected_state = {
            "delay_seconds": args.run_delay,
            "marker": "checkpointed",
            "marker_attempts": 1,
            "completed": True,
        }
        if final["status"] != "success" or database["status"] != "success":
            raise AssertionError(f"replacement Worker ended Run incorrectly: {final}, {database}")
        if state != expected_state:
            raise AssertionError(f"Run did not resume from the persisted checkpoint: {state!r}")
        if database["terminal_event_total"] != 1:
            raise AssertionError(f"expected exactly one terminal event: {database}")
        if args.worker_signal == "SIGTERM" and database["shutdown_requeue_total"] < 1:
            raise AssertionError(f"missing graceful shutdown requeue: {database}")
        return {
            "status": "passed",
            "worker_signal": args.worker_signal,
            "run_id": run_id,
            "thread_id": thread["thread_id"],
            "state": state,
            "database": database,
        }
    finally:
        await _stop(replacement, signal.SIGTERM)
        await _stop(worker, signal.SIGTERM)
        await _stop(api, signal.SIGTERM)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-uri", default=os.environ.get("DATABASE_URI"))
    parser.add_argument("--redis-uri", default=os.environ.get("REDIS_URI"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--port", type=int, default=31327)
    parser.add_argument("--lease-seconds", type=int, default=5)
    parser.add_argument("--run-delay", type=float, default=30)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--worker-signal", choices=("SIGTERM", "SIGKILL"), required=True)
    args = parser.parse_args()
    if not args.database_uri or not args.redis_uri:
        parser.error("DATABASE_URI and REDIS_URI are required")
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - CLI returns structured failure evidence.
        print(json.dumps({"status": "failed", "failure": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
