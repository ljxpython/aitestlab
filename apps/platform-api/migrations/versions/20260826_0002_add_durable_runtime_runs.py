"""Add durable runtime run coordination records.

Revision ID: 20260826_0002
Revises: 20260723_0001
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa

revision = "20260826_0002"
down_revision = "20260723_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "runtime_runs" in inspector.get_table_names():
        return

    op.create_table(
        "runtime_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=True),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("active_key", sa.String(length=1), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id"),
        sa.UniqueConstraint(
            "project_id", "thread_id", "idempotency_key", name="uq_runtime_runs_project_thread_idempotency"
        ),
        sa.UniqueConstraint(
            "project_id", "thread_id", "active_key", name="uq_runtime_runs_project_thread_active"
        ),
    )
    op.create_index("ix_runtime_runs_project_id", "runtime_runs", ["project_id"])
    op.create_index("ix_runtime_runs_thread_id", "runtime_runs", ["thread_id"])
    op.create_index("ix_runtime_runs_run_id", "runtime_runs", ["run_id"])
    op.create_index("ix_runtime_runs_status", "runtime_runs", ["status"])
    op.create_index("ix_runtime_runs_created_at", "runtime_runs", ["created_at"])


def downgrade() -> None:
    # 运行记录是审计证据；回滚应用不删除已有记录。
    pass
