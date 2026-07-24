from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.modules.iam.domain import ProjectRole


class ListProjectsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    query: str | None = Field(default=None, max_length=128)


class CreateProjectCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class UpsertProjectMemberCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: ProjectRole


class ListProjectMembersQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str | None = Field(default=None, max_length=128)


class ProjectTakeoverCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    reason: str = Field(min_length=1, max_length=500)


class RestoreProjectAdminCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str = Field(min_length=1)
