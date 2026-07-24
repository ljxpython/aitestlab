from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.identity.application.ports import (
    StoredRefreshToken,
    StoredUser,
)
from app.modules.identity.infra.sqlalchemy.models import (
    RefreshTokenRecord,
    UserRecord,
    has_super_admin_platform_role,
    normalize_user_platform_roles,
)


def _to_user(record: UserRecord) -> StoredUser:
    platform_roles = normalize_user_platform_roles(
        record.platform_roles_json,
        is_super_admin=record.is_super_admin,
    )
    return StoredUser(
        id=record.id,
        username=record.username,
        external_subject=record.external_subject,
        email=record.email,
        status=record.status,
        password_hash=record.password_hash,
        is_super_admin=has_super_admin_platform_role(platform_roles),
        platform_roles=platform_roles,
        must_change_password=record.must_change_password,
        failed_login_attempts=record.failed_login_attempts,
        locked_until=record.locked_until,
    )


def _to_refresh_token(record: RefreshTokenRecord) -> StoredRefreshToken:
    return StoredRefreshToken(
        token_id=record.token_id,
        user_id=record.user_id,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
        family_id=record.family_id,
        consumed_at=record.consumed_at,
    )


class SqlAlchemyIdentityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user_by_username(self, username: str) -> StoredUser | None:
        stmt = select(UserRecord).where(UserRecord.username == username)
        record = self.session.scalar(stmt)
        return _to_user(record) if record is not None else None

    def get_user_by_id(self, user_id: UUID) -> StoredUser | None:
        record = self.session.get(UserRecord, user_id)
        return _to_user(record) if record is not None else None

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        external_subject: str,
        email: str | None,
        platform_roles: tuple[str, ...] = (),
        is_super_admin: bool,
        must_change_password: bool = False,
    ) -> StoredUser:
        normalized_roles = normalize_user_platform_roles(
            platform_roles,
            is_super_admin=is_super_admin,
        )
        record = UserRecord(
            username=username,
            password_hash=password_hash,
            external_subject=external_subject,
            email=email,
            status="active",
            is_super_admin=has_super_admin_platform_role(normalized_roles),
            platform_roles_json=list(normalized_roles),
            must_change_password=must_change_password,
        )
        self.session.add(record)
        self.session.flush()
        return _to_user(record)

    def count_super_admins(self) -> int:
        stmt = select(UserRecord).where(UserRecord.status == "active")
        return sum(
            1
            for record in self.session.scalars(stmt).all()
            if has_super_admin_platform_role(
                record.platform_roles_json,
                is_super_admin=record.is_super_admin,
            )
        )

    def get_refresh_token(self, token_id: str) -> StoredRefreshToken | None:
        stmt = select(RefreshTokenRecord).where(RefreshTokenRecord.token_id == token_id)
        record = self.session.scalar(stmt)
        return _to_refresh_token(record) if record is not None else None

    def create_refresh_token(
        self,
        *,
        user_id: UUID,
        token_id: str,
        family_id: str,
        expires_at: datetime,
    ) -> StoredRefreshToken:
        record = RefreshTokenRecord(
            user_id=user_id,
            token_id=token_id,
            family_id=family_id,
            expires_at=expires_at,
        )
        self.session.add(record)
        self.session.flush()
        return _to_refresh_token(record)

    def consume_refresh_token(self, token_id: str) -> tuple[StoredRefreshToken | None, str | None]:
        now = datetime.now(timezone.utc)
        result = self.session.execute(
            update(RefreshTokenRecord)
            .where(
                RefreshTokenRecord.token_id == token_id,
                RefreshTokenRecord.revoked_at.is_(None),
                RefreshTokenRecord.consumed_at.is_(None),
                RefreshTokenRecord.expires_at > now,
            )
            .values(consumed_at=now, revoked_at=now)
        )
        if result.rowcount == 1:
            self.session.flush()
            return self.get_refresh_token(token_id), "consumed"
        token = self.get_refresh_token(token_id)
        if token is None:
            return None, "missing"
        if token.consumed_at is not None:
            return token, "replayed"
        if token.revoked_at is not None:
            return token, "revoked"
        return token, "expired"

    def revoke_refresh_token(self, token_id: str) -> None:
        stmt = select(RefreshTokenRecord).where(RefreshTokenRecord.token_id == token_id)
        record = self.session.scalar(stmt)
        if record is None:
            return
        if record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            self.session.flush()

    def revoke_refresh_token_family(self, family_id: str) -> int:
        now = datetime.now(timezone.utc)
        result = self.session.execute(
            update(RefreshTokenRecord)
            .where(
                RefreshTokenRecord.family_id == family_id,
                RefreshTokenRecord.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        return int(result.rowcount or 0)

    def revoke_all_refresh_tokens_for_user(self, user_id: UUID) -> int:
        stmt = select(RefreshTokenRecord).where(
            RefreshTokenRecord.user_id == user_id,
            RefreshTokenRecord.revoked_at.is_(None),
        )
        now = datetime.now(timezone.utc)
        changed = 0
        for record in self.session.scalars(stmt).all():
            record.revoked_at = now
            changed += 1
        if changed:
            self.session.flush()
        return changed

    def update_user_password_hash(
        self,
        user_id: UUID,
        password_hash: str,
        *,
        must_change_password: bool,
    ) -> None:
        record = self.session.get(UserRecord, user_id)
        if record is None:
            return
        record.password_hash = password_hash
        record.must_change_password = must_change_password
        self.session.flush()

    def record_login_failure(self, user_id: UUID, *, locked_until: datetime | None) -> None:
        record = self.session.get(UserRecord, user_id)
        if record is None:
            return
        record.failed_login_attempts += 1
        record.locked_until = locked_until
        self.session.flush()

    def clear_login_failures(self, user_id: UUID) -> None:
        record = self.session.get(UserRecord, user_id)
        if record is None:
            return
        record.failed_login_attempts = 0
        record.locked_until = None
        self.session.flush()

    def update_user_profile(
        self,
        user_id: UUID,
        *,
        username: str,
        email: str | None,
    ) -> StoredUser | None:
        record = self.session.get(UserRecord, user_id)
        if record is None:
            return None
        record.username = username
        record.email = email
        self.session.flush()
        return _to_user(record)

    def reconcile_bootstrap_admin(
        self,
        *,
        username: str,
        password_hash: str,
    ) -> str | None:
        stmt = select(UserRecord).where(UserRecord.username == username)
        record = self.session.scalar(stmt)
        if record is None:
            if self.count_super_admins() > 0:
                return None
            self.create_user(
                username=username,
                password_hash=password_hash,
                external_subject=username,
                email=None,
                platform_roles=("platform_super_admin",),
                is_super_admin=True,
            )
            return "created"

        changed = False
        if record.status != "active":
            record.status = "active"
            changed = True
        normalized_roles = normalize_user_platform_roles(
            record.platform_roles_json,
            is_super_admin=record.is_super_admin,
        )
        if "platform_super_admin" not in normalized_roles:
            normalized_roles = normalize_user_platform_roles(
                (*normalized_roles, "platform_super_admin"),
            )
            record.platform_roles_json = list(normalized_roles)
            changed = True
        if not record.is_super_admin:
            record.is_super_admin = True
            changed = True
        if not record.password_hash:
            record.password_hash = password_hash
            changed = True
        if changed:
            self.session.flush()
            return "reconciled"
        return None
