from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredRuntimeModel:
    id: UUID
    runtime_id: str
    model_key: str
    display_name: str | None
    is_default_runtime: bool
    sync_status: str
    last_seen_at: datetime | None
    last_synced_at: datetime | None
    provider: str | None = None
    base_url: str | None = None
    protocol: str | None = None
    model_name: str | None = None
    api_key_ciphertext: str | None = None
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class StoredRuntimeTool:
    id: UUID
    runtime_id: str
    tool_key: str
    name: str
    source: str | None
    description: str | None
    sync_status: str
    last_seen_at: datetime | None
    last_synced_at: datetime | None


@dataclass(frozen=True, slots=True)
class StoredRuntimeGraph:
    id: UUID
    runtime_id: str
    graph_key: str
    display_name: str | None
    description: str | None
    source_type: str
    sync_status: str
    last_seen_at: datetime | None
    last_synced_at: datetime | None


class RuntimeCatalogRepositoryProtocol(Protocol):
    def list_models(self, *, runtime_id: str) -> list[StoredRuntimeModel]: ...

    def list_tools(self, *, runtime_id: str) -> list[StoredRuntimeTool]: ...

    def list_graphs(self, *, runtime_id: str) -> list[StoredRuntimeGraph]: ...

    def upsert_model_items(
        self,
        *,
        runtime_id: str,
        items: list[dict[str, Any]],
        synced_at: datetime,
    ) -> None: ...

    def upsert_tool_items(
        self,
        *,
        runtime_id: str,
        items: list[dict[str, Any]],
        synced_at: datetime,
    ) -> None: ...

    def upsert_graph_items(
        self,
        *,
        runtime_id: str,
        items: list[dict[str, Any]],
        synced_at: datetime,
        source_type: str,
    ) -> None: ...

    def mark_missing_models_deleted(
        self,
        *,
        runtime_id: str,
        active_keys: set[str],
        synced_at: datetime,
    ) -> None: ...

    def mark_missing_tools_deleted(
        self,
        *,
        runtime_id: str,
        active_keys: set[str],
        synced_at: datetime,
    ) -> None: ...

    def mark_missing_graphs_deleted(
        self,
        *,
        runtime_id: str,
        active_keys: set[str],
        synced_at: datetime,
    ) -> None: ...
