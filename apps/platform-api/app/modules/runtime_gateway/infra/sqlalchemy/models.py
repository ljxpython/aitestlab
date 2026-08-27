from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base


class DurableRunRecord(Base):
    __tablename__ = "runtime_runs"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "thread_id",
            "idempotency_key",
            name="uq_runtime_runs_project_thread_idempotency",
        ),
        UniqueConstraint(
            "project_id",
            "thread_id",
            "active_key",
            name="uq_runtime_runs_project_thread_active",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    operation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted", index=True)
    active_key: Mapped[str | None] = mapped_column(String(1), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DurableRunInterruptRecord(Base):
    """Internal interrupt-to-run index; payloads stay in LangGraph checkpoints."""

    __tablename__ = "runtime_run_interrupts"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "thread_id",
            "run_id",
            "interrupt_id",
            name="uq_runtime_run_interrupt_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    interrupt_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
