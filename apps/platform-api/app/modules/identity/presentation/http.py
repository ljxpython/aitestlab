from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.core.errors import ServiceUnavailableError
from app.core.schemas import AckResponse
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.identity.application.contracts import (
    ChangePasswordCommand,
    LoginCommand,
    LogoutCommand,
    RefreshSessionCommand,
    UpdateCurrentUserProfileCommand,
)
from app.modules.identity.application.service import IdentityService
from app.modules.identity.domain import AuthenticatedSession, SessionTokens, UserProfile

router = APIRouter(prefix="/api/identity", tags=["identity"])


def get_identity_service(request: Request) -> IdentityService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    settings: Settings = request.app.state.settings
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        raise ServiceUnavailableError(
            code="invalid_session_factory",
            message="Database session factory is invalid",
        )
    return IdentityService(
        settings=settings,
        session_factory=session_factory,
    )


@router.post("/session", response_model=AuthenticatedSession)
async def login(
    payload: LoginCommand,
    request: Request,
    service: IdentityService = Depends(get_identity_service),
) -> AuthenticatedSession:
    session, actor = await service.login(payload)
    request.state.audit_actor = actor
    return session


@router.post("/session/refresh", response_model=SessionTokens)
async def refresh_session(
    payload: RefreshSessionCommand,
    service: IdentityService = Depends(get_identity_service),
) -> SessionTokens:
    return await service.refresh(payload)


@router.delete("/session", response_model=AckResponse)
async def logout(
    payload: LogoutCommand,
    service: IdentityService = Depends(get_identity_service),
) -> AckResponse:
    await service.logout(payload)
    return AckResponse()


@router.get("/me", response_model=UserProfile)
async def get_me(
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserProfile:
    return await service.get_current_user(actor)


@router.patch("/me", response_model=UserProfile)
async def update_me(
    payload: UpdateCurrentUserProfileCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserProfile:
    return await service.update_current_user(actor=actor, command=payload)


@router.post("/password/change", response_model=SessionTokens)
async def change_password(
    payload: ChangePasswordCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> SessionTokens:
    return await service.change_password(actor=actor, command=payload)
