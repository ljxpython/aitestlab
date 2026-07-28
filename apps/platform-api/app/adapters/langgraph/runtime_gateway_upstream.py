from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from app.adapters.langgraph.graphs_sdk_adapter import LangGraphGraphsSdkAdapter
from app.adapters.langgraph.runs_sdk_adapter import LangGraphRunsSdkAdapter
from app.adapters.langgraph.runtime_client import LangGraphRuntimeClient
from app.adapters.langgraph.threads_sdk_adapter import LangGraphThreadsSdkAdapter
from app.core.errors import PlatformApiError


class LangGraphRuntimeGatewayUpstream:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        api_key: str | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._http = LangGraphRuntimeClient(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            api_key=api_key,
            forwarded_headers=forwarded_headers,
        )
        self._graphs = LangGraphGraphsSdkAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            forwarded_headers=forwarded_headers,
        )
        self._threads = LangGraphThreadsSdkAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            forwarded_headers=forwarded_headers,
        )
        self._runs = LangGraphRunsSdkAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            forwarded_headers=forwarded_headers,
        )

    async def get_info(self) -> dict[str, Any]:
        return await self._http.require_json("GET", "/info")

    async def search_graphs(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._graphs.search(payload)

    async def count_graphs(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._graphs.count(payload)

    async def create_thread(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._threads.create(payload)

    async def search_threads(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._threads.search(payload)

    async def count_threads(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._threads.count(payload)

    async def prune_threads(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._threads.prune(payload)

    async def get_thread(self, thread_id: str) -> dict[str, Any]:
        value = await self._threads.get(thread_id)
        if isinstance(value, dict):
            return value
        raise PlatformApiError(
            code="langgraph_upstream_invalid_response",
            status_code=502,
            message="LangGraph upstream returned an invalid thread payload",
        )

    async def update_thread(self, thread_id: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._threads.update(thread_id, payload)

    async def delete_thread(self, thread_id: str) -> Any:
        return await self._threads.delete(thread_id)

    async def copy_thread(self, thread_id: str) -> Any:
        value = await self._threads.copy(thread_id)
        if value is None or isinstance(value, dict):
            return value
        raise PlatformApiError(
            code="langgraph_upstream_invalid_response",
            status_code=502,
            message="LangGraph upstream returned an invalid thread copy payload",
        )

    async def get_thread_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._threads.get_state(thread_id, payload)

    async def update_thread_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._threads.update_state(thread_id, payload)

    async def get_thread_history(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._threads.get_history(thread_id, payload)

    async def create_global_run(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._runs.create_global(payload or {})

    async def stream_global_run(
        self,
        payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        return await self._runs.stream_global(payload or {})

    async def wait_global_run(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._runs.wait_global(payload or {})

    async def create_batch_runs(self, payloads: list[dict[str, Any]]) -> Any:
        return await self._runs.create_batch(payloads)

    async def cancel_runs(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._runs.cancel_many(payload)

    async def create_cron(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._runs.create_cron(payload or {})

    async def search_crons(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._runs.search_crons(payload)

    async def count_crons(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._runs.count_crons(payload)

    async def update_cron(self, cron_id: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._runs.update_cron(cron_id, payload or {})

    async def delete_cron(self, cron_id: str) -> Any:
        return await self._runs.delete_cron(cron_id)

    async def create_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runs.create(thread_id, payload or {})

    async def stream_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        return await self._runs.stream(thread_id, payload or {})

    async def send_thread_command(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return await self._http.request_json(
            "POST",
            f"/threads/{thread_id}/commands",
            payload=payload,
        )

    async def stream_thread_events(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        return await self._http.stream(
            "POST",
            f"/threads/{thread_id}/stream/events",
            payload=payload,
        )

    async def wait_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runs.wait(thread_id, payload or {})

    async def get_thread_run(self, thread_id: str, run_id: str) -> Any:
        return await self._runs.get(thread_id, run_id)

    async def list_thread_runs(
        self,
        thread_id: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runs.list(thread_id, params)

    async def delete_thread_run(self, thread_id: str, run_id: str) -> Any:
        return await self._runs.delete(thread_id, run_id)

    async def join_thread_run(self, thread_id: str, run_id: str) -> Any:
        return await self._runs.join(thread_id, run_id)

    async def join_thread_run_stream(
        self,
        thread_id: str,
        run_id: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        return await self._runs.join_stream(thread_id, run_id, params)

    async def create_thread_run_cron(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runs.create_cron_for_thread(thread_id, payload or {})

    async def cancel_thread_run(
        self,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runs.cancel(thread_id, run_id, payload)
