from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.modules.iam.domain import PlatformRole
from app.modules.identity.domain import UserStatus


class ListUsersQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    query: str | None = None
    status: UserStatus | None = None
    exclude_user_ids: tuple[str, ...] = ()


class CreateUserCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8)
    platform_roles: tuple[PlatformRole, ...] = ()
    is_super_admin: bool = False


class UpdateUserCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=8)
    status: UserStatus | None = None
    platform_roles: tuple[PlatformRole, ...] | None = None
    is_super_admin: bool | None = None


class ResetUserPasswordCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    temporary_password: str = Field(min_length=8)
