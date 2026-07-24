from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.identifiers import parse_uuid
from app.core.security import hash_password
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.iam.domain import PlatformRole
from app.modules.users.application.contracts import (
    CreateUserCommand,
    ListUsersQuery,
    ResetUserPasswordCommand,
    UpdateUserCommand,
)
from app.modules.users.domain import UserItem, UserPage, UserProjectItem, UserProjectPage
from app.modules.users.infra import SqlAlchemyUsersRepository


def _normalize_platform_roles(
    values: tuple[PlatformRole, ...] | tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(sorted({str(role.value if isinstance(role, PlatformRole) else role).strip() for role in values if str(role).strip()}))


def _resolve_platform_roles_for_create(command: CreateUserCommand) -> tuple[str, ...]:
    roles = set(_normalize_platform_roles(command.platform_roles))
    if command.is_super_admin:
        roles.add(PlatformRole.SUPER_ADMIN.value)
    return tuple(sorted(roles))


def _resolve_platform_roles_for_update(
    *,
    current_roles: tuple[str, ...],
    command: UpdateUserCommand,
) -> tuple[str, ...]:
    roles = set(current_roles if command.platform_roles is None else _normalize_platform_roles(command.platform_roles))

    if command.is_super_admin is True:
        roles.add(PlatformRole.SUPER_ADMIN.value)
    elif command.is_super_admin is False:
        roles.discard(PlatformRole.SUPER_ADMIN.value)

    return tuple(sorted(roles))


class UsersService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _require_permission(self, *, actor: ActorContext, permission: PermissionCode) -> None:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=permission),
        )

    def _require_super_admin_role_permission(self, *, actor: ActorContext) -> None:
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_SUPER_ADMIN_MANAGE)

    def _user_item(self, item) -> UserItem:
        return UserItem(
            id=str(item.id),
            username=item.username,
            status=item.status,
            is_super_admin=item.is_super_admin,
            platform_roles=item.platform_roles,
            email=item.email,
            created_at=item.created_at,
            updated_at=item.updated_at,
            must_change_password=item.must_change_password,
        )

    def _user_project_item(self, item) -> UserProjectItem:
        return UserProjectItem(
            project_id=str(item.project_id),
            project_name=item.project_name,
            project_description=item.project_description,
            project_status=item.project_status,
            role=item.role,
            joined_at=item.joined_at,
        )

    def _parse_excluded_user_ids(self, values: tuple[str, ...]) -> tuple[UUID, ...]:
        excluded_user_ids: list[UUID] = []
        for raw_value in values:
            if not raw_value:
                continue
            excluded_user_ids.append(
                parse_uuid(raw_value, code="invalid_exclude_user_id"),
            )
        return tuple(excluded_user_ids)

    async def list_users(
        self,
        *,
        actor: ActorContext,
        query: ListUsersQuery,
    ) -> UserPage:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_READ)
        exclude_user_ids = self._parse_excluded_user_ids(query.exclude_user_ids)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyUsersRepository(uow.session)
            items, total = repository.list_users(
                limit=query.limit,
                offset=query.offset,
                query=query.query,
                status=query.status.value if query.status else None,
                exclude_user_ids=exclude_user_ids,
            )
            return UserPage(items=[self._user_item(item) for item in items], total=total)

    async def create_user(
        self,
        *,
        actor: ActorContext,
        command: CreateUserCommand,
    ) -> UserItem:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_CREATE)
        platform_roles = _resolve_platform_roles_for_create(command)
        if platform_roles:
            self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_ROLE_WRITE)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyUsersRepository(uow.session)
            if repository.get_user_by_username(command.username.strip()) is not None:
                raise ConflictError(
                    code="username_conflict",
                    message="Username already exists",
                )
            created = repository.create_user(
                username=command.username.strip(),
                password_hash=hash_password(command.password),
                email=None,
                platform_roles=platform_roles,
                is_super_admin=PlatformRole.SUPER_ADMIN.value in platform_roles,
                must_change_password=False,
            )
            return self._user_item(created)

    async def get_user(
        self,
        *,
        actor: ActorContext,
        user_id: str,
    ) -> UserItem:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_READ)
        user_uuid = parse_uuid(user_id, code="invalid_user_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyUsersRepository(uow.session)
            item = repository.get_user_by_id(user_uuid)
            if item is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            return self._user_item(item)

    async def list_user_projects(
        self,
        *,
        actor: ActorContext,
        user_id: str,
    ) -> UserProjectPage:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_READ)
        user_uuid = parse_uuid(user_id, code="invalid_user_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyUsersRepository(uow.session)
            item = repository.get_user_by_id(user_uuid)
            if item is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            projects = repository.list_user_projects(user_id=user_uuid)
            return UserProjectPage(
                items=[self._user_project_item(project) for project in projects],
                total=len(projects),
            )

    async def update_user(
        self,
        *,
        actor: ActorContext,
        user_id: str,
        command: UpdateUserCommand,
    ) -> UserItem:
        session_factory = self._require_session_factory()
        user_uuid = parse_uuid(user_id, code="invalid_user_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyUsersRepository(uow.session)
            current = repository.get_user_by_id(user_uuid)
            if current is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            if current.is_super_admin:
                self._require_super_admin_role_permission(actor=actor)
            if command.username is not None:
                self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_PROFILE_WRITE)
            if command.status is not None:
                self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_STATUS_WRITE)
            if command.password is not None:
                self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_CREDENTIAL_RESET)
            if command.platform_roles is not None or command.is_super_admin is not None:
                self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_ROLE_WRITE)

            next_username = command.username.strip() if command.username is not None else current.username
            next_status = command.status.value if command.status is not None else current.status
            next_platform_roles = _resolve_platform_roles_for_update(
                current_roles=current.platform_roles,
                command=command,
            )
            if (PlatformRole.SUPER_ADMIN.value in current.platform_roles) != (
                PlatformRole.SUPER_ADMIN.value in next_platform_roles
            ):
                self._require_super_admin_role_permission(actor=actor)
            next_is_super_admin = PlatformRole.SUPER_ADMIN.value in next_platform_roles
            if next_username != current.username:
                existing = repository.get_user_by_username(next_username)
                if existing is not None and existing.id != current.id:
                    raise ConflictError(
                        code="username_conflict",
                        message="Username already exists",
                    )

            if current.is_super_admin and (
                next_status != "active" or not next_is_super_admin
            ) and repository.count_active_super_admins() <= 1:
                raise ConflictError(
                    code="last_super_admin_protected",
                    message="Cannot disable or demote the last active super admin",
                )

            password_hash = hash_password(command.password) if command.password else None
            updated = repository.update_user(
                user_uuid,
                username=next_username,
                email=current.email,
                status=next_status,
                platform_roles=next_platform_roles,
                is_super_admin=next_is_super_admin,
                password_hash=password_hash,
                must_change_password=False if password_hash else None,
            )
            if updated is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            if password_hash or next_status != "active":
                repository.revoke_all_refresh_tokens_for_user(user_uuid)
            return self._user_item(updated)

    async def reset_password(
        self,
        *,
        actor: ActorContext,
        user_id: str,
        command: ResetUserPasswordCommand,
    ) -> UserItem:
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_USER_CREDENTIAL_RESET)
        user_uuid = parse_uuid(user_id, code="invalid_user_id")
        async with SqlAlchemyUnitOfWork(self._require_session_factory()) as uow:
            repository = SqlAlchemyUsersRepository(uow.session)
            current = repository.get_user_by_id(user_uuid)
            if current is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            if current.is_super_admin:
                self._require_super_admin_role_permission(actor=actor)
            updated = repository.update_user(
                user_uuid,
                username=current.username,
                email=current.email,
                status=current.status,
                platform_roles=current.platform_roles,
                is_super_admin=current.is_super_admin,
                password_hash=hash_password(command.temporary_password),
                must_change_password=False,
            )
            repository.revoke_all_refresh_tokens_for_user(user_uuid)
            if updated is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            return self._user_item(updated)
