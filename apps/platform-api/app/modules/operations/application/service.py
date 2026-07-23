from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from time import monotonic
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import BadRequestError, ConflictError, NotAuthenticatedError, NotFoundError, ServiceUnavailableError
from app.core.identifiers import parse_uuid
from app.modules.audit.domain import AuditResult
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.operations.application.audit import write_operation_audit_event
from app.modules.operations.application.artifacts import LocalOperationArtifactStore, OperationArtifact
from app.modules.operations.application.contracts import (
    BulkArchiveOperationsCommand,
    BulkCancelOperationsCommand,
    BulkRestoreOperationsCommand,
    CreateOperationCommand,
    ListOperationsQuery,
)
from app.modules.operations.application.execution import with_actor_snapshot
from app.modules.operations.application.ports import OperationDispatcherProtocol, StoredOperation
from app.modules.operations.domain import (
    OperationArtifactCleanupResult,
    OperationBulkMutationResult,
    OperationPage,
    OperationStatus,
    OperationView,
)
from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository

_TERMINAL_OPERATION_STATUSES = {
    OperationStatus.SUCCEEDED,
    OperationStatus.FAILED,
    OperationStatus.CANCELLED,
}

_PROJECT_OPERATION_SUBMIT_PERMISSIONS: dict[str, PermissionCode] = {
    "knowledge.documents.scan": PermissionCode.PROJECT_KNOWLEDGE_WRITE,
    "knowledge.documents.clear": PermissionCode.PROJECT_KNOWLEDGE_ADMIN,
}


def _normalize_str(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _require_actor_identity(actor: ActorContext) -> str:
    requested_by = _normalize_str(actor.user_id) or _normalize_str(actor.subject)
    if requested_by:
        return requested_by
    raise NotAuthenticatedError()


class OperationsService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        dispatcher: OperationDispatcherProtocol | None = None,
        artifact_store: LocalOperationArtifactStore | None = None,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._artifact_store = artifact_store
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _require_read_access(self, *, actor: ActorContext, project_id: str | None) -> None:
        if project_id:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_OPERATION_READ,
                    project_id=project_id,
                ),
            )
            return

        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_OPERATION_READ,
            ),
        )

    def _require_write_access(self, *, actor: ActorContext, project_id: str | None) -> None:
        if project_id:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_OPERATION_WRITE,
                    project_id=project_id,
                ),
            )
            return

        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_OPERATION_WRITE,
            ),
        )

    def _require_submit_access(
        self,
        *,
        actor: ActorContext,
        project_id: str | None,
        kind: str,
    ) -> None:
        self._require_write_access(actor=actor, project_id=project_id)
        if not project_id:
            return

        extra_permission = _PROJECT_OPERATION_SUBMIT_PERMISSIONS.get(kind)
        if extra_permission is None:
            return

        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=extra_permission,
                project_id=project_id,
            ),
        )

    def _operation_view(self, item: StoredOperation) -> OperationView:
        metadata = dict(item.metadata)
        metadata.pop("actor_snapshot", None)
        return OperationView(
            id=item.id,
            kind=item.kind,
            status=item.status,
            requested_by=item.requested_by,
            tenant_id=item.tenant_id,
            project_id=item.project_id,
            idempotency_key=item.idempotency_key,
            input_payload=dict(item.input_payload),
            result_payload=dict(item.result_payload),
            error_payload=dict(item.error_payload),
            metadata=metadata,
            cancel_requested_at=item.cancel_requested_at,
            started_at=item.started_at,
            finished_at=item.finished_at,
            archived_at=item.archived_at,
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
        repository = SqlAlchemyProjectsRepository(uow.session)
        project = repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")

    async def submit_operation(
        self,
        *,
        actor: ActorContext,
        command: CreateOperationCommand,
    ) -> OperationView:
        session_factory = self._require_session_factory()
        requested_by = _require_actor_identity(actor)
        project_id = _normalize_str(command.project_id)
        idempotency_key = _normalize_str(command.idempotency_key)
        kind = command.kind.strip()
        metadata = with_actor_snapshot(metadata=command.metadata, actor=actor)

        self._require_submit_access(
            actor=actor,
            project_id=project_id,
            kind=kind,
        )

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            if project_id:
                self._require_project_exists(uow=uow, project_id=project_id)

            repository = SqlAlchemyOperationsRepository(uow.session)
            if idempotency_key:
                existing = repository.get_by_idempotency_key(
                    requested_by=requested_by,
                    idempotency_key=idempotency_key,
                )
                if existing is not None:
                    return self._operation_view(existing)

            operation = repository.create_operation(
                kind=kind,
                status=OperationStatus.SUBMITTED,
                requested_by=requested_by,
                tenant_id=None,
                project_id=project_id,
                idempotency_key=idempotency_key,
                input_payload=dict(command.input_payload),
                metadata=metadata,
            )
            if self._dispatcher is not None:
                await self._dispatcher.dispatch(operation=operation)

        write_operation_audit_event(
            session_factory=session_factory,
            action="operation.submitted",
            operation=operation,
            actor=actor,
            result=AuditResult.SUCCESS,
            status_code=202,
        )
        return self._operation_view(operation)

    async def get_operation(
        self,
        *,
        actor: ActorContext,
        operation_id: str,
    ) -> OperationView:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            operation = repository.get_by_id(operation_id)
            if operation is None:
                raise NotFoundError(message="Operation not found", code="operation_not_found")
            self._require_read_access(actor=actor, project_id=operation.project_id)
            return self._operation_view(operation)

    async def list_operations(
        self,
        *,
        actor: ActorContext,
        query: ListOperationsQuery,
    ) -> OperationPage:
        session_factory = self._require_session_factory()
        project_id = _normalize_str(query.project_id)
        self._require_read_access(actor=actor, project_id=project_id)

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            if project_id:
                self._require_project_exists(uow=uow, project_id=project_id)

            repository = SqlAlchemyOperationsRepository(uow.session)
            items, total = repository.list_operations(
                project_id=project_id,
                kind=_normalize_str(query.kind),
                kinds=tuple(_normalize_str(item) for item in query.kinds if _normalize_str(item)),
                status=query.status.value if query.status else None,
                statuses=tuple(item.value for item in query.statuses),
                requested_by=_normalize_str(query.requested_by),
                archive_scope=query.archive_scope.value,
                limit=query.limit,
                offset=query.offset,
            )
            return OperationPage(
                items=[self._operation_view(item) for item in items],
                total=total,
            )

    async def watch_operations(
        self,
        *,
        actor: ActorContext,
        query: ListOperationsQuery,
        poll_interval_seconds: float = 2.0,
        heartbeat_interval_seconds: float = 15.0,
        initial_signature: str | None = None,
    ) -> AsyncIterator[OperationPage | None]:
        last_signature = initial_signature
        last_emitted_at = monotonic()

        while True:
            page = await self.list_operations(actor=actor, query=query)
            signature = build_operation_page_signature(page)
            now = monotonic()
            if signature != last_signature:
                last_signature = signature
                last_emitted_at = now
                yield page
            elif now - last_emitted_at >= heartbeat_interval_seconds:
                last_emitted_at = now
                yield None
            await asyncio.sleep(poll_interval_seconds)

    async def cancel_operation(
        self,
        *,
        actor: ActorContext,
        operation_id: str,
    ) -> OperationView:
        session_factory = self._require_session_factory()
        cancelled_at = datetime.now(timezone.utc)

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            operation = repository.get_by_id(operation_id)
            if operation is None:
                raise NotFoundError(message="Operation not found", code="operation_not_found")

            self._require_write_access(actor=actor, project_id=operation.project_id)
            if operation.status in _TERMINAL_OPERATION_STATUSES:
                raise ConflictError(
                    code="operation_already_finished",
                    message=f"Operation already {operation.status.value}",
                )

            updated = repository.update_status(
                operation_id=operation_id,
                status=OperationStatus.CANCELLED,
                cancel_requested_at=cancelled_at,
                finished_at=cancelled_at,
            )
            if updated is None:
                raise NotFoundError(message="Operation not found", code="operation_not_found")

        write_operation_audit_event(
            session_factory=session_factory,
            action="operation.cancelled",
            operation=updated,
            actor=actor,
            result=AuditResult.CANCELLED,
            status_code=200,
        )
        return self._operation_view(updated)

    async def bulk_cancel_operations(
        self,
        *,
        actor: ActorContext,
        command: BulkCancelOperationsCommand,
    ) -> OperationBulkMutationResult:
        session_factory = self._require_session_factory()
        operations = await self._collect_operations_for_mutation(
            actor=actor,
            operation_ids=command.operation_ids,
            require_write=True,
        )

        cancel_requested_at = datetime.now(timezone.utc)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            updated, skipped_ids = repository.bulk_cancel_operations(
                operation_ids=tuple(item.id for item in operations),
                cancel_requested_at=cancel_requested_at,
                terminal_statuses=tuple(status.value for status in _TERMINAL_OPERATION_STATUSES),
            )

        return OperationBulkMutationResult(
            requested_count=len(command.operation_ids),
            updated_count=len(updated),
            skipped_count=len(skipped_ids),
            updated=[self._operation_view(item) for item in updated],
            skipped_ids=skipped_ids,
        )

    async def bulk_archive_operations(
        self,
        *,
        actor: ActorContext,
        command: BulkArchiveOperationsCommand,
    ) -> OperationBulkMutationResult:
        session_factory = self._require_session_factory()
        operations = await self._collect_operations_for_mutation(
            actor=actor,
            operation_ids=command.operation_ids,
            require_write=True,
        )

        archived_at = datetime.now(timezone.utc)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            updated, skipped_ids = repository.bulk_archive_operations(
                operation_ids=tuple(item.id for item in operations),
                archived_at=archived_at,
                terminal_statuses=tuple(status.value for status in _TERMINAL_OPERATION_STATUSES),
            )

        return OperationBulkMutationResult(
            requested_count=len(command.operation_ids),
            updated_count=len(updated),
            skipped_count=len(skipped_ids),
            updated=[self._operation_view(item) for item in updated],
            skipped_ids=skipped_ids,
        )

    async def bulk_restore_operations(
        self,
        *,
        actor: ActorContext,
        command: BulkRestoreOperationsCommand,
    ) -> OperationBulkMutationResult:
        session_factory = self._require_session_factory()
        operations = await self._collect_operations_for_mutation(
            actor=actor,
            operation_ids=command.operation_ids,
            require_write=True,
        )

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            updated, skipped_ids = repository.bulk_restore_operations(
                operation_ids=tuple(item.id for item in operations),
            )

        return OperationBulkMutationResult(
            requested_count=len(command.operation_ids),
            updated_count=len(updated),
            skipped_count=len(skipped_ids),
            updated=[self._operation_view(item) for item in updated],
            skipped_ids=skipped_ids,
        )

    async def get_operation_artifact(
        self,
        *,
        actor: ActorContext,
        operation_id: str,
    ) -> OperationArtifact:
        session_factory = self._require_session_factory()
        if self._artifact_store is None:
            raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            operation = repository.get_by_id(operation_id)
            if operation is None:
                raise NotFoundError(message="Operation not found", code="operation_not_found")
            self._require_read_access(actor=actor, project_id=operation.project_id)

            artifact_payload = operation.result_payload.get("_artifact")
            if not isinstance(artifact_payload, dict):
                raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")
            return self._artifact_store.resolve(artifact_payload)

    async def cleanup_expired_artifacts(
        self,
        *,
        actor: ActorContext,
        limit: int,
    ) -> OperationArtifactCleanupResult:
        if self._artifact_store is None:
            raise ServiceUnavailableError(
                code="operation_artifact_store_not_enabled",
                message="Operation artifact store is not enabled",
            )
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_OPERATION_WRITE,
            ),
        )
        summary = self._artifact_store.cleanup_expired(limit=limit)
        return OperationArtifactCleanupResult(
            storage_backend=summary.storage_backend,
            retention_hours=summary.retention_hours,
            scanned_count=summary.scanned_count,
            removed_count=summary.removed_count,
            missing_count=summary.missing_count,
            bytes_reclaimed=summary.bytes_reclaimed,
        )

    async def _collect_operations_for_mutation(
        self,
        *,
        actor: ActorContext,
        operation_ids: tuple[str, ...],
        require_write: bool,
    ) -> list[StoredOperation]:
        session_factory = self._require_session_factory()
        operations: list[StoredOperation] = []
        seen_ids: set[str] = set()

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            for operation_id in operation_ids:
                normalized_id = operation_id.strip()
                if not normalized_id or normalized_id in seen_ids:
                    continue
                seen_ids.add(normalized_id)
                operation = repository.get_by_id(normalized_id)
                if operation is None:
                    continue
                if require_write:
                    self._require_write_access(actor=actor, project_id=operation.project_id)
                else:
                    self._require_read_access(actor=actor, project_id=operation.project_id)
                operations.append(operation)
        return operations


def build_operation_page_signature(page: OperationPage) -> str:
    normalized = {
        "total": page.total,
        "items": [item.model_dump(mode="json") for item in page.items],
    }
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()
