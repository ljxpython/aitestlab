from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class UserProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    username: str
    email: str | None = None
    status: UserStatus = UserStatus.ACTIVE
    platform_roles: tuple[str, ...] = ()
    must_change_password: bool = False


class SessionTokens(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthenticatedSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    tokens: SessionTokens
    user: UserProfile
