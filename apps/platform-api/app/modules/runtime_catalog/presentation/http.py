from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import sessionmaker

from app.adapters.langgraph import build_forward_headers
from app.core.config import Settings
from app.core.context.models import ActorContext
from app.core.errors import BadRequestError
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.runtime_catalog.application import RuntimeCatalogService
from app.modules.runtime_catalog.bootstrap import build_runtime_catalog_service
from app.modules.runtime_catalog.domain import (
    RuntimeCatalogRefreshResult,
    RuntimeGraphCatalogList,
    RuntimeModelCatalogList,
    RuntimeModelCatalogItem,
    RuntimeModelCreate,
    RuntimeModelUpdate,
    RuntimeToolCatalogList,
)

router = APIRouter(prefix="/api/runtime", tags=["runtime-catalog"])


def _require_project_id(request: Request) -> str:
    project_id = getattr(request.state.platform_context.project, "project_id", None)
    normalized = project_id.strip() if isinstance(project_id, str) else ""
    if not normalized:
        raise BadRequestError(
            code="project_id_required",
            message="x-project-id header is required",
        )
    request.state.audit_project_id = normalized
    return normalized


def get_runtime_catalog_service(request: Request) -> RuntimeCatalogService:
    settings: Settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    platform_context = getattr(request.state, "platform_context", None)
    tenant = getattr(platform_context, "tenant", None)
    return build_runtime_catalog_service(
        settings=settings,
        session_factory=session_factory,
        forwarded_headers=build_forward_headers(
            request.headers,
            request_id=getattr(request.state, "request_id", None),
        ),
        tenant_id=getattr(tenant, "tenant_id", None) or "__default",
    )


@router.get("/internal/model-config")
async def get_internal_runtime_model_config(
    request: Request,
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> dict[str, str]:
    """Serve a model connection only to Runtime using a short-lived opaque reference."""
    reference = request.headers.get("x-runtime-model-ref", "").strip()
    project_id = request.headers.get("x-project-id", "").strip()
    if not reference or not project_id:
        raise BadRequestError(
            code="runtime_model_reference_required",
            message="Runtime model reference and project scope are required",
        )
    return await service.resolve_model_connection(reference=reference, project_id=project_id)


@router.get("/models", response_model=RuntimeModelCatalogList)
async def list_runtime_models(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeModelCatalogList:
    project_id = _require_project_id(request)
    return await service.list_models(actor=actor, project_id=project_id)


@router.post("/models/refresh", response_model=RuntimeCatalogRefreshResult)
async def refresh_runtime_models(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeCatalogRefreshResult:
    project_id = _require_project_id(request)
    return await service.refresh_models(actor=actor, project_id=project_id)


@router.post("/models", response_model=RuntimeModelCatalogItem, status_code=201)
async def create_runtime_model(
    request: Request,
    payload: RuntimeModelCreate,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeModelCatalogItem:
    project_id = _require_project_id(request)
    return await service.create_model(actor=actor, project_id=project_id, payload=payload)


@router.patch("/models/{model_id}", response_model=RuntimeModelCatalogItem)
async def update_runtime_model(
    model_id: str,
    request: Request,
    payload: RuntimeModelUpdate,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeModelCatalogItem:
    project_id = _require_project_id(request)
    return await service.update_model(
        actor=actor,
        project_id=project_id,
        model_id=model_id,
        payload=payload,
    )


@router.get("/tools", response_model=RuntimeToolCatalogList)
async def list_runtime_tools(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeToolCatalogList:
    project_id = _require_project_id(request)
    return await service.list_tools(actor=actor, project_id=project_id)


@router.post("/tools/refresh", response_model=RuntimeCatalogRefreshResult)
async def refresh_runtime_tools(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeCatalogRefreshResult:
    project_id = _require_project_id(request)
    return await service.refresh_tools(actor=actor, project_id=project_id)


@router.get("/graphs", response_model=RuntimeGraphCatalogList)
async def list_runtime_graphs(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeGraphCatalogList:
    project_id = _require_project_id(request)
    return await service.list_graphs(actor=actor, project_id=project_id)


@router.post("/graphs/refresh", response_model=RuntimeCatalogRefreshResult)
async def refresh_runtime_graphs(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeCatalogRefreshResult:
    project_id = _require_project_id(request)
    return await service.refresh_graphs(actor=actor, project_id=project_id)
