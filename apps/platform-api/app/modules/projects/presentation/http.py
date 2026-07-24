from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import sessionmaker

from app.core.context.models import ActorContext
from app.core.schemas import AckResponse
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.projects.application.contracts import (
    CreateProjectCommand,
    ListProjectMembersQuery,
    ListProjectsQuery,
    ProjectTakeoverCommand,
    RestoreProjectAdminCommand,
    UpsertProjectMemberCommand,
)
from app.modules.projects.application.service import ProjectsService
from app.modules.projects.domain import (
    ProjectAccess,
    ProjectMemberPage,
    ProjectMemberCandidatePage,
    ProjectMemberView,
    ProjectPage,
    ProjectSummary,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_projects_service(request: Request) -> ProjectsService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return ProjectsService(session_factory=session_factory)


@router.get("", response_model=ProjectPage)
async def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectPage:
    return await service.list_projects(
        actor=actor,
        query=ListProjectsQuery(limit=limit, offset=offset, query=query),
    )


@router.post("", response_model=ProjectSummary)
async def create_project(
    payload: CreateProjectCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectSummary:
    return await service.create_project(actor=actor, command=payload)


@router.get("/{project_id}/access", response_model=ProjectAccess)
async def get_project_access(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectAccess:
    return await service.get_access(actor=actor, project_id=project_id)


@router.post("/{project_id}/takeover", response_model=ProjectMemberView)
async def takeover_project(
    project_id: str,
    payload: ProjectTakeoverCommand,
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectMemberView:
    request.state.audit_metadata = {"reason": payload.reason.strip()}
    return await service.takeover(actor=actor, project_id=project_id, command=payload)


@router.post("/{project_id}/admin-recovery", response_model=ProjectMemberView)
async def restore_project_admin(
    project_id: str,
    payload: RestoreProjectAdminCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectMemberView:
    return await service.restore_admin(actor=actor, project_id=project_id, command=payload)


@router.post("/{project_id}/archive", response_model=ProjectSummary)
async def archive_project(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectSummary:
    return await service.archive_project(actor=actor, project_id=project_id)


@router.post("/{project_id}/restore", response_model=ProjectSummary)
async def restore_project(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectSummary:
    return await service.restore_project(actor=actor, project_id=project_id)


@router.delete("/{project_id}", response_model=AckResponse)
async def delete_project(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> AckResponse:
    await service.delete_project(actor=actor, project_id=project_id)
    return AckResponse()


@router.get("/{project_id}/members", response_model=ProjectMemberPage)
async def list_project_members(
    project_id: str,
    query: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectMemberPage:
    return await service.list_members(
        actor=actor,
        project_id=project_id,
        query=ListProjectMembersQuery(query=query),
    )


@router.get("/{project_id}/member-candidates", response_model=ProjectMemberCandidatePage)
async def list_project_member_candidates(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectMemberCandidatePage:
    return await service.list_member_candidates(
        actor=actor,
        project_id=project_id,
        limit=limit,
        offset=offset,
        query=query,
    )


@router.put("/{project_id}/members/{user_id}", response_model=ProjectMemberView)
async def upsert_project_member(
    project_id: str,
    user_id: str,
    payload: UpsertProjectMemberCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> ProjectMemberView:
    return await service.upsert_member(
        actor=actor,
        project_id=project_id,
        user_id=user_id,
        command=payload,
    )


@router.delete("/{project_id}/members/{user_id}", response_model=AckResponse)
async def delete_project_member(
    project_id: str,
    user_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectsService = Depends(get_projects_service),
) -> AckResponse:
    await service.remove_member(
        actor=actor,
        project_id=project_id,
        user_id=user_id,
    )
    return AckResponse()
