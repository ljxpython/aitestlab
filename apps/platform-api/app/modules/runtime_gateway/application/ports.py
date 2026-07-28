from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class RuntimeGatewayUpstreamProtocol(Protocol):
    async def get_info(self) -> dict[str, Any]: ...

    async def search_graphs(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def count_graphs(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def create_thread(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def search_threads(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def count_threads(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def prune_threads(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def get_thread(self, thread_id: str) -> dict[str, Any]: ...

    async def update_thread(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def delete_thread(self, thread_id: str) -> Any: ...

    async def copy_thread(self, thread_id: str) -> Any: ...

    async def get_thread_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def update_thread_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def get_thread_history(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def create_global_run(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def stream_global_run(
        self,
        payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]: ...

    async def wait_global_run(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def create_batch_runs(self, payloads: list[dict[str, Any]]) -> Any: ...

    async def cancel_runs(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def create_cron(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def search_crons(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def count_crons(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def update_cron(
        self,
        cron_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def delete_cron(self, cron_id: str) -> Any: ...

    async def create_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def stream_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]: ...

    async def send_thread_command(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> Any: ...

    async def stream_thread_events(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[bytes]: ...

    async def wait_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def get_thread_run(self, thread_id: str, run_id: str) -> Any: ...

    async def list_thread_runs(
        self,
        thread_id: str,
        params: dict[str, Any] | None = None,
    ) -> Any: ...

    async def delete_thread_run(self, thread_id: str, run_id: str) -> Any: ...

    async def join_thread_run(self, thread_id: str, run_id: str) -> Any: ...

    async def join_thread_run_stream(
        self,
        thread_id: str,
        run_id: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]: ...

    async def create_thread_run_cron(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def cancel_thread_run(
        self,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...
