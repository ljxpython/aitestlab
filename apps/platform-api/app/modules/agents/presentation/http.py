from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import sessionmaker

from app.adapters.langgraph import (
    GraphParameterSchemaProvider,
    LangGraphAssistantsClient,
    build_forward_headers,
)
from app.core.config import Settings
from app.core.context.models import ActorContext, ProjectContext
from app.core.schemas import AckResponse
from app.entrypoints.http.dependencies import get_actor_context, get_project_context
from app.modules.agents.application import (
    AssistantsService,
    CreateAssistantCommand,
    ListAssistantsQuery,
    UpdateAssistantCommand,
)
from app.modules.agents.domain import AssistantItem, AssistantPage

router = APIRouter(tags=["assistants"])


def get_assistants_service(request: Request) -> AssistantsService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    settings: Settings = request.app.state.settings
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    forwarded_headers = build_forward_headers(
        request.headers,
        request_id=getattr(request.state, "request_id", None),
    )
    upstream = LangGraphAssistantsClient(
        base_url=settings.langgraph_upstream_url,
        api_key=settings.langgraph_upstream_api_key,
        timeout_seconds=settings.langgraph_upstream_timeout_seconds,
        forwarded_headers=forwarded_headers,
    )
    schema_provider = GraphParameterSchemaProvider(settings)
    return AssistantsService(
        session_factory=session_factory,
        runtime_base_url=settings.langgraph_upstream_url,
        upstream=upstream,
        schema_provider=schema_provider,
    )


@router.get("/api/projects/{project_id}/assistants", response_model=AssistantPage)
@router.get("/api/projects/{project_id}/agents", response_model=AssistantPage)
async def list_assistants(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    graph_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantPage:
    return await service.list_assistants(
        actor=actor,
        project_id=project_id,
        query=ListAssistantsQuery(
            limit=limit,
            offset=offset,
            query=query,
            graph_id=graph_id,
        ),
    )


@router.post("/api/projects/{project_id}/assistants", response_model=AssistantItem)
@router.post("/api/projects/{project_id}/agents", response_model=AssistantItem)
async def create_assistant(
    request: Request,
    project_id: str,
    payload: CreateAssistantCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantItem:
    request.state.audit_project_id = project_id
    return await service.create_assistant(
        actor=actor,
        project_id=project_id,
        command=payload,
    )


@router.get("/api/assistants/{assistant_id}", response_model=AssistantItem)
@router.get("/api/agents/{assistant_id}", response_model=AssistantItem)
async def get_assistant(
    request: Request,
    assistant_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantItem:
    item = await service.get_assistant(actor=actor, assistant_id=assistant_id)
    request.state.audit_project_id = item.project_id
    return item


@router.patch("/api/assistants/{assistant_id}", response_model=AssistantItem)
@router.patch("/api/agents/{assistant_id}", response_model=AssistantItem)
async def update_assistant(
    request: Request,
    assistant_id: str,
    payload: UpdateAssistantCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantItem:
    item = await service.update_assistant(
        actor=actor,
        assistant_id=assistant_id,
        command=payload,
    )
    request.state.audit_project_id = item.project_id
    return item


@router.delete("/api/assistants/{assistant_id}", response_model=AckResponse)
@router.delete("/api/agents/{assistant_id}", response_model=AckResponse)
async def delete_assistant(
    request: Request,
    assistant_id: str,
    delete_runtime: bool = Query(default=False),
    delete_threads: bool = Query(default=False),
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AckResponse:
    request.state.audit_project_id = await service.delete_assistant(
        actor=actor,
        assistant_id=assistant_id,
        delete_runtime=delete_runtime,
        delete_threads=delete_threads,
    )
    return AckResponse()


@router.post("/api/assistants/{assistant_id}/resync", response_model=AssistantItem)
@router.post("/api/agents/{assistant_id}/resync", response_model=AssistantItem)
async def resync_assistant(
    request: Request,
    assistant_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantItem:
    item = await service.resync_assistant(actor=actor, assistant_id=assistant_id)
    request.state.audit_project_id = item.project_id
    return item


@router.get("/api/graphs/{graph_id}/assistant-parameter-schema")
async def get_assistant_parameter_schema(
    request: Request,
    graph_id: str,
    actor: ActorContext = Depends(get_actor_context),
    project: ProjectContext = Depends(get_project_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> dict[str, object]:
    if project.project_id:
        request.state.audit_project_id = project.project_id
    return await service.get_parameter_schema(
        actor=actor,
        graph_id=graph_id,
        project_id=project.project_id,
    )
