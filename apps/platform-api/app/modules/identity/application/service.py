from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    ConflictError,
    NotAuthenticatedError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.modules.identity.application.contracts import (
    ChangePasswordCommand,
    LoginCommand,
    LogoutCommand,
    RefreshSessionCommand,
    UpdateCurrentUserProfileCommand,
)
from app.modules.identity.application.ports import (
    IdentityRepository,
    ProjectRolesReader,
    StoredUser,
)
from app.modules.identity.domain import AuthenticatedSession, SessionTokens, UserProfile, UserStatus
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_user_id(raw_user_id: str | None) -> UUID:
    if not raw_user_id:
        raise NotAuthenticatedError()
    try:
        return UUID(raw_user_id)
    except ValueError as exc:
        raise NotAuthenticatedError() from exc


class IdentityService:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session] | None,
        project_roles_reader_factory: Callable[[Session], ProjectRolesReader] | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._project_roles_reader_factory = project_roles_reader_factory

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _build_repository(self, session: Session) -> IdentityRepository:
        return SqlAlchemyIdentityRepository(session)

    def _project_roles(self, session: Session, *, user_id: UUID) -> dict[str, tuple[str, ...]]:
        if self._project_roles_reader_factory is None:
            return {}
        repository = self._project_roles_reader_factory(session)
        return repository.list_user_project_roles(user_id=user_id)

    def _user_profile(
        self,
        user: StoredUser,
        *,
        project_roles: dict[str, tuple[str, ...]] | None = None,
    ) -> UserProfile:
        status = (
            UserStatus.ACTIVE
            if user.status == UserStatus.ACTIVE.value
            else UserStatus.DISABLED
        )
        return UserProfile(
            id=str(user.id),
            username=user.username,
            email=user.email,
            status=status,
            platform_roles=user.platform_roles,
            project_roles=project_roles or {},
        )

    def _issue_session_tokens(
        self,
        *,
        repository: IdentityRepository,
        user: StoredUser,
    ) -> SessionTokens:
        access_token = create_access_token(
            user_id=str(user.id),
            username=user.username,
            settings=self._settings,
        )
        refresh_token, token_id = create_refresh_token(
            user_id=str(user.id),
            username=user.username,
            settings=self._settings,
        )
        repository.create_refresh_token(
            user_id=user.id,
            token_id=token_id,
            expires_at=_now() + timedelta(seconds=self._settings.jwt_refresh_ttl_seconds),
        )
        return SessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def login(self, command: LoginCommand) -> tuple[AuthenticatedSession, ActorContext]:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = self._build_repository(uow.session)
            user = repository.get_user_by_username(command.username.strip())
            if (
                user is None
                or user.status != UserStatus.ACTIVE.value
                or not verify_password(command.password, user.password_hash)
            ):
                raise PlatformApiError(
                    code="invalid_credentials",
                    status_code=401,
                    message="Invalid username or password",
                )
            tokens = self._issue_session_tokens(repository=repository, user=user)
            project_roles = self._project_roles(uow.session, user_id=user.id)
            session = AuthenticatedSession(
                tokens=tokens,
                user=self._user_profile(
                    user,
                    project_roles=project_roles,
                ),
            )
            return session, ActorContext(
                user_id=str(user.id),
                subject=user.external_subject,
                email=user.email,
                platform_roles=user.platform_roles,
                project_roles=project_roles,
            )

    async def refresh(self, command: RefreshSessionCommand) -> SessionTokens:
        session_factory = self._require_session_factory()
        try:
            payload = decode_refresh_token(command.refresh_token, self._settings)
        except InvalidTokenError as exc:
            raise PlatformApiError(
                code="invalid_refresh_token",
                status_code=401,
                message="Refresh token validation failed",
            ) from exc

        token_id = str(payload.get("jti") or "")
        username = str(payload.get("username") or "")
        try:
            user_id = UUID(str(payload.get("sub") or ""))
        except ValueError as exc:
            raise PlatformApiError(
                code="invalid_refresh_token",
                status_code=401,
                message="Refresh token payload is incomplete",
            ) from exc
        if not token_id or not username:
            raise PlatformApiError(
                code="invalid_refresh_token",
                status_code=401,
                message="Refresh token payload is incomplete",
            )

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = self._build_repository(uow.session)
            refresh_token = repository.get_refresh_token(token_id)
            if refresh_token is None or refresh_token.revoked_at is not None:
                raise PlatformApiError(
                    code="refresh_token_revoked",
                    status_code=401,
                    message="Refresh token has been revoked",
                )
            user = repository.get_user_by_id(user_id)
            if user is None or user.status != UserStatus.ACTIVE.value:
                raise PlatformApiError(
                    code="user_not_active",
                    status_code=401,
                    message="User is not active",
                )
            repository.revoke_refresh_token(token_id)
            return self._issue_session_tokens(repository=repository, user=user)

    async def logout(self, command: LogoutCommand) -> None:
        session_factory = self._require_session_factory()
        try:
            payload = decode_refresh_token(command.refresh_token, self._settings)
        except InvalidTokenError as exc:
            raise PlatformApiError(
                code="invalid_refresh_token",
                status_code=400,
                message="Refresh token validation failed",
            ) from exc
        token_id = str(payload.get("jti") or "")
        if not token_id:
            raise PlatformApiError(
                code="invalid_refresh_token",
                status_code=400,
                message="Refresh token payload is incomplete",
            )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = self._build_repository(uow.session)
            repository.revoke_refresh_token(token_id)

    async def change_password(
        self,
        *,
        actor: ActorContext,
        command: ChangePasswordCommand,
    ) -> None:
        session_factory = self._require_session_factory()
        user_id = _parse_user_id(actor.user_id)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = self._build_repository(uow.session)
            user = repository.get_user_by_id(user_id)
            if user is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            if not verify_password(command.old_password, user.password_hash):
                raise PlatformApiError(
                    code="invalid_credentials",
                    status_code=401,
                    message="Current password is invalid",
                )
            repository.update_user_password_hash(
                user_id,
                hash_password(command.new_password),
            )
            repository.revoke_all_refresh_tokens_for_user(user_id)

    async def get_current_user(self, actor: ActorContext) -> UserProfile:
        session_factory = self._require_session_factory()
        user_id = _parse_user_id(actor.user_id)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = self._build_repository(uow.session)
            user = repository.get_user_by_id(user_id)
            if user is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            return self._user_profile(user, project_roles=dict(actor.project_roles))

    async def update_current_user(
        self,
        *,
        actor: ActorContext,
        command: UpdateCurrentUserProfileCommand,
    ) -> UserProfile:
        session_factory = self._require_session_factory()
        user_id = _parse_user_id(actor.user_id)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = self._build_repository(uow.session)
            user = repository.get_user_by_id(user_id)
            if user is None:
                raise NotFoundError(message="User not found", code="user_not_found")

            next_username = command.username.strip() if command.username is not None else user.username
            next_email_raw = command.email if command.email is not None else user.email
            next_email = next_email_raw.strip() if isinstance(next_email_raw, str) else None
            if next_email == "":
                next_email = None

            existing_user = repository.get_user_by_username(next_username)
            if existing_user is not None and existing_user.id != user.id:
                raise ConflictError(
                    code="username_conflict",
                    message="Username already exists",
                )

            updated = repository.update_user_profile(
                user_id,
                username=next_username,
                email=next_email,
            )
            if updated is None:
                raise NotFoundError(message="User not found", code="user_not_found")
            return self._user_profile(updated, project_roles=dict(actor.project_roles))

    async def ensure_bootstrap_admin(self) -> str | None:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = self._build_repository(uow.session)
            return repository.reconcile_bootstrap_admin(
                username=self._settings.bootstrap_admin_username,
                password_hash=hash_password(self._settings.bootstrap_admin_password),
            )
