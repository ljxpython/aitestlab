from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import sessionmaker

from app.core.context.models import ActorContext
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.identity.domain import UserStatus
from app.modules.users.application import CreateUserCommand, ListUsersQuery, UpdateUserCommand, UsersService
from app.modules.users.application.contracts import ResetUserPasswordCommand
from app.modules.users.domain import UserItem, UserPage, UserProjectPage

router = APIRouter(prefix="/api/users", tags=["users"])


def get_users_service(request: Request) -> UsersService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return UsersService(session_factory=session_factory)


@router.get("", response_model=UserPage)
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    status: UserStatus | None = Query(default=None),
    exclude_user_ids: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: UsersService = Depends(get_users_service),
) -> UserPage:
    normalized_excluded_ids = tuple(
        item.strip() for item in (exclude_user_ids or "").split(",") if item.strip()
    )
    return await service.list_users(
        actor=actor,
        query=ListUsersQuery(
            limit=limit,
            offset=offset,
            query=query,
            status=status,
            exclude_user_ids=normalized_excluded_ids,
        ),
    )


@router.post("", response_model=UserItem)
async def create_user(
    payload: CreateUserCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: UsersService = Depends(get_users_service),
) -> UserItem:
    return await service.create_user(actor=actor, command=payload)


@router.get("/{user_id}", response_model=UserItem)
async def get_user(
    user_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: UsersService = Depends(get_users_service),
) -> UserItem:
    return await service.get_user(actor=actor, user_id=user_id)


@router.get("/{user_id}/projects", response_model=UserProjectPage)
async def list_user_projects(
    user_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: UsersService = Depends(get_users_service),
) -> UserProjectPage:
    return await service.list_user_projects(actor=actor, user_id=user_id)


@router.patch("/{user_id}", response_model=UserItem)
async def update_user(
    user_id: str,
    payload: UpdateUserCommand,
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: UsersService = Depends(get_users_service),
) -> UserItem:
    categories = {
        category
        for fields, category in (
            ({"username"}, "profile"),
            ({"status"}, "status"),
            ({"platform_roles", "is_super_admin"}, "roles"),
            ({"password"}, "credentials"),
        )
        if payload.model_fields_set & fields
    }
    request.state.audit_action = (
        f"user.{next(iter(categories))}.updated"
        if len(categories) == 1 and "credentials" not in categories
        else "user.credentials.reset"
        if categories == {"credentials"}
        else "user.governance.updated"
    )
    return await service.update_user(actor=actor, user_id=user_id, command=payload)


@router.post("/{user_id}/credentials/reset", response_model=UserItem)
async def reset_user_password(
    user_id: str,
    payload: ResetUserPasswordCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: UsersService = Depends(get_users_service),
) -> UserItem:
    return await service.reset_password(actor=actor, user_id=user_id, command=payload)
