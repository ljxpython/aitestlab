from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.schemas import OffsetPage
from app.modules.iam.domain import ProjectRole


class ServiceAccountTokenItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    token_prefix: str
    status: str
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None


class CreatedServiceAccountToken(BaseModel):
    model_config = ConfigDict(frozen=True)

    token: ServiceAccountTokenItem
    plain_text_token: str


class ServiceAccountItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str | None = None
    status: str
    platform_roles: tuple[str, ...]
    created_by: str | None = None
    updated_by: str | None = None
    last_used_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    tokens: list[ServiceAccountTokenItem]


class ServiceAccountPage(OffsetPage[ServiceAccountItem]):
    pass


class ServiceAccountProjectGrantItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    service_account_id: str
    project_id: str
    role: ProjectRole
    created_at: datetime | None = None
    updated_at: datetime | None = None
