from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


def _normalize_roles(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized = {value.strip() for value in values if value and value.strip()}
    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    trace_id: str
    method: str
    path: str
    started_at: float
    query: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectContext:
    project_id: str | None = None
    requested_by_header: bool = False


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: str | None = None
    subject: str | None = None
    email: str | None = None
    principal_type: str = "user"
    authentication_type: str = "bearer"
    credential_id: str | None = None
    must_change_password: bool = False
    platform_roles: tuple[str, ...] = field(default_factory=tuple)
    project_roles: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "platform_roles", _normalize_roles(list(self.platform_roles)))
        object.__setattr__(
            self,
            "project_roles",
            {
                project_id: _normalize_roles(list(roles))
                for project_id, roles in self.project_roles.items()
                if project_id
            },
        )

    @property
    def is_authenticated(self) -> bool:
        return bool(self.user_id or self.subject)

    def has_platform_role(self, role: str) -> bool:
        return role in self.platform_roles

    def project_role_set(self, project_id: str | None) -> tuple[str, ...]:
        if not project_id:
            return ()
        return self.project_roles.get(project_id, ())

    def has_project_role(self, project_id: str | None, role: str) -> bool:
        return role in self.project_role_set(project_id)


@dataclass(frozen=True, slots=True)
class PlatformRequestContext:
    request: RequestContext
    tenant: TenantContext
    project: ProjectContext
    actor: ActorContext
