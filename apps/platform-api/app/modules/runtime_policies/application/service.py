from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.core.identifiers import parse_uuid
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository
from app.modules.runtime_catalog.infra import SqlAlchemyRuntimeCatalogRepository
from app.modules.runtime_policies.application.contracts import (
    RuntimeGraphPolicyList,
    RuntimeModelPolicyList,
    RuntimeToolPolicyList,
    UpsertRuntimeGraphPolicyCommand,
    UpsertRuntimeModelPolicyCommand,
    UpsertRuntimeToolPolicyCommand,
)
from app.modules.runtime_policies.domain import (
    RuntimeGraphPolicyItem,
    RuntimeGraphPolicyValue,
    RuntimeModelPolicyItem,
    RuntimeModelPolicyValue,
    RuntimeToolPolicyItem,
    RuntimeToolPolicyValue,
)
from app.modules.runtime_policies.infra import SqlAlchemyRuntimePolicyRepository


class RuntimePolicyOverlayService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        runtime_base_url: str,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_id = runtime_base_url.rstrip("/")
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def build_delegation_policy(self, *, project_id: str) -> dict[str, object]:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        with session_factory() as session:
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(session)
            models = catalog_repository.list_models(runtime_id=self._runtime_id)
            tools = catalog_repository.list_tools(runtime_id=self._runtime_id)
            model_policies = {
                str(item.model_catalog_id): item
                for item in policy_repository.list_model_policies(project_id=project_uuid)
            }
            tool_policies = {
                str(item.tool_catalog_id): item
                for item in policy_repository.list_tool_policies(project_id=project_uuid)
            }

            allowed_model_ids = sorted(
                item.model_key
                for item in models
                if item.sync_status == "ready"
                and (
                    str(item.id) not in model_policies
                    or model_policies[str(item.id)].is_enabled
                )
            )
            allowed_tool_names = sorted(
                item.tool_key
                for item in tools
                if item.sync_status == "ready"
                and (
                    str(item.id) not in tool_policies
                    or tool_policies[str(item.id)].is_enabled
                )
            )

        if not allowed_model_ids:
            raise ServiceUnavailableError(
                code="runtime_policy_not_configured",
                message="No enabled runtime model is available for this project",
            )

        revision_payload = {
            "runtime_id": self._runtime_id,
            "models": allowed_model_ids,
            "tools": allowed_tool_names,
        }
        revision = "platform-policy-" + hashlib.sha256(
            json.dumps(revision_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:32]
        return {
            "version": revision,
            "allowed_model_ids": allowed_model_ids,
            "allowed_tool_names": allowed_tool_names,
        }

    def _require_project_access(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        write: bool,
    ) -> UUID:
        permission = PermissionCode.PROJECT_RUNTIME_WRITE if write else PermissionCode.PROJECT_RUNTIME_READ
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=permission, project_id=project_id),
        )
        return parse_uuid(project_id, code="invalid_project_id")

    @staticmethod
    def _ensure_project_exists(uow: SqlAlchemyUnitOfWork, project_uuid: UUID) -> None:
        repository = SqlAlchemyProjectsRepository(uow.session)
        project = repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")

    async def list_graph_policies(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeGraphPolicyList:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(actor=actor, project_id=project_id, write=False)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            self._ensure_project_exists(uow, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(uow.session)
            catalog_rows = catalog_repository.list_graphs(runtime_id=self._runtime_id)
            policy_rows = {
                str(item.graph_catalog_id): item
                for item in policy_repository.list_graph_policies(project_id=project_uuid)
            }
            items = [
                RuntimeGraphPolicyItem(
                    catalog_id=str(row.id),
                    graph_id=row.graph_key,
                    display_name=row.display_name or row.graph_key,
                    description=row.description or "",
                    source_type=row.source_type,
                    sync_status=row.sync_status,
                    last_synced_at=row.last_synced_at,
                    policy=RuntimeGraphPolicyValue(
                        is_enabled=policy_rows.get(str(row.id)).is_enabled
                        if policy_rows.get(str(row.id))
                        else True,
                        display_order=policy_rows.get(str(row.id)).display_order
                        if policy_rows.get(str(row.id))
                        else None,
                        note=policy_rows.get(str(row.id)).note if policy_rows.get(str(row.id)) else None,
                    ),
                )
                for row in catalog_rows
            ]
            return RuntimeGraphPolicyList(items=items, total=len(items))

    async def upsert_graph_policy(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        catalog_id: str,
        command: UpsertRuntimeGraphPolicyCommand,
    ) -> RuntimeGraphPolicyValue:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(actor=actor, project_id=project_id, write=True)
        catalog_uuid = parse_uuid(catalog_id, code="invalid_catalog_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            self._ensure_project_exists(uow, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            if catalog_repository.get_graph_by_id(catalog_uuid) is None:
                raise NotFoundError(message="Graph catalog not found", code="graph_catalog_not_found")
            policy_repository = SqlAlchemyRuntimePolicyRepository(uow.session)
            row = policy_repository.upsert_graph_policy(
                project_id=project_uuid,
                graph_catalog_id=catalog_uuid,
                is_enabled=command.is_enabled,
                display_order=command.display_order,
                note=command.note,
                updated_by=actor.user_id,
            )
            return RuntimeGraphPolicyValue(
                is_enabled=row.is_enabled,
                display_order=row.display_order,
                note=row.note,
                updated_at=row.updated_at,
            )

    async def list_tool_policies(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeToolPolicyList:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(actor=actor, project_id=project_id, write=False)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            self._ensure_project_exists(uow, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(uow.session)
            catalog_rows = catalog_repository.list_tools(runtime_id=self._runtime_id)
            policy_rows = {
                str(item.tool_catalog_id): item
                for item in policy_repository.list_tool_policies(project_id=project_uuid)
            }
            items = [
                RuntimeToolPolicyItem(
                    catalog_id=str(row.id),
                    tool_key=row.tool_key,
                    name=row.name,
                    source=row.source or "",
                    description=row.description or "",
                    sync_status=row.sync_status,
                    last_synced_at=row.last_synced_at,
                    policy=RuntimeToolPolicyValue(
                        is_enabled=policy_rows.get(str(row.id)).is_enabled
                        if policy_rows.get(str(row.id))
                        else True,
                        display_order=policy_rows.get(str(row.id)).display_order
                        if policy_rows.get(str(row.id))
                        else None,
                        note=policy_rows.get(str(row.id)).note if policy_rows.get(str(row.id)) else None,
                    ),
                )
                for row in catalog_rows
            ]
            return RuntimeToolPolicyList(items=items, total=len(items))

    async def upsert_tool_policy(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        catalog_id: str,
        command: UpsertRuntimeToolPolicyCommand,
    ) -> RuntimeToolPolicyValue:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(actor=actor, project_id=project_id, write=True)
        catalog_uuid = parse_uuid(catalog_id, code="invalid_catalog_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            self._ensure_project_exists(uow, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            if catalog_repository.get_tool_by_id(catalog_uuid) is None:
                raise NotFoundError(message="Tool catalog not found", code="tool_catalog_not_found")
            policy_repository = SqlAlchemyRuntimePolicyRepository(uow.session)
            row = policy_repository.upsert_tool_policy(
                project_id=project_uuid,
                tool_catalog_id=catalog_uuid,
                is_enabled=command.is_enabled,
                display_order=command.display_order,
                note=command.note,
                updated_by=actor.user_id,
            )
            return RuntimeToolPolicyValue(
                is_enabled=row.is_enabled,
                display_order=row.display_order,
                note=row.note,
                updated_at=row.updated_at,
            )

    async def list_model_policies(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeModelPolicyList:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(actor=actor, project_id=project_id, write=False)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            self._ensure_project_exists(uow, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(uow.session)
            catalog_rows = catalog_repository.list_models(runtime_id=self._runtime_id)
            policy_rows = {
                str(item.model_catalog_id): item
                for item in policy_repository.list_model_policies(project_id=project_uuid)
            }
            items = [
                RuntimeModelPolicyItem(
                    catalog_id=str(row.id),
                    model_id=row.model_key,
                    display_name=row.display_name or row.model_key,
                    is_default_runtime=row.is_default_runtime,
                    sync_status=row.sync_status,
                    last_synced_at=row.last_synced_at,
                    policy=RuntimeModelPolicyValue(
                        is_enabled=policy_rows.get(str(row.id)).is_enabled
                        if policy_rows.get(str(row.id))
                        else True,
                        is_default_for_project=policy_rows.get(str(row.id)).is_default_for_project
                        if policy_rows.get(str(row.id))
                        else False,
                        temperature_default=float(policy_rows.get(str(row.id)).temperature_default)
                        if policy_rows.get(str(row.id))
                        and policy_rows.get(str(row.id)).temperature_default is not None
                        else None,
                        note=policy_rows.get(str(row.id)).note if policy_rows.get(str(row.id)) else None,
                    ),
                )
                for row in catalog_rows
            ]
            return RuntimeModelPolicyList(items=items, total=len(items))

    async def upsert_model_policy(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        catalog_id: str,
        command: UpsertRuntimeModelPolicyCommand,
    ) -> RuntimeModelPolicyValue:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(actor=actor, project_id=project_id, write=True)
        catalog_uuid = parse_uuid(catalog_id, code="invalid_catalog_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            self._ensure_project_exists(uow, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            if catalog_repository.get_model_by_id(catalog_uuid) is None:
                raise NotFoundError(message="Model catalog not found", code="model_catalog_not_found")
            policy_repository = SqlAlchemyRuntimePolicyRepository(uow.session)
            row = policy_repository.upsert_model_policy(
                project_id=project_uuid,
                model_catalog_id=catalog_uuid,
                is_enabled=command.is_enabled,
                is_default_for_project=command.is_default_for_project,
                temperature_default=Decimal(str(command.temperature_default))
                if command.temperature_default is not None
                else None,
                note=command.note,
                updated_by=actor.user_id,
            )
            return RuntimeModelPolicyValue(
                is_enabled=row.is_enabled,
                is_default_for_project=row.is_default_for_project,
                temperature_default=float(row.temperature_default) if row.temperature_default is not None else None,
                note=row.note,
                updated_at=row.updated_at,
            )
