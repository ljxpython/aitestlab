from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
from typing import Any
from uuid import UUID
from urllib.parse import urlparse

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotAuthenticatedError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.identifiers import parse_uuid
from app.core.security import create_runtime_delegation_token, empty_runtime_context_hash
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository
from app.modules.runtime_catalog.domain import (
    RuntimeCatalogRefreshResult,
    RuntimeGraphCatalogItem,
    RuntimeGraphCatalogList,
    RuntimeModelCatalogItem,
    RuntimeModelCatalogList,
    RuntimeModelCreate,
    RuntimeModelUpdate,
    RuntimeToolCatalogItem,
    RuntimeToolCatalogList,
)
from app.modules.runtime_catalog.application.credentials import (
    ModelCredentialError,
    decrypt_api_key,
    encrypt_api_key,
)
from app.modules.runtime_catalog.application.model_connection import (
    ModelReferenceError,
    parse_model_reference,
)
from app.modules.runtime_catalog.infra import SqlAlchemyRuntimeCatalogRepository
from app.modules.runtime_policies.application import RuntimePolicyOverlayService


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
def _runtime_id(value: str) -> str:
    return value.rstrip("/")


_SUPPORTED_PROTOCOLS = {"openai", "openai-compatible", "deepseek"}


class RuntimeCatalogService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: Any,
        runtime_base_url: str,
        settings: Settings,
        tenant_id: str = "__default",
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._runtime_id = _runtime_id(runtime_base_url)
        self._settings = settings
        self._tenant_id = tenant_id or "__default"
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

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
        permission: PermissionCode,
    ) -> UUID:
        session_factory = self._require_session_factory()
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=permission,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            return self._require_project_exists(uow=uow, project_id=project_id)

    def _require_refresh_access(self, *, actor: ActorContext, project_id: str) -> None:
        try:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PLATFORM_CATALOG_REFRESH,
                ),
            )
            return
        except ForbiddenError:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_RUNTIME_WRITE,
                    project_id=project_id,
                ),
            )

    def _runtime_headers(self, *, actor: ActorContext, project_id: str) -> dict[str, str]:
        subject = actor.user_id or actor.subject
        if not subject:
            raise NotAuthenticatedError()
        project_roles = actor.project_role_set(project_id)
        if not project_roles:
            raise ForbiddenError(
                code="project_role_missing",
                message="Project role missing",
            )
        try:
            policy = RuntimePolicyOverlayService(
                session_factory=self._session_factory,
                runtime_base_url=self._runtime_id,
            ).build_delegation_policy(project_id=project_id)
            delegation = create_runtime_delegation_token(
                subject=subject,
                tenant_id=self._tenant_id,
                project_id=project_id,
                role=project_roles[0],
                permissions=[
                    "project.runtime.read",
                    "project.runtime.write",
                    *policy["runtime_permissions"],
                ],
                policy_version=str(policy["version"]),
                allowed_model_ids=policy["allowed_model_ids"],
                allowed_tool_names=policy["allowed_tool_names"],
                scope={"tenant_id": self._tenant_id, "project_id": project_id},
                context_hash=empty_runtime_context_hash(),
                settings=self._settings,
            )
        except ValueError as exc:
            raise ServiceUnavailableError(
                code="runtime_delegation_not_configured",
                message="Runtime delegation is not configured",
            ) from exc
        return {"authorization": f"Bearer {delegation}"}

    def _model_item(self, item: Any) -> RuntimeModelCatalogItem:
        return RuntimeModelCatalogItem(
            id=str(item.id),
            runtime_id=item.runtime_id,
            model_id=item.model_key,
            display_name=item.display_name or item.model_key,
            is_default=item.is_default_runtime,
            sync_status=item.sync_status,
            last_seen_at=item.last_seen_at,
            last_synced_at=item.last_synced_at,
            provider=item.provider,
            base_url=item.base_url,
            protocol=item.protocol,
            model=item.model_name or item.model_key,
            enabled=item.enabled,
            credential_configured=bool(item.api_key_ciphertext),
        )

    async def resolve_model_connection(
        self,
        *,
        reference: str,
        project_id: str,
    ) -> dict[str, str]:
        """Resolve one short-lived internal reference without exposing it publicly."""
        secret = self._settings.runtime_model_config_secret or self._settings.runtime_delegation_secret
        try:
            values = parse_model_reference(reference, secret=secret)
        except ModelReferenceError as exc:
            raise ForbiddenError(code="runtime_model_reference_invalid", message="Invalid model reference") from exc
        if values["project_id"] != project_id:
            raise ForbiddenError(code="runtime_model_reference_denied", message="Model reference project mismatch")

        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            item = repository.get_model_by_key(runtime_id=self._runtime_id, model_key=values["model_id"])
            if item is None or not item.enabled:
                raise NotFoundError(code="runtime_model_not_found", message="Runtime model not found")
            try:
                api_key = decrypt_api_key(
                    item.api_key_ciphertext,
                    master_key=self._settings.model_config_master_key,
                )
            except ModelCredentialError as exc:
                raise ServiceUnavailableError(
                    code="model_credential_unavailable",
                    message="Model credential storage is not configured",
                ) from exc
            required = (item.provider, item.base_url, item.protocol, item.model_name, api_key)
            if any(not value for value in required):
                raise ServiceUnavailableError(
                    code="runtime_model_connection_incomplete",
                    message="Runtime model connection is incomplete",
                )
            return {
                "model_id": item.model_key,
                "provider": item.provider,
                "base_url": item.base_url,
                "protocol": item.protocol,
                "model": item.model_name,
                "api_key": api_key,
            }

    @staticmethod
    def _validated_model_values(payload: RuntimeModelCreate | RuntimeModelUpdate, *, partial: bool) -> dict[str, Any]:
        values = payload.model_dump(exclude_unset=partial)
        required = ("provider", "display_name", "base_url", "protocol", "model")
        if not partial:
            missing = [key for key in (*required, "api_key") if not _clean(values.get(key))]
            if missing:
                raise BadRequestError(
                    message="model fields are required",
                    code="model_fields_required",
                )
        for key in required:
            if key in values and not _clean(values[key]):
                raise BadRequestError(message=f"{key} is required", code="model_field_required")
        if "base_url" in values:
            parsed = urlparse(str(values["base_url"]).strip())
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise BadRequestError(
                    message="base_url must be a valid http or https URL",
                    code="invalid_model_base_url",
                )
            if parsed.username or parsed.password:
                raise BadRequestError(
                    message="base_url must not contain embedded credentials",
                    code="invalid_model_base_url",
                )
            hostname = (parsed.hostname or "").lower().rstrip(".")
            if hostname in {"localhost", "localhost.localdomain"}:
                raise BadRequestError(
                    message="base_url must not target localhost",
                    code="invalid_model_base_url",
                )
            try:
                address = ipaddress.ip_address(hostname)
            except ValueError:
                address = None
            if address is not None and (
                address.is_private or address.is_loopback or address.is_link_local or address.is_unspecified
            ):
                raise BadRequestError(
                    message="base_url must not target a private or local address",
                    code="invalid_model_base_url",
                )
            values["base_url"] = str(values["base_url"]).strip().rstrip("/")
        if "protocol" in values:
            values["protocol"] = str(values["protocol"]).strip().lower()
            if values["protocol"] not in _SUPPORTED_PROTOCOLS:
                raise BadRequestError(message="unsupported model protocol", code="unsupported_model_protocol")
        for key in ("provider", "display_name", "model"):
            if key in values:
                values[key] = str(values[key]).strip()
        if "api_key" in values and not _clean(values["api_key"]):
            raise BadRequestError(message="api_key is required", code="model_field_required")
        return values

    async def create_model(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: RuntimeModelCreate,
    ) -> RuntimeModelCatalogItem:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_WRITE,
        )
        values = self._validated_model_values(payload, partial=False)
        try:
            values["api_key_ciphertext"] = encrypt_api_key(
                payload.api_key,
                master_key=self._settings.model_config_master_key,
            )
        except ModelCredentialError as exc:
            raise ServiceUnavailableError(
                code="model_credential_unavailable",
                message="Model credential storage is not configured",
            ) from exc
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            item = SqlAlchemyRuntimeCatalogRepository(uow.session).create_configured_model(
                runtime_id=self._runtime_id,
                values=values,
            )
            return self._model_item(item)

    async def update_model(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        model_id: str,
        payload: RuntimeModelUpdate,
    ) -> RuntimeModelCatalogItem:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_WRITE,
        )
        values = self._validated_model_values(payload, partial=True)
        if "api_key" in values:
            try:
                values["api_key_ciphertext"] = encrypt_api_key(
                    values.pop("api_key"),
                    master_key=self._settings.model_config_master_key,
                )
            except ModelCredentialError as exc:
                raise ServiceUnavailableError(
                    code="model_credential_unavailable",
                    message="Model credential storage is not configured",
                ) from exc
        if "model" in values:
            model_name = values.pop("model")
            values["model_key"] = model_name
            values["model_name"] = model_name
        if "enabled" not in values:
            values.pop("enabled", None)
        model_uuid = parse_uuid(model_id, code="invalid_model_id")
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            item = SqlAlchemyRuntimeCatalogRepository(uow.session).update_configured_model(
                model_uuid,
                values=values,
            )
            if item is None:
                raise NotFoundError(message="Model not found", code="model_not_found")
            return self._model_item(item)

    def _tool_item(self, item: Any) -> RuntimeToolCatalogItem:
        return RuntimeToolCatalogItem(
            id=str(item.id),
            runtime_id=item.runtime_id,
            tool_key=item.tool_key,
            name=item.name,
            source=item.source or "",
            description=item.description or "",
            sync_status=item.sync_status,
            last_seen_at=item.last_seen_at,
            last_synced_at=item.last_synced_at,
        )

    def _graph_item(self, item: Any) -> RuntimeGraphCatalogItem:
        return RuntimeGraphCatalogItem(
            id=str(item.id),
            runtime_id=item.runtime_id,
            graph_id=item.graph_key,
            display_name=item.display_name or item.graph_key,
            description=item.description or "",
            source_type=item.source_type,
            sync_status=item.sync_status,
            last_seen_at=item.last_seen_at,
            last_synced_at=item.last_synced_at,
        )

    @staticmethod
    def _normalize_model_items(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            return []
        return [item for item in payload["models"] if isinstance(item, dict)]

    @staticmethod
    def _normalize_tool_items(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("tools"), list):
            return []
        return [item for item in payload["tools"] if isinstance(item, dict)]

    @staticmethod
    def _normalize_graph_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
        return []

    @staticmethod
    def _latest_synced_at(items: list[Any]) -> datetime | None:
        return max(
            (item.last_synced_at for item in items if item.last_synced_at is not None),
            default=None,
        )

    async def list_models(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeModelCatalogList:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            rows = repository.list_models(runtime_id=self._runtime_id)
            items = [self._model_item(item) for item in rows]
            return RuntimeModelCatalogList(
                count=len(items),
                models=items,
                last_synced_at=self._latest_synced_at(items),
            )

    async def refresh_models(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeCatalogRefreshResult:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        self._require_refresh_access(actor=actor, project_id=project_id)

        payload = await self._upstream.require_json(
            "GET",
            "/internal/capabilities/models",
            forwarded_headers=self._runtime_headers(actor=actor, project_id=project_id),
        )
        items = self._normalize_model_items(payload)
        synced_at = datetime.now(timezone.utc)
        active_keys = {
            model_key
            for model_key in (_clean(item.get("model_id")) for item in items)
            if model_key
        }

        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            repository.upsert_model_items(
                runtime_id=self._runtime_id,
                items=items,
                synced_at=synced_at,
            )
            repository.mark_missing_models_deleted(
                runtime_id=self._runtime_id,
                active_keys=active_keys,
                synced_at=synced_at,
            )

        return RuntimeCatalogRefreshResult(
            ok=True,
            count=len(items),
            last_synced_at=synced_at,
        )

    async def list_tools(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeToolCatalogList:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            rows = repository.list_tools(runtime_id=self._runtime_id)
            items = [self._tool_item(item) for item in rows]
            return RuntimeToolCatalogList(
                count=len(items),
                tools=items,
                last_synced_at=self._latest_synced_at(items),
            )

    async def refresh_tools(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeCatalogRefreshResult:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        self._require_refresh_access(actor=actor, project_id=project_id)

        payload = await self._upstream.require_json(
            "GET",
            "/internal/capabilities/tools",
            forwarded_headers=self._runtime_headers(actor=actor, project_id=project_id),
        )
        items = self._normalize_tool_items(payload)
        synced_at = datetime.now(timezone.utc)
        active_keys = {
            tool_key
            for tool_key in (
                _clean(item.get("tool_key"))
                or (
                    f"{_clean(item.get('source'))}:{_clean(item.get('name'))}"
                    if _clean(item.get("source")) and _clean(item.get("name"))
                    else _clean(item.get("name"))
                )
                for item in items
            )
            if tool_key
        }

        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            repository.upsert_tool_items(
                runtime_id=self._runtime_id,
                items=items,
                synced_at=synced_at,
            )
            repository.mark_missing_tools_deleted(
                runtime_id=self._runtime_id,
                active_keys=active_keys,
                synced_at=synced_at,
            )

        return RuntimeCatalogRefreshResult(
            ok=True,
            count=len(items),
            last_synced_at=synced_at,
        )

    async def list_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeGraphCatalogList:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            rows = repository.list_graphs(runtime_id=self._runtime_id)
            items = [self._graph_item(item) for item in rows]
            return RuntimeGraphCatalogList(
                count=len(items),
                graphs=items,
                last_synced_at=self._latest_synced_at(items),
            )

    async def refresh_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeCatalogRefreshResult:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        self._require_refresh_access(actor=actor, project_id=project_id)

        graph_map: dict[str, dict[str, Any]] = {}
        offset = 0
        limit = 200

        while True:
            payload = await self._upstream.request_json(
                "POST",
                "/assistants/search",
                payload={
                    "limit": limit,
                    "offset": offset,
                    "select": ["graph_id", "description"],
                },
                forwarded_headers=self._runtime_headers(actor=actor, project_id=project_id),
            )
            rows = self._normalize_graph_items(payload)
            if not rows:
                break

            for item in rows:
                graph_id = _clean(item.get("graph_id"))
                if not graph_id:
                    continue

                description = _clean(item.get("description")) or ""
                existing = graph_map.get(graph_id)
                if existing is None:
                    graph_map[graph_id] = {
                        "graph_id": graph_id,
                        "display_name": graph_id,
                        "description": description,
                    }
                    continue
                if not existing.get("description") and description:
                    existing["description"] = description

            if len(rows) < limit:
                break
            offset += len(rows)

        items = list(graph_map.values())
        synced_at = datetime.now(timezone.utc)
        active_keys = {graph_id for graph_id in (_clean(item.get("graph_id")) for item in items) if graph_id}

        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            repository.upsert_graph_items(
                runtime_id=self._runtime_id,
                items=items,
                synced_at=synced_at,
                source_type="assistant_search",
            )
            repository.mark_missing_graphs_deleted(
                runtime_id=self._runtime_id,
                active_keys=active_keys,
                synced_at=synced_at,
            )

        return RuntimeCatalogRefreshResult(
            ok=True,
            count=len(items),
            last_synced_at=synced_at,
        )
