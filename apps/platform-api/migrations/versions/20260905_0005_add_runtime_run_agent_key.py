"""Persist the immutable agent binding for a thread's durable runs."""

from alembic import op
import sqlalchemy as sa

revision = "20260905_0005"
down_revision = "20260904_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runtime_runs",
        sa.Column("agent_key", sa.String(length=128), nullable=False, server_default=""),
    )
    op.add_column("runtime_runs", sa.Column("context_hash", sa.String(length=128), nullable=True))
    op.add_column("runtime_runs", sa.Column("context_snapshot", sa.JSON(), nullable=True))
    op.add_column("runtime_runs", sa.Column("policy_version", sa.String(length=255), nullable=True))
    op.create_index("ix_runtime_runs_agent_key", "runtime_runs", ["agent_key"])


def downgrade() -> None:
    op.drop_index("ix_runtime_runs_agent_key", table_name="runtime_runs")
    op.drop_column("runtime_runs", "agent_key")
    op.drop_column("runtime_runs", "context_hash")
    op.drop_column("runtime_runs", "context_snapshot")
    op.drop_column("runtime_runs", "policy_version")
