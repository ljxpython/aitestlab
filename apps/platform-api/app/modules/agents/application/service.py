from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.identifiers import parse_actor_user_id, parse_uuid
from app.core.runtime_contract import (
    normalize_runtime_contract,
    normalize_runtime_object,
)
from app.modules.agents.application.contracts import (
    CreateAssistantCommand,
    ListAssistantsQuery,
    UpdateAssistantCommand,
)
from app.modules.agents.application.ports import (
    AssistantParameterSchemaProviderProtocol,
    AssistantsUpstreamProtocol,
    StoredAssistantAggregate,
)
from app.modules.agents.domain import (
    AssistantItem,
    AssistantPage,
    AssistantStatus,
    AssistantSyncStatus,
)
from app.modules.agents.infra.sqlalchemy.repository import SqlAlchemyAssistantsRepository
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_object(value: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_runtime_object(value)


def _normalize_assistant_runtime_contract(
    *,
    config: dict[str, Any],
    context: dict[str, Any],
    metadata: dict[str, Any],
    project_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return normalize_runtime_contract(
        config=config,
        context=context,
        metadata=metadata,
        project_id=project_id,
    )


class AssistantsService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        runtime_base_url: str,
        upstream: AssistantsUpstreamProtocol,
        schema_provider: AssistantParameterSchemaProviderProtocol,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_base_url = runtime_base_url.rstrip("/")
        self._upstream = upstream
        self._schema_provider = schema_provider
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _assistant_item(self, item: StoredAssistantAggregate) -> AssistantItem:
        try:
            sync_status = AssistantSyncStatus(item.sync_status)
        except ValueError:
            sync_status = AssistantSyncStatus.READY
        try:
            status = AssistantStatus(item.status)
        except ValueError:
            status = AssistantStatus.ACTIVE
        return AssistantItem(
            id=str(item.id),
            project_id=str(item.project_id),
            name=item.name,
            description=item.description,
            graph_id=item.graph_id,
            langgraph_assistant_id=item.langgraph_assistant_id,
            runtime_base_url=item.runtime_base_url,
            sync_status=sync_status,
            last_sync_error=item.last_sync_error,
            last_synced_at=item.last_synced_at,
            status=status,
            config=dict(item.config),
            context=dict(item.context),
            metadata=dict(item.metadata),
            created_by=str(item.created_by) if item.created_by else None,
            updated_by=str(item.updated_by) if item.updated_by else None,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _require_project_exists(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        project_id: str,
    ) -> None:
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        projects_repository = SqlAlchemyProjectsRepository(uow.session)
        project = projects_repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")

    async def list_assistants(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ListAssistantsQuery,
    ) -> AssistantPage:
        session_factory = self._require_session_factory()
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_ASSISTANT_READ,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            self._require_project_exists(uow=uow, project_id=project_id)
            repository = SqlAlchemyAssistantsRepository(uow.session)
            items, total = repository.list_project_assistants(
                project_id=parse_uuid(project_id, code="invalid_project_id"),
                limit=query.limit,
                offset=query.offset,
                query=query.query,
                graph_id=query.graph_id,
            )
            return AssistantPage(
                items=[self._assistant_item(item) for item in items],
                total=total,
            )

    async def create_assistant(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        command: CreateAssistantCommand,
    ) -> AssistantItem:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_ASSISTANT_WRITE,
                project_id=project_id,
            ),
        )
        user_config = _normalize_object(command.config)
        user_context = _normalize_object(command.context)
        user_metadata = _normalize_object(command.metadata)
        user_config, user_context, user_metadata = _normalize_assistant_runtime_contract(
            config=user_config,
            context=user_context,
            metadata=user_metadata,
            project_id=project_id,
        )

        try:
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                self._require_project_exists(uow=uow, project_id=project_id)
                repository = SqlAlchemyAssistantsRepository(uow.session)
                created = repository.create_assistant(
                    project_id=parse_uuid(project_id, code="invalid_project_id"),
                    name=command.name.strip(),
                    description=command.description.strip(),
                    graph_id=command.graph_id.strip(),
                    runtime_base_url=self._runtime_base_url,
                    # Agent key is the graph id. The legacy column remains a
                    # read-compatibility alias until historical data is retired.
                    langgraph_assistant_id=command.graph_id.strip(),
                )
                item = repository.upsert_assistant_profile(
                    assistant_id=created.id,
                    status=AssistantStatus.ACTIVE.value,
                    config=user_config,
                    context=user_context,
                    metadata=user_metadata,
                    actor_user_id=actor_user_id,
                )
                return self._assistant_item(item)
        except IntegrityError as exc:
            raise ConflictError(
                code="assistant_name_conflict",
                message="Assistant name already exists in this project",
            ) from exc

    async def get_assistant(
        self,
        *,
        actor: ActorContext,
        assistant_id: str,
    ) -> AssistantItem:
        session_factory = self._require_session_factory()
        assistant_uuid = parse_uuid(assistant_id, code="invalid_assistant_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAssistantsRepository(uow.session)
            item = repository.get_assistant_by_id(assistant_uuid)
            if item is None:
                raise NotFoundError(
                    message="Assistant not found",
                    code="assistant_not_found",
                )
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_READ,
                    project_id=str(item.project_id),
                ),
            )
            return self._assistant_item(item)

    async def update_assistant(
        self,
        *,
        actor: ActorContext,
        assistant_id: str,
        command: UpdateAssistantCommand,
    ) -> AssistantItem:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        assistant_uuid = parse_uuid(assistant_id, code="invalid_assistant_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAssistantsRepository(uow.session)
            current = repository.get_assistant_by_id(assistant_uuid)
            if current is None:
                raise NotFoundError(
                    message="Assistant not found",
                    code="assistant_not_found",
                )
            project_id = str(current.project_id)
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_WRITE,
                    project_id=project_id,
                ),
            )

            fields_set = command.model_fields_set
            next_graph_id = (
                command.graph_id.strip()
                if "graph_id" in fields_set and isinstance(command.graph_id, str)
                else current.graph_id
            )
            next_name = (
                command.name.strip()
                if "name" in fields_set and isinstance(command.name, str)
                else current.name
            )
            next_description = (
                command.description.strip()
                if "description" in fields_set and isinstance(command.description, str)
                else current.description
            )
            next_status = (
                command.status.value
                if "status" in fields_set and command.status is not None
                else current.status
            )
            next_config = (
                _normalize_object(command.config)
                if "config" in fields_set
                else dict(current.config)
            )
            next_context = (
                _normalize_object(command.context)
                if "context" in fields_set
                else dict(current.context)
            )
            next_metadata = (
                _normalize_object(command.metadata)
                if "metadata" in fields_set
                else dict(current.metadata)
            )
            next_config, next_context, next_metadata = _normalize_assistant_runtime_contract(
                config=next_config,
                context=next_context,
                metadata=next_metadata,
                project_id=project_id,
            )

            repository.update_assistant_runtime_fields(
                assistant_id=assistant_uuid,
                graph_id=next_graph_id,
                name=next_name,
                description=next_description,
                runtime_base_url=self._runtime_base_url,
            )
            item = repository.upsert_assistant_profile(
                assistant_id=assistant_uuid,
                status=next_status,
                config=next_config,
                context=next_context,
                metadata=next_metadata,
                actor_user_id=actor_user_id,
            )
            return self._assistant_item(item)

    async def delete_assistant(
        self,
        *,
        actor: ActorContext,
        assistant_id: str,
        delete_runtime: bool,
        delete_threads: bool,
    ) -> str:
        session_factory = self._require_session_factory()
        assistant_uuid = parse_uuid(assistant_id, code="invalid_assistant_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAssistantsRepository(uow.session)
            current = repository.get_assistant_by_id(assistant_uuid)
            if current is None:
                raise NotFoundError(
                    message="Assistant not found",
                    code="assistant_not_found",
                )
            project_id = str(current.project_id)
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_WRITE,
                    project_id=project_id,
                ),
            )
            repository.delete_assistant(assistant_id=assistant_uuid)
            return project_id

    async def resync_assistant(
        self,
        *,
        actor: ActorContext,
        assistant_id: str,
    ) -> AssistantItem:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        assistant_uuid = parse_uuid(assistant_id, code="invalid_assistant_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAssistantsRepository(uow.session)
            current = repository.get_assistant_by_id(assistant_uuid)
            if current is None:
                raise NotFoundError(
                    message="Assistant not found",
                    code="assistant_not_found",
                )
            project_id = str(current.project_id)
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_WRITE,
                    project_id=project_id,
                ),
            )

            repository.update_assistant_sync_state(
                assistant_id=assistant_uuid,
                sync_status=AssistantSyncStatus.READY.value,
                last_sync_error=None,
                last_synced_at=_now(),
            )
            item = repository.upsert_assistant_profile(
                assistant_id=assistant_uuid,
                status=current.status,
                config=dict(current.config),
                context=dict(current.context),
                metadata=dict(current.metadata),
                actor_user_id=actor_user_id,
            )
            return self._assistant_item(item)

    async def get_parameter_schema(
        self,
        *,
        actor: ActorContext,
        graph_id: str,
        project_id: str | None,
    ) -> dict[str, Any]:
        normalized_graph_id = graph_id.strip()
        if not normalized_graph_id:
            raise BadRequestError(
                code="invalid_graph_id",
                message="Graph id is invalid",
            )

        if project_id:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_READ,
                    project_id=project_id,
                ),
            )
        elif not actor.has_platform_role("platform_super_admin"):
            raise BadRequestError(
                code="project_scope_required",
                message="project_id is required for assistant schema access",
            )

        return self._schema_provider.build_schema(normalized_graph_id)
