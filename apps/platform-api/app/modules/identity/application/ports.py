from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredUser:
    id: UUID
    username: str
    external_subject: str
    email: str | None
    status: str
    password_hash: str
    is_super_admin: bool
    platform_roles: tuple[str, ...]
    must_change_password: bool
    failed_login_attempts: int
    locked_until: datetime | None


@dataclass(frozen=True, slots=True)
class StoredRefreshToken:
    token_id: str
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    family_id: str
    consumed_at: datetime | None


class ProjectRolesReader(Protocol):
    def list_user_project_roles(self, *, user_id: UUID) -> dict[str, tuple[str, ...]]: ...


class IdentityRepository(Protocol):
    def get_user_by_username(self, username: str) -> StoredUser | None: ...

    def get_user_by_id(self, user_id: UUID) -> StoredUser | None: ...

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        external_subject: str,
        email: str | None,
        platform_roles: tuple[str, ...] = (),
        is_super_admin: bool,
        must_change_password: bool = False,
    ) -> StoredUser: ...

    def count_super_admins(self) -> int: ...

    def get_refresh_token(self, token_id: str) -> StoredRefreshToken | None: ...

    def create_refresh_token(
        self,
        *,
        user_id: UUID,
        token_id: str,
        family_id: str,
        expires_at: datetime,
    ) -> StoredRefreshToken: ...

    def consume_refresh_token(self, token_id: str) -> tuple[StoredRefreshToken | None, str | None]: ...

    def revoke_refresh_token(self, token_id: str) -> None: ...

    def revoke_refresh_token_family(self, family_id: str) -> int: ...

    def revoke_all_refresh_tokens_for_user(self, user_id: UUID) -> int: ...

    def update_user_password_hash(
        self,
        user_id: UUID,
        password_hash: str,
        *,
        must_change_password: bool,
    ) -> None: ...

    def record_login_failure(self, user_id: UUID, *, locked_until: datetime | None) -> None: ...

    def clear_login_failures(self, user_id: UUID) -> None: ...

    def update_user_profile(
        self,
        user_id: UUID,
        *,
        username: str,
        email: str | None,
    ) -> StoredUser | None: ...

    def reconcile_bootstrap_admin(
        self,
        *,
        username: str,
        password_hash: str,
    ) -> str | None: ...
