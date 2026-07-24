from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredServiceAccount:
    id: UUID
    name: str
    description: str | None
    status: str
    platform_roles: tuple[str, ...]
    created_by: str | None
    updated_by: str | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StoredServiceAccountToken:
    id: UUID
    service_account_id: UUID
    name: str
    token_prefix: str
    status: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_by: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoredServiceAccountProjectGrant:
    id: UUID
    service_account_id: UUID
    project_id: UUID
    role: str
    created_at: datetime
    updated_at: datetime


class ServiceAccountsRepositoryProtocol(Protocol):
    def list_service_accounts(
        self,
        *,
        limit: int,
        offset: int,
        query: str | None,
        status: str | None,
    ) -> tuple[list[StoredServiceAccount], int]: ...

    def get_service_account_by_id(self, service_account_id: UUID) -> StoredServiceAccount | None: ...

    def get_service_account_by_name(self, name: str) -> StoredServiceAccount | None: ...

    def create_service_account(
        self,
        *,
        name: str,
        description: str | None,
        platform_roles: tuple[str, ...],
        created_by: str | None,
    ) -> StoredServiceAccount: ...

    def update_service_account(
        self,
        *,
        service_account_id: UUID,
        description: str | None,
        status: str | None,
        platform_roles: tuple[str, ...] | None,
        updated_by: str | None,
    ) -> StoredServiceAccount | None: ...

    def list_tokens(self, *, service_account_id: UUID) -> list[StoredServiceAccountToken]: ...

    def create_token(
        self,
        *,
        service_account_id: UUID,
        name: str,
        token_prefix: str,
        token_secret_hash: str,
        expires_at: datetime | None,
        created_by: str | None,
    ) -> StoredServiceAccountToken: ...

    def get_active_token_by_prefix(self, *, token_prefix: str) -> StoredServiceAccountToken | None: ...

    def revoke_token(
        self,
        *,
        service_account_id: UUID,
        token_id: UUID,
    ) -> StoredServiceAccountToken | None: ...

    def touch_token_usage(
        self,
        *,
        token_id: UUID,
        service_account_id: UUID,
        used_at: datetime,
    ) -> None: ...

    def get_token_secret_hash(self, *, token_id: UUID) -> str | None: ...

    def summarize(self) -> dict[str, int]: ...
