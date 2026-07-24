from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.service_accounts.application.contracts import (
    CreateServiceAccountCommand,
    CreateServiceAccountTokenCommand,
    ListServiceAccountsQuery,
    UpdateServiceAccountCommand,
    UpsertServiceAccountProjectGrantCommand,
)
from app.modules.service_accounts.application.service import ServiceAccountsService
from app.modules.service_accounts.domain import (
    CreatedServiceAccountToken,
    ServiceAccountItem,
    ServiceAccountPage,
    ServiceAccountTokenItem,
    ServiceAccountProjectGrantItem,
)

router = APIRouter(prefix="/api/service-accounts", tags=["service-accounts"])


def get_service_accounts_service(request: Request) -> ServiceAccountsService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    settings: Settings = request.app.state.settings
    return ServiceAccountsService(
        session_factory=session_factory,
        default_token_ttl_days=settings.service_account_token_default_ttl_days,
    )


@router.get("/{service_account_id}/project-grants", response_model=list[ServiceAccountProjectGrantItem])
async def list_service_account_project_grants(
    service_account_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> list[ServiceAccountProjectGrantItem]:
    return await service.list_project_grants(actor=actor, service_account_id=service_account_id)


@router.put(
    "/{service_account_id}/project-grants/{project_id}",
    response_model=ServiceAccountProjectGrantItem,
)
async def upsert_service_account_project_grant(
    service_account_id: str,
    project_id: str,
    payload: UpsertServiceAccountProjectGrantCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountProjectGrantItem:
    return await service.upsert_project_grant(
        actor=actor,
        service_account_id=service_account_id,
        project_id=project_id,
        command=payload,
    )


@router.delete("/{service_account_id}/project-grants/{project_id}", status_code=204)
async def delete_service_account_project_grant(
    service_account_id: str,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> Response:
    await service.delete_project_grant(
        actor=actor,
        service_account_id=service_account_id,
        project_id=project_id,
    )
    return Response(status_code=204)

@router.get("", response_model=ServiceAccountPage)
async def list_service_accounts(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountPage:
    return await service.list_service_accounts(
        actor=actor,
        query=ListServiceAccountsQuery(limit=limit, offset=offset, query=query, status=status),
    )


@router.post("", response_model=ServiceAccountItem)
async def create_service_account(
    payload: CreateServiceAccountCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountItem:
    return await service.create_service_account(actor=actor, command=payload)


@router.patch("/{service_account_id}", response_model=ServiceAccountItem)
async def update_service_account(
    service_account_id: str,
    payload: UpdateServiceAccountCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountItem:
    return await service.update_service_account(
        actor=actor,
        service_account_id=service_account_id,
        command=payload,
    )


@router.post("/{service_account_id}/tokens", response_model=CreatedServiceAccountToken)
async def create_service_account_token(
    service_account_id: str,
    payload: CreateServiceAccountTokenCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> CreatedServiceAccountToken:
    return await service.create_service_account_token(
        actor=actor,
        service_account_id=service_account_id,
        command=payload,
    )


@router.delete("/{service_account_id}/tokens/{token_id}", response_model=ServiceAccountTokenItem)
async def revoke_service_account_token(
    service_account_id: str,
    token_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountTokenItem:
    return await service.revoke_service_account_token(
        actor=actor,
        service_account_id=service_account_id,
        token_id=token_id,
    )
