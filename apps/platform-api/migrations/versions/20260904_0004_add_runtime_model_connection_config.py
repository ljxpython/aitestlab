"""Add minimal runtime model connection configuration."""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0004"
down_revision = "20260826_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "runtime_catalog_models" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("runtime_catalog_models")}
    additions = {
        "provider": sa.String(length=64),
        "base_url": sa.String(length=2048),
        "protocol": sa.String(length=64),
        "model_name": sa.String(length=255),
        "api_key_ciphertext": sa.Text(),
        "enabled": sa.Boolean(),
    }
    for name, column in additions.items():
        if name not in columns:
            kwargs = {"server_default": sa.text("true")} if name == "enabled" else {}
            op.add_column("runtime_catalog_models", sa.Column(name, column, nullable=True, **kwargs))


def downgrade() -> None:
    # Credentials are deliberately retained during downgrade.
    pass
