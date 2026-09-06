from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agents.domain import AssistantStatus


class ListAssistantsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    query: str | None = Field(default=None, max_length=128)
    graph_id: str | None = Field(default=None, max_length=128)


class CreateAssistantCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    graph_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    config: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class UpdateAssistantCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    graph_id: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    status: AssistantStatus | None = None
    config: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
