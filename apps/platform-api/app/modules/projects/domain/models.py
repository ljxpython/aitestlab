from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.core.schemas import OffsetPage

from app.modules.iam.domain import ProjectRole


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETING = "deleting"
    DELETED = "deleted"


class ProjectSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    tenant_id: str
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectMember(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    user_id: str
    role: ProjectRole


class ProjectMemberView(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    user_id: str
    username: str
    role: ProjectRole


class ProjectPage(OffsetPage[ProjectSummary]):
    pass


class ProjectMemberPage(OffsetPage[ProjectMemberView]):
    pass


class ProjectAccess(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    roles: tuple[ProjectRole, ...] = ()
    permissions: tuple[str, ...] = ()


class ProjectMemberCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    username: str
    email: str | None = None


class ProjectMemberCandidatePage(OffsetPage[ProjectMemberCandidate]):
    pass
