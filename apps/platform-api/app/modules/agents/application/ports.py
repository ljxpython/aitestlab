from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredAssistantAggregate:
    id: UUID
    project_id: UUID
    name: str
    description: str
    graph_id: str
    langgraph_assistant_id: str
    runtime_base_url: str
    sync_status: str
    last_sync_error: str | None
    last_synced_at: datetime | None
    status: str
    config: dict[str, Any]
    context: dict[str, Any]
    metadata: dict[str, Any]
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime | None
    updated_at: datetime | None


class AssistantsRepositoryProtocol(Protocol):
    def list_project_assistants(
        self,
        *,
        project_id: UUID,
        limit: int,
        offset: int,
        query: str | None,
        graph_id: str | None,
    ) -> tuple[list[StoredAssistantAggregate], int]: ...

    def get_assistant_by_id(self, assistant_id: UUID) -> StoredAssistantAggregate | None: ...

    def get_by_project_and_graph_id(
        self,
        *,
        project_id: UUID,
        graph_id: str,
    ) -> StoredAssistantAggregate | None: ...

    def create_assistant(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
        graph_id: str,
        runtime_base_url: str,
        langgraph_assistant_id: str,
    ) -> StoredAssistantAggregate: ...

    def update_assistant_runtime_fields(
        self,
        *,
        assistant_id: UUID,
        graph_id: str,
        name: str,
        description: str,
        runtime_base_url: str,
    ) -> StoredAssistantAggregate: ...

    def update_assistant_sync_state(
        self,
        *,
        assistant_id: UUID,
        sync_status: str,
        last_sync_error: str | None,
        last_synced_at: datetime | None,
    ) -> StoredAssistantAggregate: ...

    def upsert_assistant_profile(
        self,
        *,
        assistant_id: UUID,
        status: str,
        config: dict[str, Any],
        context: dict[str, Any],
        metadata: dict[str, Any],
        actor_user_id: UUID,
    ) -> StoredAssistantAggregate: ...

    def delete_assistant(self, *, assistant_id: UUID) -> None: ...


class AssistantsUpstreamProtocol(Protocol):
    async def create_assistant(self, payload: Mapping[str, Any]) -> Any: ...

    async def get_assistant(self, assistant_id: str) -> Any: ...

    async def update_assistant(self, assistant_id: str, payload: Mapping[str, Any]) -> Any: ...

    async def delete_assistant(
        self,
        assistant_id: str,
        *,
        delete_threads: bool = False,
    ) -> Any: ...


class AssistantParameterSchemaProviderProtocol(Protocol):
    def build_schema(self, graph_id: str) -> dict[str, Any]: ...
