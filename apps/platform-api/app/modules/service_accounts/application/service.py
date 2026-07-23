from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork, session_scope
from app.core.errors import BadRequestError, ConflictError, NotFoundError, ServiceUnavailableError
from app.core.identifiers import parse_uuid
from app.core.security import hash_password, verify_password
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.iam.domain import PlatformRole
from app.modules.service_accounts.application.contracts import (
    CreateServiceAccountCommand,
    CreateServiceAccountTokenCommand,
    ListServiceAccountsQuery,
    UpdateServiceAccountCommand,
)
from app.modules.service_accounts.domain import (
    CreatedServiceAccountToken,
    ServiceAccountItem,
    ServiceAccountPage,
    ServiceAccountTokenItem,
)
from app.modules.service_accounts.infra.sqlalchemy.repository import (
    SqlAlchemyServiceAccountsRepository,
)


def _normalize_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise BadRequestError(code="invalid_service_account_name", message="Invalid service account name")
    return normalized


def _normalize_roles(value: tuple[PlatformRole, ...] | tuple[str, ...]) -> tuple[str, ...]:
    normalized = sorted({str(role.value if isinstance(role, PlatformRole) else role).strip() for role in value if str(role).strip()})
    if not normalized:
        return (PlatformRole.VIEWER.value,)
    return tuple(normalized)


def _actor_identity(actor: ActorContext) -> str | None:
    return actor.user_id or actor.subject


class ServiceAccountsService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        default_token_ttl_days: int = 90,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._default_token_ttl_days = default_token_ttl_days
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _require_permission(self, *, actor: ActorContext, permission: PermissionCode) -> None:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=permission),
        )

    def _require_super_admin_role_permission(self, *, actor: ActorContext) -> None:
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_SUPER_ADMIN_MANAGE)

    def _token_item(self, item) -> ServiceAccountTokenItem:
        return ServiceAccountTokenItem(
            id=str(item.id),
            name=item.name,
            token_prefix=item.token_prefix,
            status=item.status,
            expires_at=item.expires_at,
            last_used_at=item.last_used_at,
            revoked_at=item.revoked_at,
            created_at=item.created_at,
        )

    def _service_account_item(self, item, *, tokens: list[ServiceAccountTokenItem]) -> ServiceAccountItem:
        return ServiceAccountItem(
            id=str(item.id),
            name=item.name,
            description=item.description,
            status=item.status,
            platform_roles=item.platform_roles,
            created_by=item.created_by,
            updated_by=item.updated_by,
            last_used_at=item.last_used_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
            tokens=tokens,
        )

    async def list_service_accounts(
        self,
        *,
        actor: ActorContext,
        query: ListServiceAccountsQuery,
    ) -> ServiceAccountPage:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_SERVICE_ACCOUNT_READ)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyServiceAccountsRepository(uow.session)
            items, total = repository.list_service_accounts(
                limit=query.limit,
                offset=query.offset,
                query=query.query,
                status=query.status,
            )
            result_items: list[ServiceAccountItem] = []
            for item in items:
                tokens = [self._token_item(token) for token in repository.list_tokens(service_account_id=item.id)]
                result_items.append(self._service_account_item(item, tokens=tokens))
            return ServiceAccountPage(items=result_items, total=total)

    async def create_service_account(
        self,
        *,
        actor: ActorContext,
        command: CreateServiceAccountCommand,
    ) -> ServiceAccountItem:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_SERVICE_ACCOUNT_WRITE)
        name = _normalize_name(command.name)
        roles = _normalize_roles(command.platform_roles)
        if PlatformRole.SUPER_ADMIN.value in roles:
            self._require_super_admin_role_permission(actor=actor)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyServiceAccountsRepository(uow.session)
            if repository.get_service_account_by_name(name) is not None:
                raise ConflictError(
                    code="service_account_name_conflict",
                    message="Service account name already exists",
                )
            created = repository.create_service_account(
                name=name,
                description=command.description.strip() if command.description else None,
                platform_roles=roles,
                created_by=_actor_identity(actor),
            )
            return self._service_account_item(created, tokens=[])

    async def update_service_account(
        self,
        *,
        actor: ActorContext,
        service_account_id: str,
        command: UpdateServiceAccountCommand,
    ) -> ServiceAccountItem:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_SERVICE_ACCOUNT_WRITE)
        account_uuid = parse_uuid(service_account_id, code="invalid_service_account_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyServiceAccountsRepository(uow.session)
            current = repository.get_service_account_by_id(account_uuid)
            if current is None:
                raise NotFoundError(code="service_account_not_found", message="Service account not found")
            next_roles = (
                _normalize_roles(command.platform_roles)
                if command.platform_roles is not None
                else current.platform_roles
            )
            if (PlatformRole.SUPER_ADMIN.value in current.platform_roles) != (
                PlatformRole.SUPER_ADMIN.value in next_roles
            ):
                self._require_super_admin_role_permission(actor=actor)
            updated = repository.update_service_account(
                service_account_id=account_uuid,
                description=command.description.strip() if command.description is not None else None,
                status=command.status,
                platform_roles=next_roles if command.platform_roles is not None else None,
                updated_by=_actor_identity(actor),
            )
            if updated is None:
                raise NotFoundError(code="service_account_not_found", message="Service account not found")
            tokens = [self._token_item(token) for token in repository.list_tokens(service_account_id=updated.id)]
            return self._service_account_item(updated, tokens=tokens)

    async def create_service_account_token(
        self,
        *,
        actor: ActorContext,
        service_account_id: str,
        command: CreateServiceAccountTokenCommand,
    ) -> CreatedServiceAccountToken:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_SERVICE_ACCOUNT_WRITE)
        account_uuid = parse_uuid(service_account_id, code="invalid_service_account_id")
        expires_in_days = command.expires_in_days or self._default_token_ttl_days
        plain_text_token = f"pkv2_{secrets.token_urlsafe(24)}"
        token_prefix = plain_text_token[:20]
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyServiceAccountsRepository(uow.session)
            account = repository.get_service_account_by_id(account_uuid)
            if account is None:
                raise NotFoundError(code="service_account_not_found", message="Service account not found")
            if PlatformRole.SUPER_ADMIN.value in account.platform_roles:
                self._require_super_admin_role_permission(actor=actor)
            token = repository.create_token(
                service_account_id=account_uuid,
                name=_normalize_name(command.name),
                token_prefix=token_prefix,
                token_secret_hash=hash_password(plain_text_token),
                expires_at=expires_at,
                created_by=_actor_identity(actor),
            )
            return CreatedServiceAccountToken(
                token=self._token_item(token),
                plain_text_token=plain_text_token,
            )

    async def revoke_service_account_token(
        self,
        *,
        actor: ActorContext,
        service_account_id: str,
        token_id: str,
    ) -> ServiceAccountTokenItem:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, permission=PermissionCode.PLATFORM_SERVICE_ACCOUNT_WRITE)
        account_uuid = parse_uuid(service_account_id, code="invalid_service_account_id")
        token_uuid = parse_uuid(token_id, code="invalid_service_account_token_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyServiceAccountsRepository(uow.session)
            revoked = repository.revoke_token(service_account_id=account_uuid, token_id=token_uuid)
            if revoked is None:
                raise NotFoundError(
                    code="service_account_token_not_found",
                    message="Service account token not found",
                )
            return self._token_item(revoked)

    def authenticate_api_key(self, api_key: str) -> ActorContext | None:
        session_factory = self._session_factory
        if session_factory is None:
            return None
        token_prefix = api_key[:20]
        with session_scope(session_factory) as session:
            repository = SqlAlchemyServiceAccountsRepository(session)
            token = repository.get_active_token_by_prefix(token_prefix=token_prefix)
            if token is None:
                return None
            secret_hash = repository.get_token_secret_hash(token_id=token.id)
            if not secret_hash or not verify_password(api_key, secret_hash):
                return None
            account = repository.get_service_account_by_id(token.service_account_id)
            if account is None or account.status != "active":
                return None
            repository.touch_token_usage(
                token_id=token.id,
                service_account_id=account.id,
                used_at=datetime.now(timezone.utc),
            )
            return ActorContext(
                subject=account.name,
                platform_roles=account.platform_roles,
                principal_type="service_account",
                authentication_type="api_key",
                credential_id=str(token.id),
            )

    def summarize(self) -> dict[str, int]:
        session_factory = self._session_factory
        if session_factory is None:
            return {
                "total_accounts": 0,
                "active_accounts": 0,
                "active_tokens": 0,
                "revoked_tokens": 0,
            }
        with session_scope(session_factory) as session:
            repository = SqlAlchemyServiceAccountsRepository(session)
            return repository.summarize()
