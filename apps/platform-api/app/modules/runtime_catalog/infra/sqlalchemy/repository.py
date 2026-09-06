from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.modules.runtime_catalog.application.ports import (
    StoredRuntimeGraph,
    StoredRuntimeModel,
    StoredRuntimeTool,
)
from app.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogGraphRecord,
    RuntimeCatalogModelRecord,
    RuntimeCatalogToolRecord,
)


def _to_runtime_model(record: RuntimeCatalogModelRecord) -> StoredRuntimeModel:
    return StoredRuntimeModel(
        id=record.id,
        runtime_id=record.runtime_id,
        model_key=record.model_key,
        display_name=record.display_name,
        is_default_runtime=record.is_default_runtime,
        sync_status=record.sync_status,
        last_seen_at=record.last_seen_at,
        last_synced_at=record.last_synced_at,
        provider=record.provider,
        base_url=record.base_url,
        protocol=record.protocol,
        model_name=record.model_name or record.model_key,
        api_key_ciphertext=record.api_key_ciphertext,
        enabled=record.enabled if record.enabled is not None else True,
    )


def _to_runtime_tool(record: RuntimeCatalogToolRecord) -> StoredRuntimeTool:
    return StoredRuntimeTool(
        id=record.id,
        runtime_id=record.runtime_id,
        tool_key=record.tool_key,
        name=record.name,
        source=record.source,
        description=record.description,
        sync_status=record.sync_status,
        last_seen_at=record.last_seen_at,
        last_synced_at=record.last_synced_at,
    )


def _to_runtime_graph(record: RuntimeCatalogGraphRecord) -> StoredRuntimeGraph:
    return StoredRuntimeGraph(
        id=record.id,
        runtime_id=record.runtime_id,
        graph_key=record.graph_key,
        display_name=record.display_name,
        description=record.description,
        source_type=record.source_type,
        sync_status=record.sync_status,
        last_seen_at=record.last_seen_at,
        last_synced_at=record.last_synced_at,
    )


class SqlAlchemyRuntimeCatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_model_by_id(self, model_id) -> StoredRuntimeModel | None:
        record = self.session.get(RuntimeCatalogModelRecord, model_id)
        return _to_runtime_model(record) if record is not None else None

    def get_model_by_key(self, *, runtime_id: str, model_key: str) -> StoredRuntimeModel | None:
        record = self.session.scalar(
            select(RuntimeCatalogModelRecord).where(
                RuntimeCatalogModelRecord.runtime_id == runtime_id,
                RuntimeCatalogModelRecord.model_key == model_key,
                RuntimeCatalogModelRecord.is_deleted.is_(False),
            )
        )
        return _to_runtime_model(record) if record is not None else None

    def create_configured_model(self, *, runtime_id: str, values: dict[str, Any]) -> StoredRuntimeModel:
        record = self.session.scalar(
            select(RuntimeCatalogModelRecord).where(
                RuntimeCatalogModelRecord.runtime_id == runtime_id,
                RuntimeCatalogModelRecord.model_key == values["model"],
            )
        )
        if record is None:
            record = RuntimeCatalogModelRecord(runtime_id=runtime_id, model_key=values["model"])
            self.session.add(record)
        record.display_name = values["display_name"]
        record.provider = values["provider"]
        record.base_url = values["base_url"]
        record.protocol = values["protocol"]
        record.model_name = values["model"]
        record.api_key_ciphertext = values["api_key_ciphertext"]
        record.enabled = values["enabled"]
        record.is_deleted = False
        record.sync_status = "ready"
        self.session.flush()
        return _to_runtime_model(record)

    def update_configured_model(self, model_id, *, values: dict[str, Any]) -> StoredRuntimeModel | None:
        record = self.session.get(RuntimeCatalogModelRecord, model_id)
        if record is None or record.is_deleted:
            return None
        for key, value in values.items():
            setattr(record, key, value)
        self.session.flush()
        return _to_runtime_model(record)

    def get_tool_by_id(self, tool_id) -> StoredRuntimeTool | None:
        record = self.session.get(RuntimeCatalogToolRecord, tool_id)
        return _to_runtime_tool(record) if record is not None else None

    def get_graph_by_id(self, graph_id) -> StoredRuntimeGraph | None:
        record = self.session.get(RuntimeCatalogGraphRecord, graph_id)
        return _to_runtime_graph(record) if record is not None else None

    def list_models(self, *, runtime_id: str) -> list[StoredRuntimeModel]:
        stmt = (
            select(RuntimeCatalogModelRecord)
            .where(
                RuntimeCatalogModelRecord.runtime_id == runtime_id,
                RuntimeCatalogModelRecord.is_deleted.is_(False),
            )
            .order_by(
                desc(RuntimeCatalogModelRecord.is_default_runtime),
                asc(RuntimeCatalogModelRecord.model_key),
            )
        )
        return [_to_runtime_model(item) for item in self.session.scalars(stmt).all()]

    def list_tools(self, *, runtime_id: str) -> list[StoredRuntimeTool]:
        stmt = (
            select(RuntimeCatalogToolRecord)
            .where(
                RuntimeCatalogToolRecord.runtime_id == runtime_id,
                RuntimeCatalogToolRecord.is_deleted.is_(False),
            )
            .order_by(
                asc(RuntimeCatalogToolRecord.source),
                asc(RuntimeCatalogToolRecord.name),
            )
        )
        return [_to_runtime_tool(item) for item in self.session.scalars(stmt).all()]

    def list_graphs(self, *, runtime_id: str) -> list[StoredRuntimeGraph]:
        stmt = (
            select(RuntimeCatalogGraphRecord)
            .where(
                RuntimeCatalogGraphRecord.runtime_id == runtime_id,
                RuntimeCatalogGraphRecord.is_deleted.is_(False),
            )
            .order_by(asc(RuntimeCatalogGraphRecord.graph_key))
        )
        return [_to_runtime_graph(item) for item in self.session.scalars(stmt).all()]

    def upsert_model_items(
        self,
        *,
        runtime_id: str,
        items: list[dict[str, Any]],
        synced_at: datetime,
    ) -> None:
        for item in items:
            model_key = str(item.get("model_id") or "").strip()
            if not model_key:
                continue

            stmt = select(RuntimeCatalogModelRecord).where(
                RuntimeCatalogModelRecord.runtime_id == runtime_id,
                RuntimeCatalogModelRecord.model_key == model_key,
            )
            record = self.session.scalar(stmt)
            if record is None:
                record = RuntimeCatalogModelRecord(runtime_id=runtime_id, model_key=model_key)
                self.session.add(record)

            record.display_name = str(item.get("display_name") or model_key)
            record.is_default_runtime = bool(item.get("is_default"))
            record.raw_payload_json = dict(item)
            record.sync_status = "ready"
            record.last_seen_at = synced_at
            record.last_synced_at = synced_at
            record.is_deleted = False

        self.session.flush()

    def upsert_tool_items(
        self,
        *,
        runtime_id: str,
        items: list[dict[str, Any]],
        synced_at: datetime,
    ) -> None:
        for item in items:
            name = str(item.get("name") or "").strip()
            source = str(item.get("source") or "").strip()
            if not name:
                continue

            explicit_key = str(item.get("tool_key") or "").strip()
            tool_key = explicit_key or (f"{source}:{name}" if source else name)
            stmt = select(RuntimeCatalogToolRecord).where(
                RuntimeCatalogToolRecord.runtime_id == runtime_id,
                RuntimeCatalogToolRecord.tool_key == tool_key,
            )
            record = self.session.scalar(stmt)
            if record is None:
                record = RuntimeCatalogToolRecord(
                    runtime_id=runtime_id,
                    tool_key=tool_key,
                    name=name,
                )
                self.session.add(record)

            record.name = name
            record.source = source or None
            record.description = str(item.get("description") or "") or None
            record.raw_payload_json = dict(item)
            record.sync_status = "ready"
            record.last_seen_at = synced_at
            record.last_synced_at = synced_at
            record.is_deleted = False

        self.session.flush()

    def upsert_graph_items(
        self,
        *,
        runtime_id: str,
        items: list[dict[str, Any]],
        synced_at: datetime,
        source_type: str,
    ) -> None:
        for item in items:
            graph_key = str(item.get("graph_id") or item.get("graph_key") or "").strip()
            if not graph_key:
                continue

            stmt = select(RuntimeCatalogGraphRecord).where(
                RuntimeCatalogGraphRecord.runtime_id == runtime_id,
                RuntimeCatalogGraphRecord.graph_key == graph_key,
            )
            record = self.session.scalar(stmt)
            if record is None:
                record = RuntimeCatalogGraphRecord(
                    runtime_id=runtime_id,
                    graph_key=graph_key,
                )
                self.session.add(record)

            record.display_name = str(item.get("display_name") or graph_key) or graph_key
            record.description = str(item.get("description") or "") or None
            record.source_type = source_type
            record.raw_payload_json = dict(item)
            record.sync_status = "ready"
            record.last_seen_at = synced_at
            record.last_synced_at = synced_at
            record.is_deleted = False

        self.session.flush()

    def mark_missing_models_deleted(
        self,
        *,
        runtime_id: str,
        active_keys: set[str],
        synced_at: datetime,
    ) -> None:
        stmt = select(RuntimeCatalogModelRecord).where(RuntimeCatalogModelRecord.runtime_id == runtime_id)
        for record in self.session.scalars(stmt).all():
            if record.model_key not in active_keys:
                record.is_deleted = True
                record.last_synced_at = synced_at
        self.session.flush()

    def mark_missing_tools_deleted(
        self,
        *,
        runtime_id: str,
        active_keys: set[str],
        synced_at: datetime,
    ) -> None:
        stmt = select(RuntimeCatalogToolRecord).where(RuntimeCatalogToolRecord.runtime_id == runtime_id)
        for record in self.session.scalars(stmt).all():
            if record.tool_key not in active_keys:
                record.is_deleted = True
                record.last_synced_at = synced_at
        self.session.flush()

    def mark_missing_graphs_deleted(
        self,
        *,
        runtime_id: str,
        active_keys: set[str],
        synced_at: datetime,
    ) -> None:
        stmt = select(RuntimeCatalogGraphRecord).where(RuntimeCatalogGraphRecord.runtime_id == runtime_id)
        for record in self.session.scalars(stmt).all():
            if record.graph_key not in active_keys:
                record.is_deleted = True
                record.last_synced_at = synced_at
        self.session.flush()
