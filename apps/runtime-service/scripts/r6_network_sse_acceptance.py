"""Verify resumable SSE from an independent network namespace."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

import httpx
from langgraph_sdk import get_client
from r6_durable_smoke import _local_token


def _status(run: object) -> str:
    return (
        run.get("status", "") if isinstance(run, dict) else getattr(run, "status", "")
    )


def _field(value: object, name: str) -> Any:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


async def _parts(
    stream: AsyncIterator[Any], *, limit: int | None = None, timeout: float
) -> list[Any]:
    result: list[Any] = []
    iterator = stream.__aiter__()
    while limit is None or len(result) < limit:
        try:
            result.append(await asyncio.wait_for(anext(iterator), timeout=timeout))
        except StopAsyncIteration:
            break
    return result


async def _wait_for_api_ready(
    url: str, headers: dict[str, str], timeout: float
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    last_error = "unavailable"
    async with httpx.AsyncClient(
        base_url=url, headers=headers, timeout=10, trust_env=False
    ) as client:
        while asyncio.get_running_loop().time() < deadline:
            try:
                response = await client.get("/ready")
                payload = response.json()
                if (
                    response.status_code == 200
                    and isinstance(payload, dict)
                    and payload.get("ready") is True
                ):
                    return
                last_error = f"status={response.status_code}"
            except (httpx.HTTPError, ValueError) as exc:
                last_error = type(exc).__name__
            await asyncio.sleep(0.5)
    raise TimeoutError(f"API readiness did not pass: {last_error}")


async def _wait_for_run(
    client: Any, thread_id: str, run_id: str, timeout: float
) -> object:
    deadline = asyncio.get_running_loop().time() + timeout
    last_status = "unknown"
    while asyncio.get_running_loop().time() < deadline:
        run = await client.runs.get(thread_id, run_id)
        last_status = _status(run)
        if last_status in {"success", "error", "timeout", "interrupted", "cancelled"}:
            return run
        await asyncio.sleep(0.25)
    raise TimeoutError(f"Worker readiness probe did not finish: status={last_status}")


async def _worker_readiness_probe(client: Any, args: argparse.Namespace) -> None:
    assistant = await client.assistants.create(
        graph_id=args.worker_ready_assistant_id,
        name=f"r6-worker-ready-{uuid.uuid4()}",
        if_exists="raise",
    )
    assistant_value = _field(assistant, "assistant_id")
    if not assistant_value:
        raise RuntimeError("Worker readiness probe did not create an assistant")
    assistant_id = str(assistant_value)
    thread_id = str(uuid.uuid4())
    await client.threads.create(thread_id=thread_id, if_exists="raise")
    run = await client.runs.create(
        thread_id,
        assistant_id,
        input={"delay_seconds": 0},
        stream_mode=["values"],
        durability="sync",
    )
    run_value = _field(run, "run_id")
    if not run_value:
        raise RuntimeError("Worker readiness probe did not create a Run")
    run_id = str(run_value)
    result = await _wait_for_run(client, thread_id, run_id, args.worker_ready_timeout)
    if _status(result) != "success":
        raise AssertionError(
            f"Worker readiness probe ended with status={_status(result)}"
        )


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    parsed = urlparse(args.url)
    if parsed.hostname in {None, "127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            "--url must be reachable outside the caller loopback namespace"
        )

    secret = os.getenv(
        "R6_TEST_TOKEN_SECRET",
        os.getenv(
            "PLATFORM_RUNTIME_DELEGATION_SECRET",
            "r6-local-only-secret-at-least-32-bytes",
        ),
    )
    headers = {"Authorization": f"Bearer {_local_token(secret=secret)}"}
    first = get_client(url=args.url, headers=headers)
    second = get_client(url=args.url, headers=headers)
    thread_id = str(uuid.uuid4())
    try:
        await _wait_for_api_ready(args.url, headers, args.api_ready_timeout)
        await _worker_readiness_probe(second, args)
        await first.threads.create(thread_id=thread_id, if_exists="raise")
        stream = first.runs.stream(
            thread_id,
            args.assistant_id,
            input={"message": "network reconnect"},
            stream_mode=["values", "updates"],
            stream_resumable=True,
            on_disconnect="continue",
            durability="sync",
        )
        initial = await _parts(
            stream, limit=args.disconnect_after, timeout=args.timeout
        )
        initial_ids = [int(part.id) for part in initial if part.id]
        if not initial_ids:
            raise AssertionError("first client received no SSE event cursor")
        metadata = next(
            (part.data for part in initial if part.event == "metadata"), None
        )
        if not isinstance(metadata, dict) or not metadata.get("run_id"):
            raise AssertionError("first client received no run metadata")
        run_id = str(metadata["run_id"])
        await first.aclose()

        resumed = await _parts(
            second.runs.join_stream(
                thread_id,
                run_id,
                last_event_id=str(initial_ids[-1]),
            ),
            timeout=args.timeout,
        )
        resumed_ids = [int(part.id) for part in resumed if part.id]
        if resumed_ids != sorted(set(resumed_ids)):
            raise AssertionError(
                f"reconnect returned duplicate/out-of-order ids: {resumed_ids}"
            )
        if any(event_id <= initial_ids[-1] for event_id in resumed_ids):
            raise AssertionError(
                f"reconnect replayed acknowledged cursor {initial_ids[-1]}: {resumed_ids}"
            )
        run = await second.runs.get(thread_id, run_id)
        if _status(run) != "success":
            raise AssertionError(
                f"Run did not complete after reconnect: {_status(run)}"
            )
        if not resumed_ids:
            raise AssertionError(
                "reconnect returned no events after acknowledged cursor"
            )
        return {
            "status": "passed",
            "network_namespace": "independent-docker-bridge",
            "api_readiness": "passed",
            "worker_readiness": "passed",
            "initial_cursor": initial_ids[-1],
            "resumed_event_count": len(resumed_ids),
            "run_status": _status(run),
        }
    finally:
        await first.aclose()
        await second.aclose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default=os.getenv("RUNTIME_DURABLE_URL", "http://host.docker.internal:18123"),
    )
    parser.add_argument(
        "--assistant-id",
        default=os.getenv("RUNTIME_DURABLE_DISCONNECT_ASSISTANT_ID", "disconnect_demo"),
    )
    parser.add_argument(
        "--worker-ready-assistant-id",
        default=os.getenv("RUNTIME_DURABLE_WORKER_READY_ASSISTANT_ID", "recovery_demo"),
    )
    parser.add_argument(
        "--api-ready-timeout",
        type=float,
        default=float(os.getenv("R6_SSE_API_READY_TIMEOUT", "120")),
    )
    parser.add_argument(
        "--worker-ready-timeout",
        type=float,
        default=float(os.getenv("R6_SSE_WORKER_READY_TIMEOUT", "120")),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("R6_SSE_STREAM_TIMEOUT", "120")),
    )
    parser.add_argument("--disconnect-after", type=int, default=2)
    args = parser.parse_args()
    if (
        args.disconnect_after < 1
        or args.api_ready_timeout <= 0
        or args.worker_ready_timeout <= 0
    ):
        parser.error(
            "disconnect-after must be positive and readiness timeouts must be positive"
        )
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - acceptance must emit structured failure.
        print(
            json.dumps({"status": "failed", "failure": f"{type(exc).__name__}: {exc}"})
        )
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
