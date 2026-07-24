from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.modules.iam.domain import ProjectRole
from app.modules.identity.infra.sqlalchemy.models import UserRecord
from app.modules.projects.application.ports import (
    StoredProject,
    StoredProjectMemberView,
    StoredProjectMemberCandidate,
    StoredTenant,
)
from app.modules.projects.infra.sqlalchemy.models import (
    ProjectMemberRecord,
    ProjectRecord,
    TenantRecord,
)


def _to_project(record: ProjectRecord) -> StoredProject:
    return StoredProject(
        id=record.id,
        tenant_id=record.tenant_id,
        name=record.name,
        description=record.description,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_tenant(record: TenantRecord) -> StoredTenant:
    return StoredTenant(
        id=record.id,
        slug=record.slug,
        name=record.name,
        status=record.status,
    )


class SqlAlchemyProjectsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_default_tenant(self) -> StoredTenant:
        stmt = select(TenantRecord).where(TenantRecord.slug == "__default")
        record = self.session.scalar(stmt)
        if record is None:
            record = TenantRecord(name="Default", slug="__default", status="active")
            self.session.add(record)
            self.session.flush()
        return _to_tenant(record)

    def list_projects(
        self,
        *,
        limit: int,
        offset: int,
        query: str | None,
    ) -> tuple[list[StoredProject], int]:
        base_stmt = select(ProjectRecord).where(ProjectRecord.status != "deleted")
        if query and query.strip():
            normalized = f"%{query.strip().lower()}%"
            base_stmt = base_stmt.where(
                func.lower(ProjectRecord.name).like(normalized)
                | func.lower(ProjectRecord.description).like(normalized)
            )
        stmt = base_stmt.order_by(desc(ProjectRecord.created_at)).offset(offset).limit(limit)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        rows = list(self.session.scalars(stmt).all())
        total = int(self.session.scalar(count_stmt) or 0)
        return [_to_project(row) for row in rows], total

    def list_projects_for_user(
        self,
        *,
        user_id: UUID,
        limit: int,
        offset: int,
        query: str | None,
    ) -> tuple[list[StoredProject], int]:
        base_stmt = (
            select(ProjectRecord)
            .join(ProjectMemberRecord, ProjectMemberRecord.project_id == ProjectRecord.id)
            .where(
                ProjectMemberRecord.user_id == user_id,
                ProjectRecord.status != "deleted",
            )
        )
        if query and query.strip():
            normalized = f"%{query.strip().lower()}%"
            base_stmt = base_stmt.where(
                func.lower(ProjectRecord.name).like(normalized)
                | func.lower(ProjectRecord.description).like(normalized)
            )
        stmt = base_stmt.order_by(desc(ProjectRecord.created_at)).offset(offset).limit(limit)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        rows = list(self.session.scalars(stmt).all())
        total = int(self.session.scalar(count_stmt) or 0)
        return [_to_project(row) for row in rows], total

    def create_project(
        self,
        *,
        tenant_id: UUID,
        name: str,
        description: str,
    ) -> StoredProject:
        record = ProjectRecord(
            tenant_id=tenant_id,
            name=name,
            description=description,
            code=None,
            status="active",
        )
        self.session.add(record)
        self.session.flush()
        return _to_project(record)

    def get_project_by_id(
        self,
        project_id: UUID,
        *,
        include_inactive: bool = False,
    ) -> StoredProject | None:
        record = self.session.get(ProjectRecord, project_id)
        if record is None or (not include_inactive and record.status != "active"):
            return None
        return _to_project(record)

    def set_project_status(self, project_id: UUID, status: str) -> StoredProject | None:
        record = self.session.get(ProjectRecord, project_id)
        if record is None:
            return None
        record.status = status
        record.deleted_at = None
        self.session.flush()
        return _to_project(record)

    def soft_delete_project(self, project_id: UUID) -> None:
        record = self.session.get(ProjectRecord, project_id)
        if record is None:
            return
        record.status = "deleting"
        self.session.flush()
        record.status = "deleted"
        record.deleted_at = datetime.now(timezone.utc)
        self.session.flush()

    def list_project_members(
        self,
        *,
        project_id: UUID,
        query: str | None,
    ) -> list[StoredProjectMemberView]:
        stmt = (
            select(ProjectMemberRecord, UserRecord)
            .join(UserRecord, UserRecord.id == ProjectMemberRecord.user_id)
            .where(ProjectMemberRecord.project_id == project_id)
            .order_by(ProjectMemberRecord.created_at.asc())
        )
        rows = list(self.session.execute(stmt).tuples().all())
        normalized = query.strip().lower() if query and query.strip() else None
        result: list[StoredProjectMemberView] = []
        for member, user in rows:
            if normalized and normalized not in user.username.lower():
                continue
            result.append(
                StoredProjectMemberView(
                    project_id=member.project_id,
                    user_id=member.user_id,
                    username=user.username,
                    role=ProjectRole.from_db(member.role),
                )
            )
        return result

    def get_project_member_role(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
    ) -> ProjectRole | None:
        stmt = select(ProjectMemberRecord.role).where(
            ProjectMemberRecord.project_id == project_id,
            ProjectMemberRecord.user_id == user_id,
        )
        role = self.session.scalar(stmt)
        if role is None:
            return None
        return ProjectRole.from_db(role)

    def list_user_project_roles(self, *, user_id: UUID) -> dict[str, tuple[str, ...]]:
        stmt = select(ProjectMemberRecord.project_id, ProjectMemberRecord.role).where(
            ProjectMemberRecord.user_id == user_id
        )
        result: dict[str, list[str]] = {}
        for project_id, role in self.session.execute(stmt).all():
            project_key = str(project_id)
            result.setdefault(project_key, []).append(ProjectRole.from_db(role).value)
        return {key: tuple(sorted(set(values))) for key, values in result.items()}

    def upsert_project_member(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
    ) -> StoredProjectMemberView:
        stmt = select(ProjectMemberRecord).where(
            ProjectMemberRecord.project_id == project_id,
            ProjectMemberRecord.user_id == user_id,
        )
        member = self.session.scalar(stmt)
        if member is None:
            member = ProjectMemberRecord(
                project_id=project_id,
                user_id=user_id,
                role=role.to_db(),
            )
            self.session.add(member)
            self.session.flush()
        else:
            member.role = role.to_db()
            self.session.flush()

        user = self.session.get(UserRecord, user_id)
        username = user.username if user is not None else "unknown"
        return StoredProjectMemberView(
            project_id=project_id,
            user_id=user_id,
            username=username,
            role=role,
        )

    def remove_project_member(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
    ) -> None:
        stmt = select(ProjectMemberRecord).where(
            ProjectMemberRecord.project_id == project_id,
            ProjectMemberRecord.user_id == user_id,
        )
        member = self.session.scalar(stmt)
        if member is None:
            return
        self.session.delete(member)
        self.session.flush()

    def count_project_admins(self, *, project_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ProjectMemberRecord)
            .where(
                ProjectMemberRecord.project_id == project_id,
                ProjectMemberRecord.role == "admin",
            )
        )
        return int(self.session.scalar(stmt) or 0)

    def list_member_candidates(
        self,
        *,
        project_id: UUID,
        limit: int,
        offset: int,
        query: str | None,
    ) -> tuple[list[StoredProjectMemberCandidate], int]:
        member_ids = select(ProjectMemberRecord.user_id).where(
            ProjectMemberRecord.project_id == project_id
        )
        base_stmt = select(UserRecord).where(
            UserRecord.status == "active",
            UserRecord.id.not_in(member_ids),
        )
        if query and query.strip():
            normalized = f"%{query.strip().lower()}%"
            base_stmt = base_stmt.where(
                func.lower(UserRecord.username).like(normalized)
                | func.lower(func.coalesce(UserRecord.email, "")).like(normalized)
            )
        rows = list(
            self.session.scalars(
                base_stmt.order_by(UserRecord.username.asc()).offset(offset).limit(limit)
            ).all()
        )
        total = int(self.session.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0)
        return [
            StoredProjectMemberCandidate(user_id=row.id, username=row.username, email=row.email)
            for row in rows
        ], total

    def user_exists(self, *, user_id: UUID) -> bool:
        stmt = (
            select(UserRecord.id)
            .where(UserRecord.id == user_id, UserRecord.status == "active")
            .limit(1)
        )
        return self.session.scalar(stmt) is not None
