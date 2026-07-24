from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.iam.domain import ProjectRole


@dataclass(frozen=True, slots=True)
class StoredTenant:
    id: UUID
    slug: str
    name: str
    status: str


@dataclass(frozen=True, slots=True)
class StoredProject:
    id: UUID
    tenant_id: UUID
    name: str
    description: str
    status: str
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class StoredProjectMemberView:
    project_id: UUID
    user_id: UUID
    username: str
    role: ProjectRole


@dataclass(frozen=True, slots=True)
class StoredProjectMemberCandidate:
    user_id: UUID
    username: str
    email: str | None


class ProjectsRepositoryProtocol(Protocol):
    def get_or_create_default_tenant(self) -> StoredTenant: ...

    def list_projects(
        self,
        *,
        limit: int,
        offset: int,
        query: str | None,
    ) -> tuple[list[StoredProject], int]: ...

    def list_projects_for_user(
        self,
        *,
        user_id: UUID,
        limit: int,
        offset: int,
        query: str | None,
    ) -> tuple[list[StoredProject], int]: ...

    def create_project(
        self,
        *,
        tenant_id: UUID,
        name: str,
        description: str,
    ) -> StoredProject: ...

    def get_project_by_id(
        self,
        project_id: UUID,
        *,
        include_inactive: bool = False,
    ) -> StoredProject | None: ...

    def set_project_status(self, project_id: UUID, status: str) -> StoredProject | None: ...

    def soft_delete_project(self, project_id: UUID) -> None: ...

    def list_project_members(
        self,
        *,
        project_id: UUID,
        query: str | None,
    ) -> list[StoredProjectMemberView]: ...

    def get_project_member_role(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
    ) -> ProjectRole | None: ...

    def list_user_project_roles(self, *, user_id: UUID) -> dict[str, tuple[str, ...]]: ...

    def upsert_project_member(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
    ) -> StoredProjectMemberView: ...

    def remove_project_member(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
    ) -> None: ...

    def count_project_admins(self, *, project_id: UUID) -> int: ...

    def list_member_candidates(
        self,
        *,
        project_id: UUID,
        limit: int,
        offset: int,
        query: str | None,
    ) -> tuple[list[StoredProjectMemberCandidate], int]: ...

    def user_exists(self, *, user_id: UUID) -> bool: ...
