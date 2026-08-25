from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.adapters.langgraph.sdk_client import (
    get_langgraph_client,
    raise_runtime_upstream_error,
)


def _to_sse_chunk(event: Any) -> bytes:
    if isinstance(event, bytes):
        if event.endswith(b"\n\n"):
            return event
        if event.endswith(b"\n"):
            return event + b"\n"
        return event + b"\n\n"

    if isinstance(event, str):
        if event.startswith(("data:", "event:", "id:", "retry:", ":")):
            if event.endswith("\n\n"):
                return event.encode("utf-8")
            if event.endswith("\n"):
                return f"{event}\n".encode("utf-8")
            return f"{event}\n\n".encode("utf-8")
        return f"data: {event}\n\n".encode("utf-8")

    if isinstance(event, (list, tuple)):
        if len(event) >= 2 and isinstance(event[0], str):
            event_name = event[0]
            event_data = event[1]
            event_id = event[2] if len(event) >= 3 else None
            encoded_data = json.dumps(
                jsonable_encoder(event_data),
                separators=(",", ":"),
                ensure_ascii=False,
            )
            chunks = [f"event: {event_name}\n", f"data: {encoded_data}\n"]
            if event_id is not None:
                chunks.append(f"id: {event_id}\n")
            chunks.append("\n")
            return "".join(chunks).encode("utf-8")

    encoded = json.dumps(
        jsonable_encoder(event),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return f"data: {encoded}\n\n".encode("utf-8")


async def _sse_stream(events: Any) -> AsyncIterator[bytes]:
    if hasattr(events, "__aiter__"):
        async for event in events:
            yield _to_sse_chunk(event)
        return

    for event in events:
        yield _to_sse_chunk(event)


class LangGraphRunsSdkAdapter:
    _CREATE_FIELDS = (
        "input",
        "command",
        "stream_mode",
        "stream_subgraphs",
        "stream_resumable",
        "metadata",
        "config",
        "context",
        "checkpoint",
        "checkpoint_id",
        "checkpoint_during",
        "interrupt_before",
        "interrupt_after",
        "webhook",
        "multitask_strategy",
        "if_not_exists",
        "on_completion",
        "after_seconds",
        "durability",
    )

    _STREAM_FIELDS = _CREATE_FIELDS + (
        "version",
        "feedback_keys",
        "on_disconnect",
    )

    _WAIT_FIELDS = _CREATE_FIELDS + (
        "raise_error",
        "on_disconnect",
    )

    _CANCEL_FIELDS = (
        "wait",
        "action",
    )

    _BULK_CANCEL_FIELDS = (
        "thread_id",
        "run_ids",
        "status",
        "action",
    )

    _LIST_FIELDS = (
        "limit",
        "offset",
        "status",
        "select",
    )

    _CRON_CREATE_FIELDS = (
        "schedule",
        "input",
        "metadata",
        "config",
        "context",
        "checkpoint_during",
        "interrupt_before",
        "interrupt_after",
        "webhook",
        "on_run_completed",
        "multitask_strategy",
        "end_time",
        "enabled",
        "timezone",
        "stream_mode",
        "stream_subgraphs",
        "stream_resumable",
        "durability",
    )

    _CRON_SEARCH_FIELDS = (
        "assistant_id",
        "thread_id",
        "enabled",
        "limit",
        "offset",
        "sort_by",
        "sort_order",
        "select",
    )

    _CRON_COUNT_FIELDS = (
        "assistant_id",
        "thread_id",
    )

    _CRON_UPDATE_FIELDS = (
        "schedule",
        "end_time",
        "input",
        "metadata",
        "config",
        "context",
        "webhook",
        "interrupt_before",
        "interrupt_after",
        "on_run_completed",
        "enabled",
        "timezone",
        "stream_mode",
        "stream_subgraphs",
        "stream_resumable",
        "durability",
    )

    _JOIN_STREAM_FIELDS = (
        "cancel_on_disconnect",
        "stream_mode",
        "last_event_id",
    )

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._client = get_langgraph_client(
            base_url=base_url,
            api_key=api_key,
            forwarded_headers=forwarded_headers,
            timeout_seconds=timeout_seconds,
        )

    async def create(self, thread_id: str, payload: dict[str, Any]) -> Any:
        assistant_id = payload["assistant_id"]
        create_payload = {
            key: payload[key] for key in self._CREATE_FIELDS if key in payload
        }
        try:
            return await self._client.runs.create(thread_id, assistant_id, **create_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def create_global(self, payload: dict[str, Any]) -> Any:
        assistant_id = payload["assistant_id"]
        create_payload = {
            key: payload[key] for key in self._CREATE_FIELDS if key in payload
        }
        try:
            return await self._client.runs.create(None, assistant_id, **create_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def stream(self, thread_id: str, payload: dict[str, Any]) -> AsyncIterator[bytes]:
        assistant_id = payload["assistant_id"]
        stream_payload = {
            key: payload[key] for key in self._STREAM_FIELDS if key in payload
        }
        try:
            event_iter = self._client.runs.stream(thread_id, assistant_id, **stream_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_stream_failed")
        return _sse_stream(event_iter)

    async def stream_global(self, payload: dict[str, Any]) -> AsyncIterator[bytes]:
        assistant_id = payload["assistant_id"]
        stream_payload = {
            key: payload[key] for key in self._STREAM_FIELDS if key in payload
        }
        try:
            event_iter = self._client.runs.stream(None, assistant_id, **stream_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_stream_failed")
        return _sse_stream(event_iter)

    async def wait(self, thread_id: str, payload: dict[str, Any]) -> Any:
        assistant_id = payload["assistant_id"]
        wait_payload = {
            key: payload[key] for key in self._WAIT_FIELDS if key in payload
        }
        try:
            return await self._client.runs.wait(thread_id, assistant_id, **wait_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def wait_global(self, payload: dict[str, Any]) -> Any:
        assistant_id = payload["assistant_id"]
        wait_payload = {
            key: payload[key] for key in self._WAIT_FIELDS if key in payload
        }
        try:
            return await self._client.runs.wait(None, assistant_id, **wait_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def create_batch(self, payloads: list[dict[str, Any]]) -> Any:
        try:
            return await self._client.runs.create_batch(payloads)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def get(self, thread_id: str, run_id: str) -> Any:
        try:
            return await self._client.runs.get(thread_id, run_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def cancel(
        self,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        cancel_payload = {
            key: payload[key]
            for key in self._CANCEL_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.runs.cancel(thread_id, run_id, **cancel_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def cancel_many(self, payload: dict[str, Any] | None = None) -> Any:
        cancel_many_payload = {
            key: payload[key]
            for key in self._BULK_CANCEL_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.runs.cancel_many(**cancel_many_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def list(self, thread_id: str, payload: dict[str, Any] | None = None) -> Any:
        list_payload = {
            key: payload[key]
            for key in self._LIST_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.runs.list(thread_id, **list_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def delete(self, thread_id: str, run_id: str) -> Any:
        try:
            return await self._client.runs.delete(thread_id, run_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def join(self, thread_id: str, run_id: str) -> Any:
        try:
            return await self._client.runs.join(thread_id, run_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def join_stream(
        self,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        join_stream_payload = {
            key: payload[key]
            for key in self._JOIN_STREAM_FIELDS
            if payload is not None and key in payload
        }
        try:
            event_iter = self._client.runs.join_stream(thread_id, run_id, **join_stream_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_stream_failed")
        return _sse_stream(event_iter)

    async def create_cron(self, payload: dict[str, Any]) -> Any:
        assistant_id = payload["assistant_id"]
        cron_payload = {
            key: payload[key] for key in self._CRON_CREATE_FIELDS if key in payload
        }
        try:
            return await self._client.crons.create(assistant_id, **cron_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_cron_request_failed")

    async def search_crons(self, payload: dict[str, Any] | None = None) -> Any:
        search_payload = {
            key: payload[key]
            for key in self._CRON_SEARCH_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.crons.search(**search_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_cron_request_failed")

    async def count_crons(self, payload: dict[str, Any] | None = None) -> dict[str, int]:
        count_payload = {
            key: payload[key]
            for key in self._CRON_COUNT_FIELDS
            if payload is not None and key in payload
        }
        try:
            count = await self._client.crons.count(**count_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_cron_request_failed")
        return {"count": int(count)}

    async def update_cron(self, cron_id: str, payload: dict[str, Any]) -> Any:
        update_payload = {
            key: payload[key] for key in self._CRON_UPDATE_FIELDS if key in payload
        }
        try:
            return await self._client.crons.update(cron_id, **update_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_cron_request_failed")

    async def delete_cron(self, cron_id: str) -> Any:
        try:
            return await self._client.crons.delete(cron_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_cron_request_failed")

    async def create_cron_for_thread(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> Any:
        assistant_id = payload["assistant_id"]
        cron_payload = {
            key: payload[key] for key in self._CRON_CREATE_FIELDS if key in payload
        }
        try:
            return await self._client.crons.create_for_thread(
                thread_id,
                assistant_id,
                **cron_payload,
            )
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_cron_request_failed")
