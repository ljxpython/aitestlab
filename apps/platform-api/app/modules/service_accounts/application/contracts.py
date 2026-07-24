from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.modules.iam.domain import PlatformRole, ProjectRole


class ListServiceAccountsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=100, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    query: str | None = None
    status: str | None = None


class CreateServiceAccountCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    platform_roles: tuple[PlatformRole, ...] = (PlatformRole.VIEWER,)


class UpdateServiceAccountCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(active|disabled)$")
    platform_roles: tuple[PlatformRole, ...] | None = None


class CreateServiceAccountTokenCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=2, max_length=64)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class UpsertServiceAccountProjectGrantCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: ProjectRole
