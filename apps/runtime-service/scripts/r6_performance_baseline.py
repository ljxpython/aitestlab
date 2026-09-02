"""Measure Runtime API latency without applying an unapproved SLO."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from typing import Any
from urllib.request import Request, urlopen

from langgraph_sdk import get_client
from r6_durable_smoke import _local_token


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return round(ordered[index], 2)


def _queue_depth(url: str, secret: str) -> int | None:
    request = Request(
        url.rstrip("/") + "/metrics",
        headers={"Authorization": f"Bearer {_local_token(secret=secret)}"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            for line in response.read().decode("utf-8").splitlines():
                if line.startswith("graphharbor_queue_depth "):
                    return int(float(line.rsplit(" ", 1)[1]))
    except (OSError, ValueError):
        return None
    return None


async def _one_run(url: str, assistant_id: str, secret: str) -> dict[str, Any]:
    client = get_client(
        url=url,
        headers={"Authorization": f"Bearer {_local_token(secret=secret)}"},
    )
    thread_id = str(uuid.uuid4())
    started = time.perf_counter()
    first_event_ms: float | None = None
    try:
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        stream = client.runs.stream(
            thread_id,
            assistant_id,
            input={"message": "R6 performance baseline"},
            stream_mode=["values", "updates"],
            stream_resumable=True,
            on_disconnect="continue",
            durability="sync",
        )
        event_count = 0
        run_id: str | None = None
        async for part in stream:
            event_count += 1
            if part.event == "metadata" and isinstance(part.data, dict):
                run_id = str(part.data.get("run_id") or "") or run_id
            if first_event_ms is None:
                first_event_ms = (time.perf_counter() - started) * 1000
        completed_ms = (time.perf_counter() - started) * 1000
        if run_id is None:
            raise AssertionError("stream returned no run metadata")
        run = await client.runs.get(thread_id, run_id)
        checkpoint_started = time.perf_counter()
        await client.threads.get_state(thread_id)
        checkpoint_ms = (time.perf_counter() - checkpoint_started) * 1000
        status = run.get("status", "") if isinstance(run, dict) else run.status
        return {
            "status": status,
            "event_count": event_count,
            "first_event_ms": first_event_ms,
            "completion_ms": round(completed_ms, 2),
            "checkpoint_read_ms": round(checkpoint_ms, 2),
        }
    finally:
        await client.aclose()


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    secret = os.getenv(
        "R6_TEST_TOKEN_SECRET",
        os.getenv(
            "PLATFORM_RUNTIME_DELEGATION_SECRET",
            "r6-local-only-secret-at-least-32-bytes",
        ),
    )
    queue_depth_before = await asyncio.to_thread(_queue_depth, args.url, secret)
    samples = await asyncio.gather(
        *(_one_run(args.url, args.assistant_id, secret) for _ in range(args.runs))
    )
    queue_depth_after = await asyncio.to_thread(_queue_depth, args.url, secret)
    if any(sample["status"] != "success" for sample in samples):
        raise AssertionError(f"performance runs did not all succeed: {samples}")

    def values(name: str) -> list[float]:
        return [float(sample[name]) for sample in samples if sample[name] is not None]

    return {
        "status": "passed",
        "slo_decision": "baseline_only",
        "url": args.url,
        "assistant_id": args.assistant_id,
        "concurrency": args.runs,
        "runs": samples,
        "latency_ms": {
            name: {
                "p50": _percentile(values(name), 0.50),
                "p95": _percentile(values(name), 0.95),
                "min": round(min(values(name)), 2) if values(name) else None,
                "max": round(max(values(name)), 2) if values(name) else None,
            }
            for name in ("first_event_ms", "completion_ms", "checkpoint_read_ms")
        },
        "queue_lag_ms": None,
        "queue_depth_before": queue_depth_before,
        "queue_depth_after": queue_depth_after,
        "unobserved": ["queue_lag_ms", "database_watermark", "redis_watermark"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("RUNTIME_DURABLE_URL", "http://127.0.0.1:18123"))
    parser.add_argument(
        "--assistant-id",
        default=os.getenv("RUNTIME_DURABLE_DISCONNECT_ASSISTANT_ID", "disconnect_demo"),
    )
    parser.add_argument("--runs", type=int, default=4)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    try:
        print(json.dumps(asyncio.run(_run(args)), ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001 - baseline must emit structured failure.
        print(json.dumps({"status": "failed", "failure": f"{type(exc).__name__}: {exc}"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
