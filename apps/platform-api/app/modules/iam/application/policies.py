from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.context.models import ActorContext
from app.core.errors import BadRequestError, ForbiddenError, NotAuthenticatedError, PlatformApiError
from app.modules.iam.domain.roles import PlatformRole, ProjectRole


class PermissionCode(StrEnum):
    PLATFORM_USER_READ = "platform.user.read"
    PLATFORM_USER_WRITE = "platform.user.write"
    PLATFORM_USER_CREATE = "platform.user.create"
    PLATFORM_USER_PROFILE_WRITE = "platform.user.profile.write"
    PLATFORM_USER_STATUS_WRITE = "platform.user.status.write"
    PLATFORM_USER_CREDENTIAL_RESET = "platform.user.credential.reset"
    PLATFORM_USER_ROLE_WRITE = "platform.user.role.write"
    PLATFORM_PROJECT_READ = "platform.project.read"
    PLATFORM_PROJECT_CREATE = "platform.project.create"
    PLATFORM_PROJECT_WRITE = "platform.project.write"
    PLATFORM_PROJECT_TAKEOVER = "platform.project.takeover"
    PLATFORM_AUDIT_READ = "platform.audit.read"
    PLATFORM_CATALOG_REFRESH = "platform.catalog.refresh"
    PLATFORM_ANNOUNCEMENT_WRITE = "platform.announcement.write"
    PLATFORM_OPERATION_READ = "platform.operation.read"
    PLATFORM_OPERATION_WRITE = "platform.operation.write"
    PLATFORM_CONFIG_READ = "platform.config.read"
    PLATFORM_CONFIG_WRITE = "platform.config.write"
    PLATFORM_SERVICE_ACCOUNT_READ = "platform.service_account.read"
    PLATFORM_SERVICE_ACCOUNT_WRITE = "platform.service_account.write"
    PLATFORM_SERVICE_ACCOUNT_GRANT_WRITE = "platform.service_account.grant.write"
    PLATFORM_SUPER_ADMIN_MANAGE = "platform.super_admin.manage"
    PROJECT_MEMBER_READ = "project.member.read"
    PROJECT_MEMBER_WRITE = "project.member.write"
    PROJECT_AUDIT_READ = "project.audit.read"
    PROJECT_ANNOUNCEMENT_READ = "project.announcement.read"
    PROJECT_ANNOUNCEMENT_WRITE = "project.announcement.write"
    PROJECT_ASSISTANT_READ = "project.assistant.read"
    PROJECT_ASSISTANT_WRITE = "project.assistant.write"
    PROJECT_RUNTIME_READ = "project.runtime.read"
    PROJECT_RUNTIME_WRITE = "project.runtime.write"
    PROJECT_KNOWLEDGE_READ = "project.knowledge.read"
    PROJECT_KNOWLEDGE_WRITE = "project.knowledge.write"
    PROJECT_KNOWLEDGE_ADMIN = "project.knowledge.admin"
    PROJECT_TESTCASE_READ = "project.testcase.read"
    PROJECT_TESTCASE_WRITE = "project.testcase.write"
    PROJECT_OPERATION_READ = "project.operation.read"
    PROJECT_OPERATION_WRITE = "project.operation.write"


class PolicyReason(StrEnum):
    NOT_AUTHENTICATED = "not_authenticated"
    PLATFORM_SUPER_ADMIN = "platform_super_admin"
    PLATFORM_ROLE_ALLOWED = "platform_role_allowed"
    PROJECT_ROLE_ALLOWED = "project_role_allowed"
    MISSING_PLATFORM_ROLE = "missing_platform_role"
    PROJECT_SCOPE_REQUIRED = "project_scope_required"
    MISSING_PROJECT_ROLE = "missing_project_role"
    PERMISSION_NOT_REGISTERED = "permission_not_registered"


PLATFORM_PERMISSION_MAP: dict[PermissionCode, frozenset[PlatformRole]] = {
    PermissionCode.PLATFORM_USER_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_USER_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_USER_CREATE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_USER_PROFILE_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_USER_STATUS_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_USER_CREDENTIAL_RESET: frozenset({PlatformRole.SUPER_ADMIN}),
    PermissionCode.PLATFORM_USER_ROLE_WRITE: frozenset({PlatformRole.SUPER_ADMIN}),
    PermissionCode.PLATFORM_PROJECT_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_PROJECT_CREATE: frozenset({PlatformRole.SUPER_ADMIN}),
    PermissionCode.PLATFORM_PROJECT_WRITE: frozenset({PlatformRole.SUPER_ADMIN}),
    PermissionCode.PLATFORM_PROJECT_TAKEOVER: frozenset({PlatformRole.SUPER_ADMIN}),
    PermissionCode.PLATFORM_AUDIT_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_CATALOG_REFRESH: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_ANNOUNCEMENT_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_OPERATION_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_OPERATION_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_CONFIG_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_CONFIG_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_SERVICE_ACCOUNT_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_SERVICE_ACCOUNT_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_SERVICE_ACCOUNT_GRANT_WRITE: frozenset({PlatformRole.SUPER_ADMIN}),
    PermissionCode.PLATFORM_SUPER_ADMIN_MANAGE: frozenset({PlatformRole.SUPER_ADMIN}),
}

PROJECT_PERMISSION_MAP: dict[PermissionCode, frozenset[ProjectRole]] = {
    PermissionCode.PROJECT_MEMBER_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_MEMBER_WRITE: frozenset(
        {ProjectRole.ADMIN}
    ),
    PermissionCode.PROJECT_AUDIT_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_ANNOUNCEMENT_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_ANNOUNCEMENT_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_ASSISTANT_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_ASSISTANT_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_RUNTIME_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_RUNTIME_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_KNOWLEDGE_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_KNOWLEDGE_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_KNOWLEDGE_ADMIN: frozenset(
        {ProjectRole.ADMIN}
    ),
    PermissionCode.PROJECT_TESTCASE_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_TESTCASE_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_OPERATION_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_OPERATION_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
}


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    permission: PermissionCode
    project_id: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: PolicyReason


class IamPolicyEngine:
    def evaluate(
        self,
        *,
        actor: ActorContext,
        authorization: AuthorizationRequest,
    ) -> PolicyDecision:
        if not actor.is_authenticated:
            return PolicyDecision(allowed=False, reason=PolicyReason.NOT_AUTHENTICATED)

        permission = authorization.permission
        if permission in PROJECT_PERMISSION_MAP:
            if not authorization.project_id:
                return PolicyDecision(allowed=False, reason=PolicyReason.PROJECT_SCOPE_REQUIRED)
            actor_roles = actor.project_role_set(authorization.project_id)
            required_roles = PROJECT_PERMISSION_MAP[permission]
            matched = {ProjectRole(role) for role in actor_roles if role in required_roles}
            if matched:
                return PolicyDecision(allowed=True, reason=PolicyReason.PROJECT_ROLE_ALLOWED)
            return PolicyDecision(allowed=False, reason=PolicyReason.MISSING_PROJECT_ROLE)

        if permission in PLATFORM_PERMISSION_MAP:
            if actor.has_platform_role(PlatformRole.SUPER_ADMIN.value):
                return PolicyDecision(allowed=True, reason=PolicyReason.PLATFORM_SUPER_ADMIN)
            required_roles = PLATFORM_PERMISSION_MAP[permission]
            matched = {PlatformRole(role) for role in actor.platform_roles if role in required_roles}
            if matched:
                return PolicyDecision(allowed=True, reason=PolicyReason.PLATFORM_ROLE_ALLOWED)
            return PolicyDecision(allowed=False, reason=PolicyReason.MISSING_PLATFORM_ROLE)

        return PolicyDecision(allowed=False, reason=PolicyReason.PERMISSION_NOT_REGISTERED)

    def require(
        self,
        *,
        actor: ActorContext,
        authorization: AuthorizationRequest,
    ) -> None:
        decision = self.evaluate(actor=actor, authorization=authorization)
        if decision.allowed:
            return
        if decision.reason is PolicyReason.NOT_AUTHENTICATED:
            raise NotAuthenticatedError()
        if decision.reason is PolicyReason.PROJECT_SCOPE_REQUIRED:
            raise BadRequestError(
                code=PolicyReason.PROJECT_SCOPE_REQUIRED.value,
                message="Project scope required",
            )
        if decision.reason is PolicyReason.MISSING_PLATFORM_ROLE:
            raise ForbiddenError(
                code="platform_role_missing",
                message="Platform role missing",
            )
        if decision.reason is PolicyReason.MISSING_PROJECT_ROLE:
            raise ForbiddenError(
                code="project_role_missing",
                message="Project role missing",
            )
        if decision.reason is PolicyReason.PERMISSION_NOT_REGISTERED:
            raise PlatformApiError(
                code=PolicyReason.PERMISSION_NOT_REGISTERED.value,
                status_code=500,
                message="Permission not registered",
            )
        raise PlatformApiError(
            code="policy_engine_unhandled_reason",
            status_code=500,
            message=f"Unhandled policy decision reason: {decision.reason.value}",
        )
