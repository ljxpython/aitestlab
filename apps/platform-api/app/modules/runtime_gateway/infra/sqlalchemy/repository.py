from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.runtime_gateway.infra.sqlalchemy.models import (
    DurableRunInterruptRecord,
    DurableRunRecord,
)


@dataclass(frozen=True, slots=True)
class StoredDurableRun:
    id: str
    project_id: str
    thread_id: str
    idempotency_key: str
    request_digest: str
    run_id: str | None
    operation_id: str
    status: str
    active: bool
    created_at: datetime
    updated_at: datetime


def _to_stored(record: DurableRunRecord) -> StoredDurableRun:
    return StoredDurableRun(
        id=str(record.id),
        project_id=record.project_id,
        thread_id=record.thread_id,
        idempotency_key=record.idempotency_key,
        request_digest=record.request_digest,
        run_id=record.run_id,
        operation_id=str(record.operation_id),
        status=record.status,
        active=record.active_key is not None,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SqlAlchemyDurableRunsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_idempotency_key(
        self, *, project_id: str, thread_id: str, idempotency_key: str
    ) -> StoredDurableRun | None:
        record = self.session.scalar(
            select(DurableRunRecord).where(
                DurableRunRecord.project_id == project_id,
                DurableRunRecord.thread_id == thread_id,
                DurableRunRecord.idempotency_key == idempotency_key,
            )
        )
        return _to_stored(record) if record is not None else None

    def get_active(self, *, project_id: str, thread_id: str) -> StoredDurableRun | None:
        record = self.session.scalar(
            select(DurableRunRecord).where(
                DurableRunRecord.project_id == project_id,
                DurableRunRecord.thread_id == thread_id,
                DurableRunRecord.active_key.is_not(None),
            )
        )
        return _to_stored(record) if record is not None else None

    def get_by_run_id(
        self, *, project_id: str, thread_id: str, run_id: str
    ) -> StoredDurableRun | None:
        record = self.session.scalar(
            select(DurableRunRecord).where(
                DurableRunRecord.project_id == project_id,
                DurableRunRecord.thread_id == thread_id,
                DurableRunRecord.run_id == run_id,
            )
        )
        return _to_stored(record) if record is not None else None

    def create(
        self,
        *,
        project_id: str,
        thread_id: str,
        idempotency_key: str,
        request_digest: str,
        operation_id: str,
    ) -> StoredDurableRun:
        from uuid import UUID

        record = DurableRunRecord(
            project_id=project_id,
            thread_id=thread_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            operation_id=UUID(operation_id),
            status="submitted",
            active_key="1",
        )
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return _to_stored(record)

    def mark_started(self, *, durable_run_id: str, run_id: str) -> StoredDurableRun | None:
        from uuid import UUID

        record = self.session.get(DurableRunRecord, UUID(durable_run_id))
        if record is None:
            return None
        record.run_id = run_id
        record.status = "running"
        self.session.flush()
        self.session.refresh(record)
        return _to_stored(record)

    def mark_terminal(self, *, durable_run_id: str, status: str) -> StoredDurableRun | None:
        from uuid import UUID

        record = self.session.get(DurableRunRecord, UUID(durable_run_id))
        if record is None:
            return None
        record.status = status
        record.active_key = None
        self.session.flush()
        self.session.refresh(record)
        return _to_stored(record)

    def sync_active_interrupts(
        self,
        *,
        project_id: str,
        thread_id: str,
        run_id: str,
        interrupt_ids: set[str],
    ) -> None:
        for interrupt_id in sorted(interrupt_ids):
            record = self.session.scalar(
                select(DurableRunInterruptRecord).where(
                    DurableRunInterruptRecord.project_id == project_id,
                    DurableRunInterruptRecord.thread_id == thread_id,
                    DurableRunInterruptRecord.run_id == run_id,
                    DurableRunInterruptRecord.interrupt_id == interrupt_id,
                )
            )
            if record is None:
                self.session.add(
                    DurableRunInterruptRecord(
                        project_id=project_id,
                        thread_id=thread_id,
                        run_id=run_id,
                        interrupt_id=interrupt_id,
                    )
                )
        self.session.flush()

    def is_interrupt_active(
        self,
        *,
        project_id: str,
        thread_id: str,
        run_id: str,
        interrupt_id: str,
    ) -> bool:
        record = self.session.scalar(
            select(DurableRunInterruptRecord).where(
                DurableRunInterruptRecord.project_id == project_id,
                DurableRunInterruptRecord.thread_id == thread_id,
                DurableRunInterruptRecord.run_id == run_id,
                DurableRunInterruptRecord.interrupt_id == interrupt_id,
                DurableRunInterruptRecord.resolved_at.is_(None),
            )
        )
        return record is not None

    def mark_interrupt_resolved(
        self,
        *,
        project_id: str,
        thread_id: str,
        run_id: str,
        interrupt_id: str,
    ) -> bool:
        record = self.session.scalar(
            select(DurableRunInterruptRecord).where(
                DurableRunInterruptRecord.project_id == project_id,
                DurableRunInterruptRecord.thread_id == thread_id,
                DurableRunInterruptRecord.run_id == run_id,
                DurableRunInterruptRecord.interrupt_id == interrupt_id,
                DurableRunInterruptRecord.resolved_at.is_(None),
            )
        )
        if record is None:
            return False
        record.resolved_at = datetime.now(timezone.utc)
        self.session.flush()
        return True

    def mark_run_interrupts_resolved(self, *, run_id: str) -> None:
        records = self.session.scalars(
            select(DurableRunInterruptRecord).where(
                DurableRunInterruptRecord.run_id == run_id,
                DurableRunInterruptRecord.resolved_at.is_(None),
            )
        ).all()
        resolved_at = datetime.now(timezone.utc)
        for record in records:
            record.resolved_at = resolved_at
        self.session.flush()
