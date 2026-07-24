from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.identifiers import parse_actor_user_id, parse_uuid
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.iam.application.policies import PROJECT_PERMISSION_MAP
from app.modules.iam.domain import ProjectRole
from app.modules.projects.application.contracts import (
    CreateProjectCommand,
    ListProjectMembersQuery,
    ListProjectsQuery,
    ProjectTakeoverCommand,
    RestoreProjectAdminCommand,
    UpsertProjectMemberCommand,
)
from app.modules.projects.application.ports import StoredProject, StoredProjectMemberView
from app.modules.projects.domain import (
    ProjectMemberPage,
    ProjectMemberCandidate,
    ProjectMemberCandidatePage,
    ProjectMemberView,
    ProjectPage,
    ProjectStatus,
    ProjectSummary,
    ProjectAccess,
)
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class ProjectsService:
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

    def _project_summary(self, project: StoredProject) -> ProjectSummary:
        return ProjectSummary(
            id=str(project.id),
            tenant_id=str(project.tenant_id),
            name=project.name,
            description=project.description,
            status=ProjectStatus(project.status),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def _member_view(self, item: StoredProjectMemberView) -> ProjectMemberView:
        return ProjectMemberView(
            project_id=str(item.project_id),
            user_id=str(item.user_id),
            username=item.username,
            role=item.role,
        )

    async def list_projects(
        self,
        *,
        actor: ActorContext,
        query: ListProjectsQuery,
    ) -> ProjectPage:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            if self._policy_engine.evaluate(
                actor=actor,
                authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_PROJECT_READ),
            ).allowed:
                items, total = repository.list_projects(
                    limit=query.limit,
                    offset=query.offset,
                    query=query.query,
                )
            else:
                items, total = repository.list_projects_for_user(
                    user_id=actor_user_id,
                    limit=query.limit,
                    offset=query.offset,
                    query=query.query,
                )
            return ProjectPage(
                items=[self._project_summary(item) for item in items],
                total=total,
            )

    async def create_project(
        self,
        *,
        actor: ActorContext,
        command: CreateProjectCommand,
    ) -> ProjectSummary:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_PROJECT_CREATE),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            tenant = repository.get_or_create_default_tenant()
            project = repository.create_project(
                tenant_id=tenant.id,
                name=command.name.strip(),
                description=command.description.strip(),
            )
            repository.upsert_project_member(
                project_id=project.id,
                user_id=actor_user_id,
                role=ProjectRole.ADMIN,
            )
            return self._project_summary(project)

    async def delete_project(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_PROJECT_WRITE),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid, include_inactive=True)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            repository.soft_delete_project(project_uuid)

    async def archive_project(self, *, actor: ActorContext, project_id: str) -> ProjectSummary:
        return await self._set_project_lifecycle(
            actor=actor,
            project_id=project_id,
            expected_status="active",
            next_status="disabled",
        )

    async def restore_project(self, *, actor: ActorContext, project_id: str) -> ProjectSummary:
        return await self._set_project_lifecycle(
            actor=actor,
            project_id=project_id,
            expected_status="disabled",
            next_status="active",
        )

    async def _set_project_lifecycle(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        expected_status: str,
        next_status: str,
    ) -> ProjectSummary:
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_PROJECT_WRITE),
        )
        async with SqlAlchemyUnitOfWork(self._require_session_factory()) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid, include_inactive=True)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            if project.status != expected_status:
                raise ConflictError(
                    code="invalid_project_status",
                    message=f"Project status must be {expected_status}",
                )
            updated = repository.set_project_status(project_uuid, next_status)
            if updated is None:
                raise NotFoundError(message="Project not found", code="project_not_found")
            return self._project_summary(updated)

    async def list_members(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ListProjectMembersQuery,
    ) -> ProjectMemberPage:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_MEMBER_READ,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None:
                raise NotFoundError(message="Project not found", code="project_not_found")
            items = repository.list_project_members(
                project_id=project_uuid,
                query=query.query,
            )
            return ProjectMemberPage(items=[self._member_view(item) for item in items])

    async def upsert_member(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        user_id: str,
        command: UpsertProjectMemberCommand,
    ) -> ProjectMemberView:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        target_user_id = parse_uuid(user_id, code="invalid_user_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_MEMBER_WRITE,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None:
                raise NotFoundError(message="Project not found", code="project_not_found")
            if not repository.user_exists(user_id=target_user_id):
                raise NotFoundError(message="User not found", code="user_not_found")

            current_role = repository.get_project_member_role(
                project_id=project_uuid,
                user_id=target_user_id,
            )
            if current_role == ProjectRole.ADMIN and command.role != ProjectRole.ADMIN:
                if repository.count_project_admins(project_id=project_uuid) <= 1:
                    raise ConflictError(
                        code="cannot_downgrade_last_admin",
                        message="Cannot downgrade the last project admin",
                    )

            item = repository.upsert_project_member(
                project_id=project_uuid,
                user_id=target_user_id,
                role=command.role,
            )
            return self._member_view(item)

    async def remove_member(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        user_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        target_user_id = parse_uuid(user_id, code="invalid_user_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_MEMBER_WRITE,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            role = repository.get_project_member_role(
                project_id=project_uuid,
                user_id=target_user_id,
            )
            if role is None:
                raise NotFoundError(message="Member not found", code="member_not_found")
            if role == ProjectRole.ADMIN and repository.count_project_admins(project_id=project_uuid) <= 1:
                raise ConflictError(
                    code="cannot_remove_last_admin",
                    message="Cannot remove the last project admin",
                )
            repository.remove_project_member(project_id=project_uuid, user_id=target_user_id)

    async def get_access(self, *, actor: ActorContext, project_id: str) -> ProjectAccess:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid, include_inactive=True)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            if project.status != "active":
                return ProjectAccess(project_id=project_id)
            roles: tuple[ProjectRole, ...] = ()
            if actor.principal_type == "user":
                role = repository.get_project_member_role(
                    project_id=project_uuid,
                    user_id=parse_actor_user_id(actor),
                )
                roles = (role,) if role is not None else ()
            else:
                from app.modules.service_accounts.infra.sqlalchemy.repository import SqlAlchemyServiceAccountsRepository

                role = SqlAlchemyServiceAccountsRepository(uow.session).get_project_grant_role(
                    credential_id=actor.credential_id,
                    project_id=project_uuid,
                )
                roles = (role,) if role is not None else ()
            scoped_actor = ActorContext(
                user_id=actor.user_id,
                subject=actor.subject,
                principal_type=actor.principal_type,
                platform_roles=actor.platform_roles,
                project_roles={project_id: tuple(role.value for role in roles)},
            )
            permissions = tuple(
                permission.value
                for permission in PROJECT_PERMISSION_MAP
                if self._policy_engine.evaluate(
                    actor=scoped_actor,
                    authorization=AuthorizationRequest(permission=permission, project_id=project_id),
                ).allowed
            )
            return ProjectAccess(project_id=project_id, roles=roles, permissions=permissions)

    async def list_member_candidates(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        limit: int,
        offset: int,
        query: str | None,
    ) -> ProjectMemberCandidatePage:
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_MEMBER_WRITE,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(self._require_session_factory()) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            items, total = repository.list_member_candidates(
                project_id=project_uuid,
                limit=limit,
                offset=offset,
                query=query,
            )
            return ProjectMemberCandidatePage(
                items=[
                    ProjectMemberCandidate(
                        user_id=str(item.user_id),
                        username=item.username,
                        email=item.email,
                    )
                    for item in items
                ],
                total=total,
            )

    async def takeover(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        command: ProjectTakeoverCommand,
    ) -> ProjectMemberView:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_PROJECT_TAKEOVER),
        )
        return await self._restore_admin(project_id=project_id, user_id=actor.user_id)

    async def restore_admin(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        command: RestoreProjectAdminCommand,
    ) -> ProjectMemberView:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_PROJECT_WRITE),
        )
        return await self._restore_admin(project_id=project_id, user_id=command.user_id)

    async def _restore_admin(self, *, project_id: str, user_id: str | None) -> ProjectMemberView:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        target_user_id = parse_uuid(user_id or "", code="invalid_user_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            if not repository.user_exists(user_id=target_user_id):
                raise NotFoundError(message="User not found", code="user_not_found")
            return self._member_view(
                repository.upsert_project_member(
                    project_id=project_uuid,
                    user_id=target_user_id,
                    role=ProjectRole.ADMIN,
                )
            )
