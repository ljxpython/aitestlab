from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredPlatformUser:
    id: UUID
    username: str
    email: str | None
    status: str
    is_super_admin: bool
    platform_roles: tuple[str, ...]
    created_at: datetime | None
    updated_at: datetime | None
    must_change_password: bool


@dataclass(frozen=True, slots=True)
class StoredUserProjectMembership:
    project_id: UUID
    project_name: str
    project_description: str
    project_status: str
    role: str
    joined_at: datetime | None


class UsersRepositoryProtocol(Protocol):
    def list_users(
        self,
        *,
        limit: int,
        offset: int,
        query: str | None,
        status: str | None,
        exclude_user_ids: tuple[UUID, ...],
    ) -> tuple[list[StoredPlatformUser], int]: ...

    def get_user_by_id(self, user_id: UUID) -> StoredPlatformUser | None: ...

    def get_user_by_username(self, username: str) -> StoredPlatformUser | None: ...

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        email: str | None,
        platform_roles: tuple[str, ...] = (),
        is_super_admin: bool,
        must_change_password: bool = False,
    ) -> StoredPlatformUser: ...

    def update_user(
        self,
        user_id: UUID,
        *,
        username: str,
        email: str | None,
        status: str,
        platform_roles: tuple[str, ...],
        is_super_admin: bool,
        password_hash: str | None,
        must_change_password: bool | None = None,
    ) -> StoredPlatformUser | None: ...

    def list_user_projects(self, *, user_id: UUID) -> list[StoredUserProjectMembership]: ...

    def revoke_all_refresh_tokens_for_user(self, user_id: UUID) -> int: ...

    def count_active_super_admins(self) -> int: ...
