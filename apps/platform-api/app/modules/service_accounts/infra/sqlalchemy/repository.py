from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.service_accounts.application.ports import (
    StoredServiceAccount,
    StoredServiceAccountToken,
    StoredServiceAccountProjectGrant,
)
from app.modules.iam.domain import ProjectRole
from app.modules.service_accounts.infra.sqlalchemy.models import (
    ServiceAccountRecord,
    ServiceAccountProjectGrantRecord,
    ServiceAccountTokenRecord,
)


def _to_service_account(record: ServiceAccountRecord) -> StoredServiceAccount:
    return StoredServiceAccount(
        id=record.id,
        name=record.name,
        description=record.description,
        status=record.status,
        platform_roles=tuple(sorted(str(role) for role in (record.platform_roles_json or []))),
        created_by=record.created_by,
        updated_by=record.updated_by,
        last_used_at=record.last_used_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_token(record: ServiceAccountTokenRecord) -> StoredServiceAccountToken:
    return StoredServiceAccountToken(
        id=record.id,
        service_account_id=record.service_account_id,
        name=record.name,
        token_prefix=record.token_prefix,
        status=record.status,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _to_grant(record: ServiceAccountProjectGrantRecord) -> StoredServiceAccountProjectGrant:
    return StoredServiceAccountProjectGrant(
        id=record.id,
        service_account_id=record.service_account_id,
        project_id=record.project_id,
        role=ProjectRole.from_db(record.role).value,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SqlAlchemyServiceAccountsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_service_accounts(
        self,
        *,
        limit: int,
        offset: int,
        query: str | None,
        status: str | None,
    ) -> tuple[list[StoredServiceAccount], int]:
        filters = []
        if query:
            normalized = f"%{query.strip()}%"
            filters.append(
                or_(
                    ServiceAccountRecord.name.ilike(normalized),
                    ServiceAccountRecord.description.ilike(normalized),
                )
            )
        if status:
            filters.append(ServiceAccountRecord.status == status)

        stmt = (
            select(ServiceAccountRecord)
            .where(*filters)
            .order_by(ServiceAccountRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list(self.session.scalars(stmt).all())
        total = int(
            self.session.scalar(
                select(func.count()).select_from(ServiceAccountRecord).where(*filters)
            )
            or 0
        )
        return [_to_service_account(row) for row in rows], total

    def get_service_account_by_id(self, service_account_id: UUID) -> StoredServiceAccount | None:
        record = self.session.get(ServiceAccountRecord, service_account_id)
        return _to_service_account(record) if record is not None else None

    def get_service_account_by_name(self, name: str) -> StoredServiceAccount | None:
        stmt = select(ServiceAccountRecord).where(ServiceAccountRecord.name == name).limit(1)
        record = self.session.scalar(stmt)
        return _to_service_account(record) if record is not None else None

    def create_service_account(
        self,
        *,
        name: str,
        description: str | None,
        platform_roles: tuple[str, ...],
        created_by: str | None,
    ) -> StoredServiceAccount:
        record = ServiceAccountRecord(
            name=name,
            description=description,
            status="active",
            platform_roles_json=list(platform_roles),
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return _to_service_account(record)

    def update_service_account(
        self,
        *,
        service_account_id: UUID,
        description: str | None,
        status: str | None,
        platform_roles: tuple[str, ...] | None,
        updated_by: str | None,
    ) -> StoredServiceAccount | None:
        record = self.session.get(ServiceAccountRecord, service_account_id)
        if record is None:
            return None
        if description is not None:
            record.description = description
        if status is not None:
            record.status = status
        if platform_roles is not None:
            record.platform_roles_json = list(platform_roles)
        record.updated_by = updated_by
        self.session.flush()
        self.session.refresh(record)
        return _to_service_account(record)

    def list_tokens(self, *, service_account_id: UUID) -> list[StoredServiceAccountToken]:
        stmt = (
            select(ServiceAccountTokenRecord)
            .where(ServiceAccountTokenRecord.service_account_id == service_account_id)
            .order_by(ServiceAccountTokenRecord.created_at.desc())
        )
        return [_to_token(row) for row in self.session.scalars(stmt).all()]

    def create_token(
        self,
        *,
        service_account_id: UUID,
        name: str,
        token_prefix: str,
        token_secret_hash: str,
        expires_at: datetime | None,
        created_by: str | None,
    ) -> StoredServiceAccountToken:
        record = ServiceAccountTokenRecord(
            service_account_id=service_account_id,
            name=name,
            token_prefix=token_prefix,
            token_secret_hash=token_secret_hash,
            expires_at=expires_at,
            created_by=created_by,
            status="active",
        )
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return _to_token(record)

    def get_active_token_by_prefix(self, *, token_prefix: str) -> StoredServiceAccountToken | None:
        now = datetime.now(timezone.utc)
        stmt = (
            select(ServiceAccountTokenRecord)
            .where(
                ServiceAccountTokenRecord.token_prefix == token_prefix,
                ServiceAccountTokenRecord.status == "active",
                or_(
                    ServiceAccountTokenRecord.expires_at.is_(None),
                    ServiceAccountTokenRecord.expires_at > now,
                ),
            )
            .order_by(ServiceAccountTokenRecord.created_at.desc())
            .limit(1)
        )
        record = self.session.scalar(stmt)
        return _to_token(record) if record is not None else None

    def get_token_secret_hash(self, *, token_id: UUID) -> str | None:
        record = self.session.get(ServiceAccountTokenRecord, token_id)
        return record.token_secret_hash if record is not None else None

    def revoke_token(
        self,
        *,
        service_account_id: UUID,
        token_id: UUID,
    ) -> StoredServiceAccountToken | None:
        record = self.session.get(ServiceAccountTokenRecord, token_id)
        if record is None or record.service_account_id != service_account_id:
            return None
        record.status = "revoked"
        record.revoked_at = datetime.now(timezone.utc)
        self.session.flush()
        self.session.refresh(record)
        return _to_token(record)

    def touch_token_usage(
        self,
        *,
        token_id: UUID,
        service_account_id: UUID,
        used_at: datetime,
    ) -> None:
        token = self.session.get(ServiceAccountTokenRecord, token_id)
        account = self.session.get(ServiceAccountRecord, service_account_id)
        if token is not None:
            token.last_used_at = used_at
        if account is not None:
            account.last_used_at = used_at
        self.session.flush()

    def list_project_grants(self, *, service_account_id: UUID) -> list[StoredServiceAccountProjectGrant]:
        stmt = select(ServiceAccountProjectGrantRecord).where(
            ServiceAccountProjectGrantRecord.service_account_id == service_account_id
        )
        return [_to_grant(row) for row in self.session.scalars(stmt).all()]

    def upsert_project_grant(
        self,
        *,
        service_account_id: UUID,
        project_id: UUID,
        role: ProjectRole,
        actor_id: str | None,
    ) -> StoredServiceAccountProjectGrant:
        stmt = select(ServiceAccountProjectGrantRecord).where(
            ServiceAccountProjectGrantRecord.service_account_id == service_account_id,
            ServiceAccountProjectGrantRecord.project_id == project_id,
        )
        record = self.session.scalar(stmt)
        if record is None:
            record = ServiceAccountProjectGrantRecord(
                service_account_id=service_account_id,
                project_id=project_id,
                role=role.to_db(),
                created_by=actor_id,
                updated_by=actor_id,
            )
            self.session.add(record)
        else:
            record.role = role.to_db()
            record.updated_by = actor_id
        self.session.flush()
        self.session.refresh(record)
        return _to_grant(record)

    def delete_project_grant(self, *, service_account_id: UUID, project_id: UUID) -> bool:
        stmt = select(ServiceAccountProjectGrantRecord).where(
            ServiceAccountProjectGrantRecord.service_account_id == service_account_id,
            ServiceAccountProjectGrantRecord.project_id == project_id,
        )
        record = self.session.scalar(stmt)
        if record is None:
            return False
        self.session.delete(record)
        self.session.flush()
        return True

    def get_project_grant_role(
        self,
        *,
        credential_id: str | None,
        project_id: UUID,
    ) -> ProjectRole | None:
        if not credential_id:
            return None
        try:
            token_id = UUID(credential_id)
        except ValueError:
            return None
        stmt = (
            select(ServiceAccountProjectGrantRecord.role)
            .join(
                ServiceAccountTokenRecord,
                ServiceAccountTokenRecord.service_account_id
                == ServiceAccountProjectGrantRecord.service_account_id,
            )
            .where(
                ServiceAccountTokenRecord.id == token_id,
                ServiceAccountProjectGrantRecord.project_id == project_id,
            )
        )
        role = self.session.scalar(stmt)
        return ProjectRole.from_db(role) if role else None

    def summarize(self) -> dict[str, int]:
        total_accounts = int(self.session.scalar(select(func.count()).select_from(ServiceAccountRecord)) or 0)
        active_accounts = int(
            self.session.scalar(
                select(func.count())
                .select_from(ServiceAccountRecord)
                .where(ServiceAccountRecord.status == "active")
            )
            or 0
        )
        active_tokens = int(
            self.session.scalar(
                select(func.count())
                .select_from(ServiceAccountTokenRecord)
                .where(ServiceAccountTokenRecord.status == "active")
            )
            or 0
        )
        revoked_tokens = int(
            self.session.scalar(
                select(func.count())
                .select_from(ServiceAccountTokenRecord)
                .where(ServiceAccountTokenRecord.status == "revoked")
            )
            or 0
        )
        return {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "active_tokens": active_tokens,
            "revoked_tokens": revoked_tokens,
        }
