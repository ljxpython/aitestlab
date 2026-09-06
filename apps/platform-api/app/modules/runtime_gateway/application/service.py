from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Callable, Mapping
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
    PlatformApiError,
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
    validate_runtime_option_values,
)
from app.modules.agents.infra.sqlalchemy.repository import SqlAlchemyAssistantsRepository
from app.modules.audit.domain import AuditResult
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.operations.application.audit import write_operation_audit_event
from app.modules.operations.application.ports import OperationDispatcherProtocol
from app.modules.operations.domain import OperationStatus
from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository
from app.modules.runtime_catalog.infra.sqlalchemy.repository import (
    SqlAlchemyRuntimeCatalogRepository,
)
from app.modules.runtime_catalog.application.model_connection import create_model_reference
from app.modules.runtime_gateway.application.ports import RuntimeGatewayUpstreamProtocol
from app.modules.runtime_gateway.infra.sqlalchemy.repository import (
    SqlAlchemyDurableRunsRepository,
    StoredDurableRun,
)
from app.modules.runtime_policies.infra import SqlAlchemyRuntimePolicyRepository
from app.modules.runtime_policies.application import RuntimePolicyOverlayService

_THREAD_PROJECT_ID_KEYS = PROJECT_SCOPE_ALIAS_KEYS
_THREAD_GRAPH_ID_KEYS = ("graph_id", "graphId")
_DURABLE_RUN_OPERATION_KIND = "runtime.durable_run"
_SDK_LIFECYCLE_EVENTS = {
    "started": "running",
    "success": "completed",
    "error": "failed",
}


def _request_digest(command: dict[str, Any]) -> str:
    encoded = json.dumps(command, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _runtime_context_snapshot(command: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    params = ensure_dict(command.get("params"))
    config = ensure_dict(params.get("config"))
    configurable = ensure_dict(config.get("configurable"))
    runtime_options = ensure_dict(configurable.get("platform_runtime"))
    context = ensure_dict(params.get("context"))
    # Protocol promotion applies platform_runtime over the submitted context.
    merged = {**context, **runtime_options}
    tools = merged.get("tools")
    if tools is not None:
        tools = sorted(tools)
    snapshot = {
        "model_id": merged.get("model_id"),
        "temperature": (
            float(merged["temperature"])
            if isinstance(merged.get("temperature"), (int, float))
            and not isinstance(merged.get("temperature"), bool)
            else merged.get("temperature")
        ),
        "max_tokens": merged.get("max_tokens"),
        "top_p": (
            float(merged["top_p"])
            if isinstance(merged.get("top_p"), (int, float))
            and not isinstance(merged.get("top_p"), bool)
            else merged.get("top_p")
        ),
        "tools": tools,
    }
    encoded = json.dumps(
        {"schema": "runtime-context/v1", **snapshot},
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    persisted_snapshot = {
        key: value for key, value in snapshot.items() if value is not None
    }
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest(), persisted_snapshot


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


def _run_items(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if not isinstance(result, dict):
        return []
    for key in ("runs", "data", "items"):
        value = result.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _promote_protocol_run_start(params: dict[str, Any]) -> dict[str, Any]:
    """Convert Platform's v2 candidate envelope into a standard Runs payload."""
    config = ensure_dict(params.get("config"))
    configurable = ensure_dict(config.get("configurable"))
    runtime_options = ensure_dict(configurable.get("platform_runtime"))
    next_configurable = dict(configurable)
    next_configurable.pop("platform_runtime", None)
    next_config = dict(config)
    if next_configurable:
        next_config["configurable"] = next_configurable
    else:
        next_config.pop("configurable", None)

    context = ensure_dict(params.get("context"))
    context.update(runtime_options)
    promoted = {
        key: params[key]
        for key in (
            "assistant_id",
            "input",
            "command",
            "stream_mode",
            "stream_subgraphs",
            "stream_resumable",
            "metadata",
            "context",
            "checkpoint",
            "checkpoint_id",
            "checkpoint_during",
            "interrupt_before",
            "interrupt_after",
            "webhook",
            "multitask_strategy",
            "if_not_exists",
            "on_completion",
            "after_seconds",
            "durability",
        )
        if key in params
    }
    promoted["context"] = context
    if next_config:
        promoted["config"] = next_config
    return promoted


def _terminal_operation_status(snapshot: Any) -> OperationStatus | None:
    if not isinstance(snapshot, dict):
        return None
    status = clean_str(snapshot.get("status"))
    if status in {"success", "succeeded", "completed"}:
        return OperationStatus.SUCCEEDED
    if status in {"error", "failed", "timeout"}:
        return OperationStatus.FAILED
    if status in {"cancelled", "canceled"}:
        return OperationStatus.CANCELLED
    return None


def _normalize_protocol_lifecycle_frame(frame: bytes) -> tuple[bytes, dict[str, str] | None]:
    """Bridge GraphHarbor lifecycle labels to the locked frontend SDK contract."""
    try:
        lines = frame.decode("utf-8").split("\n")
    except UnicodeDecodeError:
        return frame, None
    data_positions = [index for index, line in enumerate(lines) if line.startswith("data:")]
    if not data_positions:
        return frame, None
    try:
        payload = json.loads("\n".join(lines[index][5:].lstrip() for index in data_positions))
    except ValueError:
        return frame, None
    if not isinstance(payload, dict) or payload.get("method") != "lifecycle":
        return frame, None
    params = ensure_dict(payload.get("params"))
    data = ensure_dict(params.get("data"))
    event = clean_str(data.get("event"))
    normalized_event = _SDK_LIFECYCLE_EVENTS.get(event, event)
    if normalized_event != event:
        payload["params"] = {**params, "data": {**data, "event": normalized_event}}
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        first_data_position = data_positions[0]
        lines = [
            f"data: {encoded}" if index == first_data_position else line
            for index, line in enumerate(lines)
            if index not in data_positions[1:]
        ]
        frame = "\n".join(lines).encode("utf-8")
    run_id = clean_str(params.get("run_id"))
    status = clean_str(data.get("status"))
    if not run_id or _terminal_operation_status({"status": status}) is None:
        return frame, None
    return frame, {"run_id": run_id, "status": status}


def _interrupt_ids(state: Any) -> set[str]:
    if not isinstance(state, dict):
        return set()
    interrupts = state.get("interrupts")
    if isinstance(interrupts, dict):
        return {interrupt_id for interrupt_id in (clean_str(key) for key in interrupts) if interrupt_id}
    if isinstance(interrupts, list):
        return {
            interrupt_id
            for interrupt in interrupts
            if isinstance(interrupt, dict)
            for interrupt_id in [clean_str(interrupt.get("id") or interrupt.get("interrupt_id"))]
            if interrupt_id
        }
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


def _merge_runtime_context(
    *,
    project_default_model: str | None,
    agent_defaults: dict[str, Any],
    requested: dict[str, Any],
) -> dict[str, Any]:
    defaults = dict(agent_defaults)
    if project_default_model and "model_id" not in defaults:
        defaults["model_id"] = project_default_model
    return {**defaults, **requested}


class RuntimeGatewayService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: RuntimeGatewayUpstreamProtocol,
        runtime_base_url: str = "",
        policy_engine: IamPolicyEngine | None = None,
        operation_dispatcher: OperationDispatcherProtocol | None = None,
        delegation_headers_factory: Callable[..., Mapping[str, str]] | None = None,
        runtime_model_config_secret: str | None = None,
        runtime_model_config_ttl_seconds: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._runtime_id = runtime_base_url.rstrip("/")
        self._policy_engine = policy_engine or IamPolicyEngine()
        self._operation_dispatcher = operation_dispatcher
        self._delegation_headers_factory = delegation_headers_factory
        self._runtime_model_config_secret = runtime_model_config_secret
        self._runtime_model_config_ttl_seconds = runtime_model_config_ttl_seconds

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
        assistant_id = clean_str(payload.get("assistant_id"))
        profile_defaults: dict[str, Any] = {}
        if assistant_id and self._session_factory is not None:
            try:
                project_uuid = parse_uuid(project_id, code="invalid_project_id")
            except PlatformApiError:
                project_uuid = None
            if project_uuid is not None:
                async with SqlAlchemyUnitOfWork(self._session_factory) as uow:
                    agent = SqlAlchemyAssistantsRepository(uow.session).get_by_project_and_graph_id(
                        project_id=project_uuid,
                        graph_id=assistant_id,
                    )
                    if agent is None:
                        agent = SqlAlchemyAssistantsRepository(uow.session).get_by_project_and_langgraph_assistant_id(
                            project_id=project_uuid,
                            langgraph_assistant_id=assistant_id,
                        )
                    if agent is not None:
                        profile_defaults = {
                            key: agent.context[key]
                            for key in ("model_id", "temperature", "max_tokens", "top_p", "tools")
                            if key in agent.context
                        }

        if default_model_id is None and not clean_str(context.get("model_id")):
            default_model_id = await self._project_default_model_id(project_id=project_id)
        merged = _merge_runtime_context(
            project_default_model=default_model_id,
            agent_defaults=profile_defaults,
            requested=context,
        )
        if merged == context:
            return payload
        next_payload = dict(payload)
        next_payload["context"] = merged
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
                if item.enabled
                and (str(item.id) not in model_policies
                or model_policies[str(item.id)].is_enabled
                )
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

    async def _validate_run_options(self, *, project_id: str, payload: dict[str, Any]) -> None:
        context = ensure_dict(payload.get("context"))
        config = ensure_dict(payload.get("config"))
        configurable = ensure_dict(config.get("configurable"))
        options = {**ensure_dict(configurable.get("platform_runtime")), **context}
        try:
            validate_runtime_option_values(options)
        except ValueError as exc:
            raise BadRequestError(
                code="invalid_runtime_options",
                message=str(exc),
            ) from exc
        await self._assert_runtime_options_allowed(project_id=project_id, options=options)

    async def _attach_runtime_model_reference(
        self,
        *,
        project_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Pass only a short-lived model capability through the generic Agent Server."""
        if not self._runtime_model_config_secret:
            return payload
        model_id = clean_str(ensure_dict(payload.get("context")).get("model_id"))
        if not model_id:
            return payload
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            item = SqlAlchemyRuntimeCatalogRepository(uow.session).get_model_by_key(
                runtime_id=self._runtime_id,
                model_key=model_id,
            )
            if item is None or not item.enabled:
                raise ForbiddenError(code="runtime_model_denied", message="Requested runtime model is not enabled")
        reference = create_model_reference(
            project_id=project_id,
            model_id=model_id,
            secret=self._runtime_model_config_secret,
            ttl_seconds=self._runtime_model_config_ttl_seconds,
        )
        config = ensure_dict(payload.get("config"))
        configurable = dict(ensure_dict(config.get("configurable")))
        configurable["_runtime_model_ref"] = reference
        next_config = dict(config)
        next_config["configurable"] = configurable
        next_payload = dict(payload)
        next_payload["config"] = next_config
        return next_payload

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
            item = repository.get_by_project_and_graph_id(
                project_id=project_uuid,
                graph_id=assistant_id,
            )
            if item is None:
                # Read-only compatibility for historical rows; new runs use graph_id.
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
        context_hash, context_snapshot = _runtime_context_snapshot(command)
        agent_key = clean_str(command["params"].get("assistant_id")) or ""
        policy_version: str | None = None
        if self._session_factory is not None:
            try:
                policy_version = str(
                    RuntimePolicyOverlayService(
                        session_factory=self._session_factory,
                        runtime_base_url=self._runtime_id,
                    ).build_delegation_policy(project_id=project_id)["version"]
                )
            except PlatformApiError:
                policy_version = None
        if not agent_key:
            raise BadRequestError(code="agent_key_required", message="agent_key is required")
        try:
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                runs = SqlAlchemyDurableRunsRepository(uow.session)
                bound_agent_key = runs.get_bound_agent_key(
                    project_id=project_id,
                    thread_id=thread_id,
                )
                if bound_agent_key and bound_agent_key != agent_key:
                    raise ConflictError(
                        code="agent_thread_mismatch",
                        message="The thread is already bound to a different agent",
                    )
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
                    agent_key=agent_key,
                    context_hash=context_hash,
                    context_snapshot=context_snapshot,
                    policy_version=policy_version,
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
        if existing.status == "run_start_unknown":
            return existing
        raise ConflictError(
            code="run_start_in_progress",
            message="The original run.start request is still being reconciled",
        )

    async def _mark_durable_run_unknown(
        self,
        *,
        actor: ActorContext,
        durable_run: StoredDurableRun,
    ) -> None:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            runs = SqlAlchemyDurableRunsRepository(uow.session)
            unknown = runs.mark_unknown(durable_run_id=durable_run.id)
            if unknown is None:
                raise ServiceUnavailableError(
                    code="durable_run_record_missing",
                    message="Durable Run record disappeared during timeout handling",
                )
            operations = SqlAlchemyOperationsRepository(uow.session)
            current_operation = operations.get_by_id(durable_run.operation_id)
            metadata = dict(current_operation.metadata) if current_operation is not None else {}
            metadata.update(
                {
                    "durable_run": True,
                    "reconciliation": {
                        "state": "run_start_unknown",
                        "idempotency_key": durable_run.idempotency_key,
                        "attempt_limit": 3,
                    },
                    "_retry_policy": {"max_attempts": 3},
                }
            )
            operation = operations.update_status(
                operation_id=durable_run.operation_id,
                status=OperationStatus.SUBMITTED,
                metadata=metadata,
            )
        if operation is not None:
            write_operation_audit_event(
                session_factory=session_factory,
                action="runtime.run.start_unknown",
                operation=operation,
                actor=actor,
                result=AuditResult.FAILED,
                status_code=202,
                metadata={"thread_id": durable_run.thread_id},
            )
            if self._operation_dispatcher is not None:
                await self._operation_dispatcher.dispatch(operation=operation)

    async def reconcile_durable_run(
        self,
        *,
        actor: ActorContext,
        durable_run: StoredDurableRun,
    ) -> StoredDurableRun | None:
        """Find a remotely-created Run without replaying the original input."""
        if durable_run.run_id:
            return durable_run
        result = await self._upstream.list_thread_runs(
            durable_run.thread_id,
            {"limit": 100},
        )
        for item in _run_items(result):
            metadata = ensure_dict(item.get("metadata"))
            if metadata.get("platform_idempotency_key") != durable_run.idempotency_key:
                continue
            run_id = _run_id_from_command_result(item) or clean_str(item.get("id"))
            if not run_id:
                continue
            await self._mark_durable_run_started(
                actor=actor,
                durable_run=durable_run,
                run_id=run_id,
            )
            return StoredDurableRun(
                id=durable_run.id,
                project_id=durable_run.project_id,
                thread_id=durable_run.thread_id,
                agent_key=durable_run.agent_key,
                idempotency_key=durable_run.idempotency_key,
                request_digest=durable_run.request_digest,
                run_id=run_id,
                operation_id=durable_run.operation_id,
                status="running",
                active=True,
                created_at=durable_run.created_at,
                updated_at=durable_run.updated_at,
            )
        return None

    async def reconcile_operation(self, *, operation_id: str, actor: ActorContext) -> bool:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            durable_run = SqlAlchemyDurableRunsRepository(uow.session).get_by_operation_id(operation_id)
        if durable_run is None or durable_run.run_id:
            return durable_run is not None
        return await self.reconcile_durable_run(actor=actor, durable_run=durable_run) is not None

    async def fail_reconciliation(self, *, operation_id: str) -> None:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            durable_run = SqlAlchemyDurableRunsRepository(uow.session).get_by_operation_id(operation_id)
            if durable_run is not None and durable_run.active and not durable_run.run_id:
                SqlAlchemyDurableRunsRepository(uow.session).mark_terminal(
                    durable_run_id=durable_run.id,
                    status="failed",
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

    async def _launch_runtime_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        command: dict[str, Any],
        upstream_payload: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[StoredDurableRun, Any]:
        """Reserve once, create upstream once, and reconcile timeout outcomes."""
        await self._reconcile_active_durable_run_before_launch(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            idempotency_key=idempotency_key,
        )
        durable_run = await self._reserve_durable_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            command=command,
            idempotency_key=idempotency_key,
        )
        if durable_run.run_id:
            return durable_run, {"run_id": durable_run.run_id, "thread_id": thread_id}
        if getattr(durable_run, "status", "") == "run_start_unknown":
            reconciled = await self.reconcile_durable_run(actor=actor, durable_run=durable_run)
            if reconciled is not None and reconciled.run_id:
                return reconciled, {"run_id": reconciled.run_id, "thread_id": thread_id}
            raise ConflictError(
                code="run_start_in_progress",
                message="The original run.start request is still being reconciled",
            )

        idempotency_marker = clean_str(getattr(durable_run, "idempotency_key", None))
        if idempotency_marker:
            promoted_metadata = ensure_dict(upstream_payload.get("metadata"))
            upstream_payload = dict(upstream_payload)
            upstream_payload["metadata"] = {
                **promoted_metadata,
                "platform_idempotency_key": idempotency_marker,
            }
        upstream = self._upstream
        if self._delegation_headers_factory is not None and hasattr(
            upstream, "with_forwarded_headers"
        ):
            context_hash, _ = _runtime_context_snapshot(command)
            upstream = upstream.with_forwarded_headers(
                self._delegation_headers_factory(
                    project_id=project_id,
                    agent_key=durable_run.agent_key,
                    thread_id=thread_id,
                    context_hash=context_hash,
                )
            )
        try:
            result = await upstream.create_thread_run(thread_id, upstream_payload)
        except UpstreamServiceError as exc:
            if exc.code == "langgraph_upstream_timeout":
                await self._mark_durable_run_unknown(actor=actor, durable_run=durable_run)
                raise UpstreamServiceError(
                    code="run_start_unknown",
                    message="Run creation outcome is unknown and is being reconciled",
                    upstream="langgraph",
                ) from exc
            raise
        run_id = _run_id_from_command_result(result)
        if not run_id:
            raise UpstreamServiceError(
                code="protocol_run_id_missing",
                message="Run creation response did not include run_id",
                upstream="langgraph",
            )
        await self._mark_durable_run_started(
            actor=actor,
            durable_run=durable_run,
            run_id=run_id,
        )
        return durable_run, result

    async def _reconcile_active_durable_run_before_launch(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        idempotency_key: str,
    ) -> None:
        """Release an old ledger slot only when the Agent Server reports a terminal Run."""
        if self._session_factory is None:
            return
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            runs = SqlAlchemyDurableRunsRepository(uow.session)
            if runs.get_by_idempotency_key(
                project_id=project_id,
                thread_id=thread_id,
                idempotency_key=idempotency_key,
            ) is not None:
                return
            active_run = runs.get_active(project_id=project_id, thread_id=thread_id)
            if active_run is not None:
                operation = SqlAlchemyOperationsRepository(uow.session).get_by_id(
                    active_run.operation_id
                )
                if operation is not None and operation.cancel_requested_at is not None:
                    return

        if active_run is None or not active_run.run_id:
            return
        try:
            snapshot = await self._upstream.get_thread_run(thread_id, active_run.run_id)
        except PlatformApiError:
            # The ledger remains authoritative until an upstream terminal fact is available.
            return
        await self._sync_durable_run_terminal_state(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            run_id=active_run.run_id,
            snapshot=snapshot,
        )

    async def launch_runtime_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        command: dict[str, Any],
        upstream_payload: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[StoredDurableRun, Any]:
        """Single application entry point for every governed Run creation."""
        upstream_payload = await self._attach_runtime_model_reference(
            project_id=project_id,
            payload=upstream_payload,
        )
        return await self._launch_runtime_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            command=command,
            upstream_payload=upstream_payload,
            idempotency_key=idempotency_key,
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

    async def _assert_run_project_scope(
        self,
        *,
        project_id: str,
        thread_id: str,
        run_id: str,
    ) -> None:
        """Reject known durable runs owned by another project.

        Historical upstream runs may not have a Platform projection; those remain
        readable after the thread ownership check for backwards compatibility.
        """
        if self._session_factory is None:
            return
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            durable_run = SqlAlchemyDurableRunsRepository(uow.session).get_any_by_run_id(
                thread_id=thread_id,
                run_id=run_id,
            )
        if durable_run is not None and durable_run.project_id != project_id:
            raise ForbiddenError(
                code="run_project_denied",
                message="run_project_denied",
            )

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
        await self._validate_run_options(project_id=project_id, payload=next_payload)
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
        await self._validate_run_options(project_id=project_id, payload=next_payload)
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
        await self._validate_run_options(project_id=project_id, payload=next_payload)
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
        await self._validate_run_options(project_id=project_id, payload=next_payload)
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
        await self._validate_run_options(project_id=project_id, payload=next_payload)
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
        await self._validate_run_options(project_id=project_id, payload=next_payload)
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        command = {"id": "standard-run", "method": "run.start", "params": next_payload}
        digest = _request_digest(command)
        _, result = await self.launch_runtime_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            command=command,
            upstream_payload=next_payload,
            idempotency_key="standard:" + digest,
        )
        return result

    async def stream_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        result = await self.create_thread_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            payload=next_payload,
        )
        run_id = _run_id_from_command_result(result)
        if not run_id:
            raise UpstreamServiceError(
                code="protocol_run_id_missing",
                message="Run creation response did not include run_id",
                upstream="langgraph",
            )
        stream_params = {
            key: next_payload[key]
            for key in ("stream_mode", "stream_subgraphs", "stream_resumable", "on_disconnect")
            if key in next_payload
        }
        return await self._upstream.join_thread_run_stream(thread_id, run_id, stream_params)

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
        raw_payload = dict(payload)
        raw_params = ensure_dict(raw_payload.get("params"))
        if raw_payload.get("method") == "run.start":
            raw_params = await self._inject_project_default_model(
                project_id=project_id,
                payload=raw_params,
            )
        raw_payload["params"] = raw_params
        default_model_id = clean_str(ensure_dict(raw_params.get("context")).get("model_id"))
        try:
            command = normalize_protocol_v2_command(
                payload=raw_payload,
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
            context = ensure_dict(command["params"].get("context"))
            if "model_id" in context and "model_id" not in options:
                options["model_id"] = context["model_id"]
            if "tools" in context and "tools" not in options:
                options["tools"] = context["tools"]
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
            promoted_payload = _promote_protocol_run_start(command["params"])
            _, result = await self.launch_runtime_run(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                command=command,
                upstream_payload=promoted_payload,
                idempotency_key=_normalize_idempotency_key(idempotency_key),
            )
            run_id = _run_id_from_command_result(result)
            return {
                "type": "success",
                "id": command["id"],
                "result": {"run_id": run_id, "thread_id": thread_id},
            }
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
                resumed_run_id = _run_id_from_command_result(result)
                if resumed_run_id and resumed_run_id != active_run_id:
                    session_factory = self._require_session_factory()
                    async with SqlAlchemyUnitOfWork(session_factory) as uow:
                        SqlAlchemyDurableRunsRepository(uow.session).replace_active_run_id(
                            project_id=project_id,
                            thread_id=thread_id,
                            run_id=active_run_id,
                            next_run_id=resumed_run_id,
                        )
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
        stream = await self._upstream.stream_thread_events(thread_id, subscription)

        async def normalized_stream() -> AsyncIterator[bytes]:
            buffer = b""
            async for chunk in stream:
                buffer += chunk.replace(b"\r\n", b"\n")
                frames = buffer.split(b"\n\n")
                buffer = frames.pop()
                for frame in frames:
                    normalized, terminal = _normalize_protocol_lifecycle_frame(frame)
                    if terminal is not None:
                        await self._sync_durable_run_terminal_state(
                            actor=actor,
                            project_id=project_id,
                            thread_id=thread_id,
                            run_id=terminal["run_id"],
                            snapshot={"status": terminal["status"]},
                        )
                    yield normalized + b"\n\n"
            if buffer:
                normalized, terminal = _normalize_protocol_lifecycle_frame(buffer)
                if terminal is not None:
                    await self._sync_durable_run_terminal_state(
                        actor=actor,
                        project_id=project_id,
                        thread_id=thread_id,
                        run_id=terminal["run_id"],
                        snapshot={"status": terminal["status"]},
                    )
                yield normalized

        return normalized_stream()

    async def wait_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        next_payload = await self._inject_project_default_model(
            project_id=project_id,
            payload=next_payload,
        )
        result = await self.create_thread_run(
            project_id=project_id,
            actor=actor,
            thread_id=thread_id,
            payload=next_payload,
        )
        run_id = _run_id_from_command_result(result)
        if not run_id:
            raise UpstreamServiceError(
                code="protocol_run_id_missing",
                message="Run creation response did not include run_id",
                upstream="langgraph",
            )
        return await self._upstream.join_thread_run(thread_id, run_id)

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
        await self._assert_run_project_scope(
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
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
        await self._assert_run_project_scope(
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
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
        await self._assert_run_project_scope(
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
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
        await self._assert_run_project_scope(
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
        )
        stream_params = _normalize_payload(params)
        if stream_params.get("cancel_on_disconnect") is True:
            raise BadRequestError(
                code="cancel_on_disconnect_not_supported",
                message="SSE disconnect must not cancel a run; use the explicit cancel endpoint",
            )
        stream_params["cancel_on_disconnect"] = False
        return await self._upstream.join_thread_run_stream(
            thread_id,
            run_id,
            stream_params,
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
        await self._assert_run_project_scope(
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
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
