from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.modules.identity.infra.sqlalchemy.models import (
    RefreshTokenRecord,
    UserRecord,
    has_super_admin_platform_role,
    normalize_user_platform_roles,
)
from app.modules.projects.infra.sqlalchemy.models import ProjectMemberRecord, ProjectRecord
from app.modules.users.application.ports import StoredPlatformUser, StoredUserProjectMembership


def _to_user(record: UserRecord) -> StoredPlatformUser:
    platform_roles = normalize_user_platform_roles(
        record.platform_roles_json,
        is_super_admin=record.is_super_admin,
    )
    return StoredPlatformUser(
        id=record.id,
        username=record.username,
        email=record.email,
        status=record.status,
        is_super_admin=has_super_admin_platform_role(platform_roles),
        platform_roles=platform_roles,
        created_at=record.created_at,
        updated_at=record.updated_at,
        must_change_password=record.must_change_password,
    )


class SqlAlchemyUsersRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_users(
        self,
        *,
        limit: int,
        offset: int,
        query: str | None,
        status: str | None,
        exclude_user_ids: tuple[UUID, ...],
    ) -> tuple[list[StoredPlatformUser], int]:
        base_stmt = select(UserRecord)
        if query and query.strip():
            normalized = f"%{query.strip().lower()}%"
            base_stmt = base_stmt.where(
                func.lower(UserRecord.username).like(normalized)
                | func.lower(func.coalesce(UserRecord.email, "")).like(normalized)
            )
        if status:
            base_stmt = base_stmt.where(UserRecord.status == status)
        if exclude_user_ids:
            base_stmt = base_stmt.where(UserRecord.id.not_in(exclude_user_ids))

        stmt = base_stmt.order_by(desc(UserRecord.created_at)).offset(offset).limit(limit)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        rows = list(self.session.scalars(stmt).all())
        total = int(self.session.scalar(count_stmt) or 0)
        return [_to_user(row) for row in rows], total

    def get_user_by_id(self, user_id: UUID) -> StoredPlatformUser | None:
        record = self.session.get(UserRecord, user_id)
        return _to_user(record) if record is not None else None

    def get_user_by_username(self, username: str) -> StoredPlatformUser | None:
        stmt = select(UserRecord).where(UserRecord.username == username)
        record = self.session.scalar(stmt)
        return _to_user(record) if record is not None else None

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        email: str | None,
        platform_roles: tuple[str, ...] = (),
        is_super_admin: bool,
        must_change_password: bool = False,
    ) -> StoredPlatformUser:
        normalized_roles = normalize_user_platform_roles(
            platform_roles,
            is_super_admin=is_super_admin,
        )
        record = UserRecord(
            username=username,
            external_subject=username,
            email=email,
            password_hash=password_hash,
            status="active",
            is_super_admin=has_super_admin_platform_role(normalized_roles),
            platform_roles_json=list(normalized_roles),
            must_change_password=must_change_password,
        )
        self.session.add(record)
        self.session.flush()
        return _to_user(record)

    def update_user(
        self,
        user_id: UUID,
        *,
        username: str,
        email: str | None,
        status: str,
        platform_roles: tuple[str, ...],
        is_super_admin: bool,
        password_hash: str | None,
        must_change_password: bool | None = None,
    ) -> StoredPlatformUser | None:
        record = self.session.get(UserRecord, user_id)
        if record is None:
            return None
        normalized_roles = normalize_user_platform_roles(
            platform_roles,
            is_super_admin=is_super_admin,
        )
        record.username = username
        record.external_subject = username
        record.email = email
        record.status = status
        record.is_super_admin = has_super_admin_platform_role(normalized_roles)
        record.platform_roles_json = list(normalized_roles)
        if password_hash:
            record.password_hash = password_hash
        if must_change_password is not None:
            record.must_change_password = must_change_password
        self.session.flush()
        return _to_user(record)

    def list_user_projects(self, *, user_id: UUID) -> list[StoredUserProjectMembership]:
        stmt = (
            select(ProjectMemberRecord, ProjectRecord)
            .join(ProjectRecord, ProjectRecord.id == ProjectMemberRecord.project_id)
            .where(ProjectMemberRecord.user_id == user_id)
            .order_by(ProjectMemberRecord.created_at.desc())
        )
        rows = list(self.session.execute(stmt).tuples().all())
        return [
            StoredUserProjectMembership(
                project_id=project.id,
                project_name=project.name,
                project_description=project.description,
                project_status=project.status,
                role=member.role,
                joined_at=member.created_at,
            )
            for member, project in rows
        ]

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

    def count_active_super_admins(self) -> int:
        stmt = select(UserRecord).where(UserRecord.status == "active")
        return sum(
            1
            for record in self.session.scalars(stmt).all()
            if has_super_admin_platform_role(
                record.platform_roles_json,
                is_super_admin=record.is_super_admin,
            )
        )
