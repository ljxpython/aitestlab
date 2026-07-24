from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.schemas import OffsetPage


class UserItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    username: str
    status: str
    is_super_admin: bool
    platform_roles: tuple[str, ...] = ()
    email: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    must_change_password: bool = False


class UserProjectItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    project_name: str
    project_description: str
    project_status: str
    role: str
    joined_at: datetime | None = None


class UserPage(OffsetPage[UserItem]):
    pass


class UserProjectPage(OffsetPage[UserProjectItem]):
    pass
