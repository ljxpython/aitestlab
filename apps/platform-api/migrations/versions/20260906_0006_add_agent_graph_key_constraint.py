"""Enforce project-scoped agent graph keys."""

from alembic import op
import sqlalchemy as sa


revision = "20260906_0006"
down_revision = "20260905_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "agents" not in inspector.get_table_names():
        return

    duplicate = bind.execute(
        sa.text(
            "SELECT project_id, graph_id FROM agents "
            "GROUP BY project_id, graph_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot add uq_agents_project_graph_id: duplicate project_id/graph_id rows exist"
        )

    constraints = {
        item["name"] for item in inspector.get_unique_constraints("agents")
    }
    if "uq_agents_project_graph_id" not in constraints:
        with op.batch_alter_table("agents") as batch:
            batch.create_unique_constraint(
                "uq_agents_project_graph_id",
                ["project_id", "graph_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    if "agents" in sa.inspect(bind).get_table_names():
        with op.batch_alter_table("agents") as batch:
            batch.drop_constraint("uq_agents_project_graph_id", type_="unique")
