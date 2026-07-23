from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.identifiers import parse_uuid
from app.core.normalization import clean_str, ensure_dict
from app.core.runtime_contract import (
    PROJECT_SCOPE_ALIAS_KEYS,
    normalize_runtime_payload,
    strip_keys,
)
from app.modules.assistants.infra.sqlalchemy.repository import SqlAlchemyAssistantsRepository
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository
from app.modules.runtime_gateway.application.ports import RuntimeGatewayUpstreamProtocol
from app.modules.runtime_policies.infra import SqlAlchemyRuntimePolicyRepository

_THREAD_PROJECT_ID_KEYS = PROJECT_SCOPE_ALIAS_KEYS
_THREAD_GRAPH_ID_KEYS = ("graph_id", "graphId")


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
        session_factory = self._require_session_factory()
        self._authorize(actor=actor, project_id=project_id, write=write)
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
        return await self._upstream.get_thread_run(thread_id, run_id)

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
        return await self._upstream.cancel_thread_run(
            thread_id,
            run_id,
            _normalize_payload(payload),
        )
