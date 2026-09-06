from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import OffsetPage


class AssistantStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class AssistantSyncStatus(StrEnum):
    READY = "ready"
    ERROR = "error"
    SYNCING = "syncing"


class AssistantItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    name: str
    description: str = ""
    graph_id: str
    langgraph_assistant_id: str
    runtime_base_url: str
    sync_status: AssistantSyncStatus = AssistantSyncStatus.READY
    last_sync_error: str | None = None
    last_synced_at: datetime | None = None
    status: AssistantStatus = AssistantStatus.ACTIVE
    config: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssistantPage(OffsetPage[AssistantItem]):
    pass
