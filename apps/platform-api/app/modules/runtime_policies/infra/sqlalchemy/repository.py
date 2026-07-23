from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.modules.runtime_catalog.infra.sqlalchemy.models import RuntimeCatalogModelRecord
from app.modules.runtime_policies.infra.sqlalchemy.models import (
    ProjectGraphPolicyRecord,
    ProjectModelPolicyRecord,
    ProjectToolPolicyRecord,
)


class SqlAlchemyRuntimePolicyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_graph_policies(self, *, project_id: UUID) -> list[ProjectGraphPolicyRecord]:
        stmt = (
            select(ProjectGraphPolicyRecord)
            .where(ProjectGraphPolicyRecord.project_id == project_id)
            .order_by(asc(ProjectGraphPolicyRecord.display_order), asc(ProjectGraphPolicyRecord.updated_at))
        )
        return list(self.session.scalars(stmt).all())

    def upsert_graph_policy(
        self,
        *,
        project_id: UUID,
        graph_catalog_id: UUID,
        is_enabled: bool,
        display_order: int | None,
        note: str | None,
        updated_by: str | None,
    ) -> ProjectGraphPolicyRecord:
        stmt = select(ProjectGraphPolicyRecord).where(
            ProjectGraphPolicyRecord.project_id == project_id,
            ProjectGraphPolicyRecord.graph_catalog_id == graph_catalog_id,
        )
        row = self.session.scalar(stmt)
        if row is None:
            row = ProjectGraphPolicyRecord(project_id=project_id, graph_catalog_id=graph_catalog_id)
            self.session.add(row)
        row.is_enabled = is_enabled
        row.display_order = display_order
        row.note = note
        row.updated_by = updated_by
        self.session.flush()
        return row

    def list_tool_policies(self, *, project_id: UUID) -> list[ProjectToolPolicyRecord]:
        stmt = (
            select(ProjectToolPolicyRecord)
            .where(ProjectToolPolicyRecord.project_id == project_id)
            .order_by(asc(ProjectToolPolicyRecord.display_order), asc(ProjectToolPolicyRecord.updated_at))
        )
        return list(self.session.scalars(stmt).all())

    def upsert_tool_policy(
        self,
        *,
        project_id: UUID,
        tool_catalog_id: UUID,
        is_enabled: bool,
        display_order: int | None,
        note: str | None,
        updated_by: str | None,
    ) -> ProjectToolPolicyRecord:
        stmt = select(ProjectToolPolicyRecord).where(
            ProjectToolPolicyRecord.project_id == project_id,
            ProjectToolPolicyRecord.tool_catalog_id == tool_catalog_id,
        )
        row = self.session.scalar(stmt)
        if row is None:
            row = ProjectToolPolicyRecord(project_id=project_id, tool_catalog_id=tool_catalog_id)
            self.session.add(row)
        row.is_enabled = is_enabled
        row.display_order = display_order
        row.note = note
        row.updated_by = updated_by
        self.session.flush()
        return row

    def list_model_policies(self, *, project_id: UUID) -> list[ProjectModelPolicyRecord]:
        stmt = (
            select(ProjectModelPolicyRecord)
            .where(ProjectModelPolicyRecord.project_id == project_id)
            .order_by(desc(ProjectModelPolicyRecord.is_default_for_project), asc(ProjectModelPolicyRecord.updated_at))
        )
        return list(self.session.scalars(stmt).all())

    def get_default_model_key(self, *, project_id: UUID, runtime_id: str) -> str | None:
        stmt = (
            select(RuntimeCatalogModelRecord.model_key)
            .join(
                ProjectModelPolicyRecord,
                ProjectModelPolicyRecord.model_catalog_id == RuntimeCatalogModelRecord.id,
            )
            .where(
                ProjectModelPolicyRecord.project_id == project_id,
                ProjectModelPolicyRecord.is_enabled.is_(True),
                ProjectModelPolicyRecord.is_default_for_project.is_(True),
                RuntimeCatalogModelRecord.runtime_id == runtime_id,
                RuntimeCatalogModelRecord.is_deleted.is_(False),
            )
            .order_by(
                desc(RuntimeCatalogModelRecord.is_default_runtime),
                asc(RuntimeCatalogModelRecord.model_key),
            )
        )
        return self.session.scalar(stmt)

    def upsert_model_policy(
        self,
        *,
        project_id: UUID,
        model_catalog_id: UUID,
        is_enabled: bool,
        is_default_for_project: bool,
        temperature_default: Decimal | None,
        note: str | None,
        updated_by: str | None,
    ) -> ProjectModelPolicyRecord:
        stmt = select(ProjectModelPolicyRecord).where(
            ProjectModelPolicyRecord.project_id == project_id,
            ProjectModelPolicyRecord.model_catalog_id == model_catalog_id,
        )
        row = self.session.scalar(stmt)
        if row is None:
            row = ProjectModelPolicyRecord(project_id=project_id, model_catalog_id=model_catalog_id)
            self.session.add(row)
        row.is_enabled = is_enabled
        row.is_default_for_project = is_default_for_project
        row.temperature_default = temperature_default
        row.note = note
        row.updated_by = updated_by
        self.session.flush()
        return row
