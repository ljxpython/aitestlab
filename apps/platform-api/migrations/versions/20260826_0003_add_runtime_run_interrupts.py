"""Persist the internal interrupt-to-run index.

Revision ID: 20260826_0003
Revises: 20260826_0002
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260826_0003"
down_revision = "20260826_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "runtime_run_interrupts" in inspector.get_table_names():
        return

    op.create_table(
        "runtime_run_interrupts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("interrupt_id", sa.String(length=128), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "thread_id",
            "run_id",
            "interrupt_id",
            name="uq_runtime_run_interrupt_identity",
        ),
    )
    op.create_index("ix_runtime_run_interrupts_project_id", "runtime_run_interrupts", ["project_id"])
    op.create_index("ix_runtime_run_interrupts_thread_id", "runtime_run_interrupts", ["thread_id"])
    op.create_index("ix_runtime_run_interrupts_run_id", "runtime_run_interrupts", ["run_id"])
    op.create_index("ix_runtime_run_interrupts_interrupt_id", "runtime_run_interrupts", ["interrupt_id"])
    op.create_index("ix_runtime_run_interrupts_created_at", "runtime_run_interrupts", ["created_at"])


def downgrade() -> None:
    # Interrupt records are audit/recovery evidence; removal requires a separately approved retention change.
    pass
