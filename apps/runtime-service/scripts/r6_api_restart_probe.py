"""Verify that GraphHarbor can replace an API process on the same port."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

import httpx

from r6_worker_fault_injection import (
    DEFAULT_CONFIG,
    _graphharbor_command,
    _start,
    _stop,
    _wait_for,
)


async def _run(args: argparse.Namespace) -> dict[str, object]:
    if not args.database_uri or not args.redis_uri:
        raise ValueError("DATABASE_URI and REDIS_URI are required")

    env = {
        **os.environ,
        "DATABASE_URI": args.database_uri,
        "REDIS_URI": args.redis_uri,
        "GRAPHHARBOR_ENV": "development",
        "LG_RUNTIME_PG_AUTO_MIGRATE": "false",
        "N_JOBS_PER_WORKER": "0",
    }
    command = _graphharbor_command()
    serve = [
        "serve",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--config",
        str(args.config),
        "--n-jobs-per-worker",
        "0",
    ]
    base_url = f"http://127.0.0.1:{args.port}"
    first = second = None
    try:
        first = await _start(command + serve, env)
        async with httpx.AsyncClient(base_url=base_url, timeout=5, trust_env=False) as client:
            await _wait_for(client, "/ready", lambda value: value.get("ready") is True, args.timeout, first)
            await _stop(first, signal.SIGTERM)
            if first.returncode is None:
                raise AssertionError("first API process did not exit after SIGTERM")

            second = await _start(command + serve, env)
            await _wait_for(
                client,
                "/ready",
                lambda value: value.get("ready") is True,
                args.timeout,
                second,
            )
        return {
            "status": "passed",
            "port": args.port,
            "first_exit_code": first.returncode,
            "second_exit_code": second.returncode,
        }
    finally:
        await _stop(second, signal.SIGTERM)
        await _stop(first, signal.SIGTERM)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-uri", default=os.environ.get("DATABASE_URI"))
    parser.add_argument("--redis-uri", default=os.environ.get("REDIS_URI"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=31329)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - emit structured probe failure.
        print(json.dumps({"status": "failed", "failure": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
