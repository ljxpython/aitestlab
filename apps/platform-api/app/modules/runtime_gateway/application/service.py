from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UpstreamServiceError,
)
from app.core.identifiers import parse_uuid
from app.core.normalization import clean_str, ensure_dict
from app.core.runtime_contract import (
    PROJECT_SCOPE_ALIAS_KEYS,
    normalize_protocol_v2_command,
    normalize_protocol_v2_event_request,
    normalize_runtime_payload,
    strip_keys,
)
from app.modules.assistants.infra.sqlalchemy.repository import SqlAlchemyAssistantsRepository
from app.modules.audit.domain import AuditResult
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.operations.application.audit import write_operation_audit_event
from app.modules.operations.domain import OperationStatus
from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository
from app.modules.runtime_catalog.infra.sqlalchemy.repository import (
    SqlAlchemyRuntimeCatalogRepository,
)
from app.modules.runtime_gateway.application.ports import RuntimeGatewayUpstreamProtocol
from app.modules.runtime_gateway.infra.sqlalchemy.repository import (
    SqlAlchemyDurableRunsRepository,
    StoredDurableRun,
)
from app.modules.runtime_policies.infra import SqlAlchemyRuntimePolicyRepository

_THREAD_PROJECT_ID_KEYS = PROJECT_SCOPE_ALIAS_KEYS
_THREAD_GRAPH_ID_KEYS = ("graph_id", "graphId")
_DURABLE_RUN_OPERATION_KIND = "runtime.durable_run"


def _request_digest(command: dict[str, Any]) -> str:
    encoded = json.dumps(command, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _normalize_idempotency_key(value: str | None) -> str:
    normalized = clean_str(value)
    if not normalized:
        raise BadRequestError(
            code="idempotency_key_required",
            message="Idempotency-Key header is required for run.start",
        )
    if len(normalized) > 128:
        raise BadRequestError(
            code="invalid_idempotency_key",
            message="Idempotency-Key header must not exceed 128 characters",
        )
    return normalized


def _run_id_from_command_result(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    candidate = result.get("run_id")
    if not candidate and isinstance(result.get("result"), dict):
        candidate = result["result"].get("run_id")
    return clean_str(candidate)


def _terminal_operation_status(snapshot: Any) -> OperationStatus | None:
    if not isinstance(snapshot, dict):
        return None
    status = clean_str(snapshot.get("status"))
    if status in {"success", "succeeded", "completed"}:
        return OperationStatus.SUCCEEDED
    if status in {"error", "failed", "timeout"}:
        return OperationStatus.FAILED
    if status in {"cancelled", "canceled", "interrupted"}:
        return OperationStatus.CANCELLED
    return None


def _interrupt_ids(state: Any) -> set[str]:
    if not isinstance(state, dict):
        return set()
    tasks = state.get("tasks")
    if not isinstance(tasks, list):
        return set()
    return {
        interrupt_id
        for task in tasks
        if isinstance(task, dict)
        for interrupt in (task.get("interrupts") or [])
        if isinstance(interrupt, dict)
        for interrupt_id in [clean_str(interrupt.get("id"))]
        if interrupt_id
    }


def _normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return ensure_dict(payload)


def _thread_metadata(thread: dict[str, Any]) -> dict[str, Any]:
    metadata = thread.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _thread_project_id(thread: dict[str, Any]) -> str | None:
    metadata = _thread_metadata(thread)
    for key in _THREAD_PROJECT_ID_KEYS:
        value = clean_str(metadata.get(key))
        if value:
            return value
    return None


def _without_project_scope_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    return strip_keys(payload, _THREAD_PROJECT_ID_KEYS)


def _thread_graph_id(thread: dict[str, Any]) -> str | None:
    metadata = _thread_metadata(thread)
    for key in _THREAD_GRAPH_ID_KEYS:
        value = clean_str(metadata.get(key))
        if value:
            return value
    if clean_str(metadata.get("target_type")) == "graph":
        legacy_graph_id = clean_str(metadata.get("assistant_id"))
        if legacy_graph_id:
            return legacy_graph_id
    return None


def _promote_thread_graph_id(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    if clean_str(next_payload.get("graph_id")):
        return next_payload

    metadata = ensure_dict(next_payload.get("metadata"))
    graph_id = clean_str(metadata.get("graph_id"))
    if not graph_id and clean_str(metadata.get("target_type")) == "graph":
        graph_id = clean_str(metadata.get("assistant_id"))

    if graph_id:
        next_payload["graph_id"] = graph_id

    return next_payload


class RuntimeGatewayService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: RuntimeGatewayUpstreamProtocol,
        runtime_base_url: str = "",
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._runtime_id = runtime_base_url.rstrip("/")
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _authorize(self, *, actor: ActorContext, project_id: str, write: bool) -> None:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=(
                    PermissionCode.PROJECT_RUNTIME_WRITE
                    if write
                    else PermissionCode.PROJECT_RUNTIME_READ
                ),
                project_id=project_id,
            ),
        )

    def _require_project_exists(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        project_id: str,
    ) -> UUID:
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        repository = SqlAlchemyProjectsRepository(uow.session)
        project = repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")
        return project_uuid

    async def _prepare_project_scope(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        write: bool,
    ) -> UUID:
        self._authorize(actor=actor, project_id=project_id, write=write)
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            return self._require_project_exists(uow=uow, project_id=project_id)

    def _inject_project_metadata(
        self,
        *,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        next_payload = _normalize_payload(payload)
        metadata = next_payload.get("metadata")
        metadata_dict = (
            _without_project_scope_aliases(dict(metadata))
            if isinstance(metadata, dict)
            else {}
        )
        metadata_dict["project_id"] = project_id
        next_payload["metadata"] = metadata_dict
        return next_payload

    def _inject_project_scope(
        self,
        *,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return normalize_runtime_payload(payload=payload, project_id=project_id)

    async def _inject_project_default_model(
        self,
        *,
        project_id: str,
        payload: dict[str, Any],
        default_model_id: str | None = None,
    ) -> dict[str, Any]:
        context = ensure_dict(payload.get("context"))
        if clean_str(context.get("model_id")):
            return payload
        if default_model_id is None:
            default_model_id = await self._project_default_model_id(project_id=project_id)
        if not default_model_id:
            return payload

        next_payload = dict(payload)
        next_payload["context"] = {**context, "model_id": default_model_id}
        return next_payload

    async def _project_default_model_id(self, *, project_id: str) -> str | None:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimePolicyRepository(uow.session)
            return repository.get_default_model_key(
                project_id=project_uuid,
                runtime_id=self._runtime_id,
            )

    async def _assert_runtime_options_allowed(
        self,
        *,
        project_id: str,
        options: dict[str, Any],
    ) -> None:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(uow.session)

            model_policies = {
                str(item.model_catalog_id): item
                for item in policy_repository.list_model_policies(
                    project_id=project_uuid
                )
            }
            allowed_models = {
                item.model_key
                for item in catalog_repository.list_models(runtime_id=self._runtime_id)
                if str(item.id) not in model_policies
                or model_policies[str(item.id)].is_enabled
            }
            requested_model = clean_str(options.get("model_id"))
            if requested_model and requested_model not in allowed_models:
                raise ForbiddenError(
                    code="runtime_model_denied",
                    message="Requested runtime model is not enabled for this project",
                )

            tool_policies = {
                str(item.tool_catalog_id): item
                for item in policy_repository.list_tool_policies(project_id=project_uuid)
            }
            allowed_tools = {
                item.tool_key
                for item in catalog_repository.list_tools(runtime_id=self._runtime_id)
                if str(item.id) not in tool_policies
                or tool_policies[str(item.id)].is_enabled
            }
            requested_tools = {
                name
                for name in (
                    clean_str(item)
                    for item in options.get("tools", [])
                    if isinstance(item, str)
                )
                if name
            }
            denied_tools = sorted(requested_tools - allowed_tools)
            if denied_tools:
                raise ForbiddenError(
                    code="runtime_tools_denied",
                    message="Requested runtime tools are not enabled for this project",
                )

    def _assert_thread_project_scope(
        self,
        *,
        project_id: str,
        thread: dict[str, Any],
    ) -> None:
        thread_project_id = _thread_project_id(thread)
        if thread_project_id != project_id:
            raise ForbiddenError(
                code="thread_project_denied",
                message="thread_project_denied",
            )

    async def _load_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        write: bool,
    ) -> dict[str, Any]:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=write)
        thread = await self._upstream.get_thread(thread_id)
        self._assert_thread_project_scope(project_id=project_id, thread=thread)
        return thread

    async def _assistant_belongs_project(
        self,
        *,
        project_id: str,
        assistant_id: str,
    ) -> bool:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            project_uuid = self._require_project_exists(uow=uow, project_id=project_id)
            repository = SqlAlchemyAssistantsRepository(uow.session)
            item = repository.get_by_project_and_langgraph_assistant_id(
                project_id=project_uuid,
                langgraph_assistant_id=assistant_id,
            )
            return item is not None

    async def _assert_runtime_target_allowed(
        self,
        *,
        project_id: str,
        assistant_id: str,
        thread: dict[str, Any] | None = None,
    ) -> None:
        normalized_assistant_id = clean_str(assistant_id)
        if not normalized_assistant_id:
            raise BadRequestError(
                message="assistant_id is required",
                code="assistant_id_required",
            )

        if await self._assistant_belongs_project(
            project_id=project_id,
            assistant_id=normalized_assistant_id,
        ):
            return

        if thread is not None and _thread_graph_id(thread) == normalized_assistant_id:
            return

        raise ForbiddenError(
            code="runtime_target_denied",
            message="runtime_target_denied",
        )

    async def _reserve_durable_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        command: dict[str, Any],
        idempotency_key: str,
    ) -> StoredDurableRun:
        session_factory = self._require_session_factory()
        digest = _request_digest(command)
        try:
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                runs = SqlAlchemyDurableRunsRepository(uow.session)
                existing = runs.get_by_idempotency_key(
                    project_id=project_id,
                    thread_id=thread_id,
                    idempotency_key=idempotency_key,
                )
                if existing is not None:
                    return self._reuse_or_reject_durable_run(existing=existing, digest=digest)

                active = runs.get_active(project_id=project_id, thread_id=thread_id)
                if active is not None:
                    raise ConflictError(
                        code="thread_active_run_conflict",
                        message="The thread already has an active Durable Run",
                    )

                requested_by = clean_str(getattr(actor, "user_id", None)) or clean_str(
                    getattr(actor, "subject", None)
                )
                if not requested_by:
                    raise ServiceUnavailableError(
                        code="runtime_actor_identity_missing",
                        message="Authenticated actor identity is required",
                    )
                operation = SqlAlchemyOperationsRepository(uow.session).create_operation(
                    kind=_DURABLE_RUN_OPERATION_KIND,
                    status=OperationStatus.SUBMITTED,
                    requested_by=requested_by,
                    tenant_id=None,
                    project_id=project_id,
                    idempotency_key=None,
                    input_payload={
                        "thread_id": thread_id,
                        "assistant_id": clean_str(command["params"].get("assistant_id")) or "",
                    },
                    metadata={"durable_run": True},
                )
                durable_run = runs.create(
                    project_id=project_id,
                    thread_id=thread_id,
                    idempotency_key=idempotency_key,
                    request_digest=digest,
                    operation_id=operation.id,
                )
        except IntegrityError:
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                runs = SqlAlchemyDurableRunsRepository(uow.session)
                existing = runs.get_by_idempotency_key(
                    project_id=project_id,
                    thread_id=thread_id,
                    idempotency_key=idempotency_key,
                )
                if existing is not None:
                    return self._reuse_or_reject_durable_run(existing=existing, digest=digest)
            raise ConflictError(
                code="thread_active_run_conflict",
                message="The thread already has an active Durable Run",
            )

        write_operation_audit_event(
            session_factory=session_factory,
            action="runtime.run.submitted",
            operation=operation,
            actor=actor,
            result=AuditResult.SUCCESS,
            status_code=202,
            metadata={"thread_id": thread_id, "durable_run_id": durable_run.id},
        )
        return durable_run

    @staticmethod
    def _reuse_or_reject_durable_run(*, existing: StoredDurableRun, digest: str) -> StoredDurableRun:
        if existing.request_digest != digest:
            raise ConflictError(
                code="idempotency_key_conflict",
                message="Idempotency-Key was already used with a different request",
            )
        if existing.run_id:
            return existing
        raise ConflictError(
            code="run_start_in_progress",
            message="The original run.start request is still being reconciled",
        )

    async def _mark_durable_run_started(
        self,
        *,
        actor: ActorContext,
        durable_run: StoredDurableRun,
        run_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            started = SqlAlchemyDurableRunsRepository(uow.session).mark_started(
                durable_run_id=durable_run.id,
                run_id=run_id,
            )
            if started is None:
                raise ServiceUnavailableError(
                    code="durable_run_record_missing",
                    message="Durable Run record disappeared during start",
                )
            operation = SqlAlchemyOperationsRepository(uow.session).update_status(
                operation_id=durable_run.operation_id,
                status=OperationStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )
        if operation is not None:
            write_operation_audit_event(
                session_factory=session_factory,
                action="runtime.run.started",
                operation=operation,
                actor=actor,
                result=AuditResult.SUCCESS,
                status_code=202,
                metadata={"thread_id": durable_run.thread_id, "run_id": run_id},
            )

    async def _assert_active_interrupt(
        self,
        *,
        project_id: str,
        thread_id: str,
        interrupt_id: str,
    ) -> str:
        session_factory = self._require_session_factory()
        state = await self._upstream.get_thread_state(thread_id, {})
        interrupt_ids = _interrupt_ids(state)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            runs = SqlAlchemyDurableRunsRepository(uow.session)
            active_run = runs.get_active(
                project_id=project_id,
                thread_id=thread_id,
            )
            if active_run is None or not active_run.run_id:
                raise ConflictError(
                    code="active_durable_run_not_found",
                    message="input.respond requires an active Durable Run",
                )
            if interrupt_id not in interrupt_ids:
                raise ConflictError(
                    code="interrupt_not_active",
                    message="The interrupt does not belong to the active Durable Run",
                )
            runs.sync_active_interrupts(
                project_id=project_id,
                thread_id=thread_id,
                run_id=active_run.run_id,
                interrupt_ids=interrupt_ids,
            )
            if not runs.is_interrupt_active(
                project_id=project_id,
                thread_id=thread_id,
                run_id=active_run.run_id,
                interrupt_id=interrupt_id,
            ):
                raise ConflictError(
                    code="interrupt_not_active",
                    message="The interrupt has already been resolved",
                )
            return active_run.run_id

    async def _mark_interrupt_resolved(
        self,
        *,
        project_id: str,
        thread_id: str,
        run_id: str,
        interrupt_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            SqlAlchemyDurableRunsRepository(uow.session).mark_interrupt_resolved(
                project_id=project_id,
                thread_id=thread_id,
                run_id=run_id,
                interrupt_id=interrupt_id,
            )

    async def _sync_durable_run_terminal_state(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
        snapshot: Any,
    ) -> None:
        operation_status = _terminal_operation_status(snapshot)
        if operation_status is None:
            return
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            durable_run = SqlAlchemyDurableRunsRepository(uow.session).get_by_run_id(
                project_id=project_id,
                thread_id=thread_id,
                run_id=run_id,
            )
            if durable_run is None or not durable_run.active:
                return
            SqlAlchemyDurableRunsRepository(uow.session).mark_terminal(
                durable_run_id=durable_run.id,
                status=operation_status.value,
            )
            SqlAlchemyDurableRunsRepository(uow.session).mark_run_interrupts_resolved(
                run_id=run_id,
            )
            operation = SqlAlchemyOperationsRepository(uow.session).update_status(
                operation_id=durable_run.operation_id,
                status=operation_status,
                finished_at=datetime.now(timezone.utc),
            )
        if operation is not None:
            if operation_status is OperationStatus.SUCCEEDED:
                result = AuditResult.SUCCESS
            elif operation_status is OperationStatus.CANCELLED:
                result = AuditResult.CANCELLED
            else:
                result = AuditResult.FAILED
            write_operation_audit_event(
                session_factory=session_factory,
                action=f"runtime.run.{operation_status.value}",
                operation=operation,
                actor=actor,
                result=result,
                status_code=200,
                metadata={"thread_id": thread_id, "run_id": run_id},
            )

    async def _mark_durable_run_cancel_requested(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            durable_run = SqlAlchemyDurableRunsRepository(uow.session).get_by_run_id(
                project_id=project_id,
                thread_id=thread_id,
                run_id=run_id,
            )
            if durable_run is None or not durable_run.active:
                return
            operations = SqlAlchemyOperationsRepository(uow.session)
            operation = operations.get_by_id(durable_run.operation_id)
            if operation is None:
                raise ServiceUnavailableError(
                    code="durable_run_operation_missing",
                    message="Durable Run operation disappeared during cancellation",
                )
            if operation.cancel_requested_at is not None:
                return
            operation = operations.update_status(
                operation_id=operation.id,
                status=operation.status,
                cancel_requested_at=datetime.now(timezone.utc),
            )
        if operation is not None:
            write_operation_audit_event(
                session_factory=session_factory,
                action="runtime.run.cancel_requested",
                operation=operation,
                actor=actor,
                result=AuditResult.SUCCESS,
                status_code=202,
                metadata={"thread_id": thread_id, "run_id": run_id},
            )

    async def get_info(self, *, actor: ActorContext, project_id: str) -> dict[str, Any]:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.get_info()

    async def search_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.search_graphs(_normalize_payload(payload))

    async def count_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.count_graphs(_normalize_payload(payload))

    async def create_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        next_payload = _promote_thread_graph_id(next_payload)
        return await self._upstream.create_thread(next_payload)

    async def search_threads(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        return await self._upstream.search_threads(next_payload)

    async def count_threads(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        return await self._upstream.count_threads(next_payload)

    async def prune_threads(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = _normalize_payload(payload)
        thread_ids = next_payload.get("thread_ids")
        if isinstance(thread_ids, list):
            for thread_id in thread_ids:
                normalized_thread_id = clean_str(thread_id)
                if normalized_thread_id:
                    await self._load_thread(
                        actor=actor,
                        project_id=project_id,
                        thread_id=normalized_thread_id,
                        write=True,
                    )
        return await self._upstream.prune_threads(next_payload)

    async def get_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
    ) -> dict[str, Any]:
        return await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )

    async def update_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        return await self._upstream.update_thread(thread_id, next_payload)

    async def delete_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        return await self._upstream.delete_thread(thread_id)

    async def copy_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        copied = await self._upstream.copy_thread(thread_id)
        if isinstance(copied, dict):
            self._assert_thread_project_scope(project_id=project_id, thread=copied)
        return copied

    async def get_thread_state(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        params: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.get_thread_state(thread_id, _normalize_payload(params))

    async def update_thread_state(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        return await self._upstream.update_thread_state(thread_id, _normalize_payload(payload))

    async def get_thread_state_at_checkpoint(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        checkpoint_id: str,
    ) -> Any:
        return await self.get_thread_state(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            params={"checkpoint_id": checkpoint_id},
        )

    async def get_thread_history(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.get_thread_history(thread_id, _normalize_payload(payload))

    async def create_global_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
        )
        return await self._upstream.create_global_run(next_payload)

    async def stream_global_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
        )
        return await self._upstream.stream_global_run(next_payload)

    async def wait_global_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
        )
        return await self._upstream.wait_global_run(next_payload)

    async def create_batch_runs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payloads: list[dict[str, Any]],
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        default_model_id = await self._project_default_model_id(project_id=project_id)
        next_payloads: list[dict[str, Any]] = []
        for item in payloads:
            next_item = self._inject_project_scope(project_id=project_id, payload=item)
            if default_model_id:
                next_item = await self._inject_project_default_model(
                    project_id=project_id,
                    payload=next_item,
                    default_model_id=default_model_id,
                )
            assistant_id = clean_str(next_item.get("assistant_id"))
            await self._assert_runtime_target_allowed(
                project_id=project_id,
                assistant_id=assistant_id or "",
            )
            next_payloads.append(next_item)
        return await self._upstream.create_batch_runs(next_payloads)

    async def cancel_runs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = _normalize_payload(payload)
        thread_id = clean_str(next_payload.get("thread_id"))
        if thread_id:
            await self._load_thread(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                write=True,
            )
        return await self._upstream.cancel_runs(next_payload)

    async def create_cron(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
        )
        return await self._upstream.create_cron(next_payload)

    async def search_crons(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.search_crons(_normalize_payload(payload))

    async def count_crons(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.count_crons(_normalize_payload(payload))

    async def update_cron(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        cron_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        return await self._upstream.update_cron(cron_id, next_payload)

    async def delete_cron(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        cron_id: str,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        return await self._upstream.delete_cron(cron_id)

    async def create_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        return await self._upstream.create_thread_run(thread_id, next_payload)

    async def stream_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        return await self._upstream.stream_thread_run(thread_id, next_payload)

    async def send_thread_command(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        default_model_id = await self._project_default_model_id(project_id=project_id)
        try:
            command = normalize_protocol_v2_command(
                payload=payload,
                default_model_id=default_model_id,
            )
        except ValueError as exc:
            raise BadRequestError(
                code="invalid_protocol_command",
                message=str(exc),
            ) from exc

        if command["method"] == "run.start":
            config = ensure_dict(command["params"].get("config"))
            configurable = ensure_dict(config.get("configurable"))
            options = ensure_dict(configurable.get("platform_runtime"))
            await self._assert_runtime_options_allowed(
                project_id=project_id,
                options=options,
            )
            assistant_id = clean_str(command["params"].get("assistant_id"))
            await self._assert_runtime_target_allowed(
                project_id=project_id,
                assistant_id=assistant_id or "",
                thread=thread,
            )
            durable_run = await self._reserve_durable_run(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                command=command,
                idempotency_key=_normalize_idempotency_key(idempotency_key),
            )
            if durable_run.run_id:
                return {
                    "type": "success",
                    "id": command["id"],
                    "result": {"run_id": durable_run.run_id},
                }
            result = await self._upstream.send_thread_command(thread_id, command)
            run_id = _run_id_from_command_result(result)
            if not run_id:
                raise UpstreamServiceError(
                    code="protocol_run_id_missing",
                    message="Protocol v2 run.start response did not include run_id",
                    upstream="langgraph",
                )
            await self._mark_durable_run_started(
                actor=actor,
                durable_run=durable_run,
                run_id=run_id,
            )
            return result
        if command["method"] == "input.respond":
            interrupt_id = clean_str(command["params"].get("interrupt_id"))
            if not interrupt_id:
                raise BadRequestError(
                    code="interrupt_id_required",
                    message="input.respond requires interrupt_id",
                )
            active_run_id = await self._assert_active_interrupt(
                project_id=project_id,
                thread_id=thread_id,
                interrupt_id=interrupt_id,
            )
            result = await self._upstream.send_thread_command(thread_id, command)
            if not (
                isinstance(result, dict)
                and str(result.get("type") or "").lower() == "error"
            ):
                await self._mark_interrupt_resolved(
                    project_id=project_id,
                    thread_id=thread_id,
                    run_id=active_run_id,
                    interrupt_id=interrupt_id,
                )
            return result
        return await self._upstream.send_thread_command(thread_id, command)

    async def stream_thread_events(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any],
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        try:
            subscription = normalize_protocol_v2_event_request(payload)
        except ValueError as exc:
            raise BadRequestError(
                code="invalid_protocol_event_subscription",
                message=str(exc),
            ) from exc
        return await self._upstream.stream_thread_events(thread_id, subscription)

    async def wait_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        return await self._upstream.wait_thread_run(thread_id, next_payload)

    async def get_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        snapshot = await self._upstream.get_thread_run(thread_id, run_id)
        await self._sync_durable_run_terminal_state(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
            snapshot=snapshot,
        )
        return snapshot

    async def list_thread_runs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        params: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.list_thread_runs(thread_id, _normalize_payload(params))

    async def delete_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        return await self._upstream.delete_thread_run(thread_id, run_id)

    async def join_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.join_thread_run(thread_id, run_id)

    async def join_thread_run_stream(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
        params: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.join_thread_run_stream(
            thread_id,
            run_id,
            _normalize_payload(params),
        )

    async def create_thread_run_cron(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        return await self._upstream.create_thread_run_cron(thread_id, next_payload)

    async def cancel_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        result = await self._upstream.cancel_thread_run(
            thread_id,
            run_id,
            _normalize_payload(payload),
        )
        await self._mark_durable_run_cancel_requested(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
        )
        return result
