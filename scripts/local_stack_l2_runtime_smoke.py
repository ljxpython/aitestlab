#!/usr/bin/env python3
"""Bounded local L2 smoke for the Platform -> GraphHarbor runtime chain."""

from __future__ import annotations

import json
import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from uuid import uuid4


BASE_URL = "http://127.0.0.1:2142"
PROMPT = "Reply exactly: local-l2-ok"


def request_json(
    path: str,
    *,
    token: str | None = None,
    project_id: str | None = None,
    idempotency_key: str | None = None,
    payload: dict[str, Any] | None = None,
    method: str | None = None,
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if project_id:
        headers["X-Project-Id"] = project_id
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method or ("POST" if payload is not None else "GET"),
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        error = body.get("error")
        if isinstance(error, dict):
            body = {**body, **error}
        return exc.code, {
            key: body.get(key)
            for key in ("code", "error", "detail", "message")
            if key in body and isinstance(body.get(key), (str, int, float, bool))
        }


def stream_shape(
    path: str,
    *,
    token: str,
    project_id: str,
    payload: dict[str, Any] | None = None,
    max_seconds: float = 45,
) -> dict[str, Any]:
    headers = {"Accept": "text/event-stream", "Authorization": f"Bearer {token}", "X-Project-Id": project_id}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    started = time.monotonic()
    frames: list[dict[str, Any]] = []
    current = {"id": False, "event": False, "data": False}
    current_id: str | None = None
    try:
        with urllib.request.urlopen(request, timeout=max_seconds + 5) as response:
            while time.monotonic() - started < max_seconds:
                line = response.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    if any(current.values()):
                        frames.append({**current, "id_value": current_id})
                        if current["id"]:
                            break
                        current = {"id": False, "event": False, "data": False}
                        current_id = None
                    continue
                for key in current:
                    if line.startswith(f"{key}:"):
                        current[key] = True
                        if key == "id":
                            current_id = line.partition(":")[2].strip()
                        break
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "frames": frames, "has_cursor": False}
    return {
        "http_status": 200,
        "frames": frames,
        "has_cursor": any(frame["id"] for frame in frames),
        "cursor": next((frame.get("id_value") for frame in reversed(frames) if frame.get("id_value")), None),
    }


def run_id(response: dict[str, Any]) -> str:
    value = response.get("run_id") or response.get("id")
    if not isinstance(value, str) or not value:
        raise RuntimeError("run response did not include a run_id")
    return value


def restart_recovery_check(token: str, project_id: str, marker: str) -> dict[str, Any]:
    thread_id = create_thread(token, project_id, f"{marker}-restart")
    status, created = request_json(
        f"/api/langgraph/threads/{thread_id}/runs",
        token=token,
        project_id=project_id,
        payload={
            "assistant_id": "reference_agent",
            "input": {"messages": [{"role": "user", "content": PROMPT}]},
            "after_seconds": 30,
            "stream_resumable": True,
        },
    )
    run = run_id(created) if status in {200, 201} else ""
    if not run:
        return {"create_status": status, "thread_status": 0, "run_status": 0, "stream": {}}
    try:
        for service in ("runtime-api", "runtime-worker"):
            subprocess.run(
                ["bash", "scripts/local-stack.sh", "restart-one", service],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except subprocess.CalledProcessError as exc:
        return {"create_status": status, "restart_error_exit_code": exc.returncode, "thread_status": 0, "run_status": 0, "stream": {}}
    thread_status, _ = request_json(
        f"/api/langgraph/threads/{thread_id}",
        token=token,
        project_id=project_id,
    )
    state_status, _ = request_json(
        f"/api/langgraph/threads/{thread_id}/state",
        token=token,
        project_id=project_id,
    )
    history_status, _ = request_json(
        f"/api/langgraph/threads/{thread_id}/history",
        token=token,
        project_id=project_id,
        payload={"limit": 10},
    )
    run_status, snapshot = request_json(
        f"/api/langgraph/threads/{thread_id}/runs/{run}",
        token=token,
        project_id=project_id,
    )
    stream = stream_shape(
        f"/api/langgraph/threads/{thread_id}/runs/{run}/stream?stream_mode=values",
        token=token,
        project_id=project_id,
        max_seconds=10,
    )
    event_stream = stream_shape(
        f"/api/langgraph/threads/{thread_id}/stream/events",
        token=token,
        project_id=project_id,
        payload={"channels": ["messages", "values", "updates", "lifecycle"], "since": 0},
        max_seconds=10,
    )
    cursor = event_stream.get("cursor")
    since = int(cursor) if isinstance(cursor, str) and cursor.isdigit() else cursor
    replay = (
        stream_shape(
            f"/api/langgraph/threads/{thread_id}/stream/events",
            token=token,
            project_id=project_id,
            payload={"channels": ["messages", "values", "updates", "lifecycle"], "since": since},
            max_seconds=10,
        )
        if cursor is not None
        else {"http_status": 0, "frames": [], "has_cursor": False, "cursor": None}
    )
    replay_cursor = replay.get("cursor")
    replay_cursor_advances = False
    if isinstance(since, int) and isinstance(replay_cursor, str) and replay_cursor.isdigit():
        replay_cursor_advances = int(replay_cursor) > since
    request_json(
        f"/api/langgraph/threads/{thread_id}/runs/{run}/cancel",
        token=token,
        project_id=project_id,
        payload={"wait": True},
    )
    return {
        "create_status": status,
        "thread_status": thread_status,
        "state_status": state_status,
        "history_status": history_status,
        "run_status": run_status,
        "run_terminal_status": snapshot.get("status"),
        "stream": stream,
        "event_stream": {
            "initial": event_stream,
            "replay": replay,
            "replay_cursor_not_older": (
                cursor is not None
                and all(
                    str(frame.get("id_value")) != str(cursor)
                    for frame in replay.get("frames", [])
                    if frame.get("id_value") is not None
                )
            ),
            "replay_cursor_advances": replay_cursor_advances,
        },
    }


def create_thread(token: str, project_id: str, marker: str) -> str:
    status, thread = request_json(
        "/api/langgraph/threads",
        token=token,
        project_id=project_id,
        payload={"graph_id": "reference_agent", "metadata": {"harness": marker}},
    )
    thread_id = thread.get("thread_id") or thread.get("id")
    if status not in {200, 201} or not isinstance(thread_id, str):
        raise RuntimeError(f"bound thread creation failed: HTTP {status}")
    return thread_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart-check", action="store_true")
    args = parser.parse_args()
    _, login = request_json(
        "/api/identity/session",
        payload={"username": "admin", "password": "admin123456"},
    )
    tokens = login.get("tokens") if isinstance(login.get("tokens"), dict) else {}
    token = tokens.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("local admin login failed")

    marker = f"l2-smoke-{uuid4()}"
    status, project = request_json("/api/projects", token=token, payload={"name": marker})
    project_id = project.get("id")
    if status != 200 or not isinstance(project_id, str):
        raise RuntimeError("isolated project creation failed")
    refresh_status, _ = request_json(
        "/api/runtime/graphs/refresh",
        token=token,
        project_id=project_id,
        payload={},
    )
    if refresh_status != 200:
        raise RuntimeError(f"runtime graph catalog refresh failed: HTTP {refresh_status}")
    thread_id = create_thread(token, project_id, marker)

    search_status, search_payload = request_json(
        "/api/langgraph/threads/search",
        token=token,
        project_id=project_id,
        payload={"limit": 100, "offset": 0, "metadata": {"harness": marker}},
    )
    count_status, count_payload = request_json(
        "/api/langgraph/threads/count",
        token=token,
        project_id=project_id,
        payload={"metadata": {"harness": marker}},
    )
    thread_get_status, _ = request_json(
        f"/api/langgraph/threads/{thread_id}",
        token=token,
        project_id=project_id,
    )

    command_status, command = request_json(
        f"/api/langgraph/threads/{thread_id}/commands",
        token=token,
        project_id=project_id,
        idempotency_key=f"{marker}-run-1",
        payload={
            "id": 1,
            "method": "run.start",
            "params": {
                "assistant_id": "reference_agent",
                "input": {"messages": [{"role": "user", "content": PROMPT}]},
                "durability": "sync",
                "stream_resumable": True,
                "on_disconnect": "continue",
            },
        },
    )
    command_result = command.get("result") if isinstance(command.get("result"), dict) else {}
    command_run_id = command_result.get("run_id")
    if command_status != 200 or not isinstance(command_run_id, str):
        reason = command.get("error") or command.get("detail") or command.get("message") or "unknown"
        raise RuntimeError(f"protocol run.start failed: HTTP {command_status} ({reason})")
    protocol_events = stream_shape(
        f"/api/langgraph/threads/{thread_id}/stream/events",
        token=token,
        project_id=project_id,
        payload={"channels": ["messages", "values", "updates", "lifecycle"], "since": 0},
    )
    protocol_snapshot_status, protocol_snapshot = request_json(
        f"/api/langgraph/threads/{thread_id}/runs/{command_run_id}",
        token=token,
        project_id=project_id,
    )
    protocol_kwargs = protocol_snapshot.get("kwargs") if isinstance(protocol_snapshot.get("kwargs"), dict) else {}

    standard_thread_id = create_thread(token, project_id, f"{marker}-standard")
    status, standard = request_json(
        f"/api/langgraph/threads/{standard_thread_id}/runs",
        token=token,
        project_id=project_id,
        payload={
            "assistant_id": "reference_agent",
            "input": {"messages": [{"role": "user", "content": PROMPT}]},
            "durability": "sync",
            "stream_resumable": True,
            "multitask_strategy": "reject",
            "context": {"temperature": 0.2, "tools": []},
            "stream_mode": ["values", "updates"],
            "after_seconds": 2,
        },
    )
    if status not in {200, 201}:
        raise RuntimeError("standard Runs create failed")
    standard_run_id = run_id(standard)
    standard_stream = stream_shape(
        f"/api/langgraph/threads/{standard_thread_id}/runs/{standard_run_id}/stream?stream_mode=values",
        token=token,
        project_id=project_id,
    )
    standard_snapshot_status, standard_snapshot = request_json(
        f"/api/langgraph/threads/{standard_thread_id}/runs/{standard_run_id}",
        token=token,
        project_id=project_id,
    )
    standard_kwargs = (
        standard_snapshot.get("kwargs")
        if isinstance(standard_snapshot.get("kwargs"), dict)
        else {}
    )

    cancel_thread_id = create_thread(token, project_id, f"{marker}-cancel")
    status, cancel_run = request_json(
        f"/api/langgraph/threads/{cancel_thread_id}/runs",
        token=token,
        project_id=project_id,
        payload={
            "assistant_id": "reference_agent",
            "input": {"messages": [{"role": "user", "content": PROMPT}]},
            "durability": "sync",
            "stream_resumable": True,
            "after_seconds": 30,
        },
    )
    if status not in {200, 201}:
        raise RuntimeError("delayed Runs create failed")
    cancel_run_id = run_id(cancel_run)
    cancel_status, _ = request_json(
        f"/api/langgraph/threads/{cancel_thread_id}/runs/{cancel_run_id}/cancel",
        token=token,
        project_id=project_id,
        payload={"wait": True},
    )
    final_status, final_run = request_json(
        f"/api/langgraph/threads/{cancel_thread_id}/runs/{cancel_run_id}",
        token=token,
        project_id=project_id,
    )

    duplicate_status, _ = request_json(
        f"/api/langgraph/threads/{thread_id}/commands",
        token=token,
        project_id=project_id,
        idempotency_key=f"{marker}-run-1",
        payload={
            "id": 2,
            "method": "run.start",
            "params": {
                "assistant_id": "reference_agent",
                "input": {"messages": [{"role": "user", "content": "different"}]},
            },
        },
    )

    second_project_status, second_project = request_json(
        "/api/projects", token=token, payload={"name": f"{marker}-other"}
    )
    second_project_id = second_project.get("id")
    if second_project_status != 200 or not isinstance(second_project_id, str):
        raise RuntimeError("second project creation failed")
    cross_project_status, _ = request_json(
        f"/api/langgraph/threads/{thread_id}",
        token=token,
        project_id=second_project_id,
    )

    active_thread_id = create_thread(token, project_id, f"{marker}-active")
    active_status, active = request_json(
        f"/api/langgraph/threads/{active_thread_id}/runs",
        token=token,
        project_id=project_id,
        payload={
            "assistant_id": "reference_agent",
            "input": {"messages": [{"role": "user", "content": PROMPT}]},
            "after_seconds": 30,
        },
    )
    active_run_id = run_id(active) if active_status in {200, 201} else ""
    conflict_status, _ = request_json(
        f"/api/langgraph/threads/{active_thread_id}/runs",
        token=token,
        project_id=project_id,
        payload={
            "assistant_id": "reference_agent",
            "input": {"messages": [{"role": "user", "content": PROMPT}]},
            "after_seconds": 30,
            "metadata": {"attempt": "conflict"},
        },
    )
    if active_run_id:
        request_json(
            f"/api/langgraph/threads/{active_thread_id}/runs/{active_run_id}/cancel",
            token=token,
            project_id=project_id,
            payload={"wait": True},
        )

    model_status, model_list = request_json("/api/runtime/models", token=token, project_id=project_id)
    models = model_list.get("models") if isinstance(model_list.get("models"), list) else []
    configured_model_id = models[0].get("id") if models and isinstance(models[0], dict) else None
    disable_update_status = None
    disabled_run_status = None
    restored_status = None
    if isinstance(configured_model_id, str):
        disabled_thread_id = create_thread(token, project_id, f"{marker}-disabled")
        disable_update_status, _ = request_json(
            f"/api/runtime/models/{configured_model_id}",
            token=token,
            project_id=project_id,
            payload={"enabled": False},
            method="PATCH",
        )
        disabled_run_status, _ = request_json(
            f"/api/langgraph/threads/{disabled_thread_id}/runs",
            token=token,
            project_id=project_id,
            payload={
                "assistant_id": "reference_agent",
                "input": {"messages": [{"role": "user", "content": PROMPT}]},
                "context": {"model_id": models[0].get("model_id")},
            },
        )
        restored_status, _ = request_json(
            f"/api/runtime/models/{configured_model_id}",
            token=token,
            project_id=project_id,
            payload={"enabled": True},
            method="PATCH",
        )

    reconnect_thread_id = create_thread(token, project_id, f"{marker}-reconnect")
    reconnect_status, reconnect_run = request_json(
        f"/api/langgraph/threads/{reconnect_thread_id}/runs",
        token=token,
        project_id=project_id,
        payload={
            "assistant_id": "reference_agent",
            "input": {"messages": [{"role": "user", "content": PROMPT}]},
            "after_seconds": 30,
        },
    )
    reconnect_run_id = run_id(reconnect_run) if reconnect_status in {200, 201} else ""
    reconnect_stream = (
        stream_shape(
            f"/api/langgraph/threads/{reconnect_thread_id}/runs/{reconnect_run_id}/stream?stream_mode=values",
            token=token,
            project_id=project_id,
        )
        if reconnect_run_id
        else {"http_status": 0, "frames": [], "has_cursor": False}
    )
    reconnect_snapshot_status, reconnect_snapshot = request_json(
        f"/api/langgraph/threads/{reconnect_thread_id}/runs/{reconnect_run_id}",
        token=token,
        project_id=project_id,
    ) if reconnect_run_id else (0, {})
    if reconnect_run_id:
        request_json(
            f"/api/langgraph/threads/{reconnect_thread_id}/runs/{reconnect_run_id}/cancel",
            token=token,
            project_id=project_id,
            payload={"wait": True},
        )

    restart_recovery = (
        restart_recovery_check(token, project_id, marker)
        if args.restart_check
        else None
    )

    print(
        json.dumps(
            {
                "project_created": True,
                "thread_created": True,
                "thread_queries": {
                    "search_status": search_status,
                    "search_items": (
                        len(search_payload)
                        if isinstance(search_payload, list)
                        else len(search_payload.get("items", []))
                        if isinstance(search_payload.get("items"), list)
                        else None
                    ),
                    "count_status": count_status,
                    "count": (
                        count_payload
                        if isinstance(count_payload, int)
                        else count_payload.get("count")
                    ),
                    "get_status": thread_get_status,
                },
                "protocol_run": {
                    "http_status": command_status,
                    "snapshot_status": protocol_snapshot_status,
                    "stream_resumable_persisted": protocol_kwargs.get("stream_resumable") is True,
                    "event_stream": protocol_events,
                },
                "standard_runs": {
                    "stream": standard_stream,
                    "snapshot_status": standard_snapshot_status,
                    "options": {
                        key: standard_kwargs.get(key)
                        for key in (
                            "context",
                            "durability",
                            "stream_resumable",
                            "multitask_strategy",
                            "stream_mode",
                        )
                        if key in standard_kwargs
                    },
                },
                "cancel": {
                    "http_status": cancel_status,
                    "snapshot_status": final_status,
                    "terminal_status": final_run.get("status"),
                },
                "negative_cases": {
                    "idempotency_conflict_http": duplicate_status,
                    "cross_project_get_http": cross_project_status,
                    "active_run_conflict_http": conflict_status,
                    "model_disable_http": disable_update_status if model_status == 200 else None,
                    "disabled_model_run_http": disabled_run_status if model_status == 200 else None,
                    "model_restore_http": restored_status if model_status == 200 else None,
                    "sse_disconnect_stream": reconnect_stream,
                    "sse_disconnect_run_status_http": reconnect_snapshot_status,
                    "sse_disconnect_run_status": reconnect_snapshot.get("status"),
                },
                "restart_recovery": restart_recovery,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
