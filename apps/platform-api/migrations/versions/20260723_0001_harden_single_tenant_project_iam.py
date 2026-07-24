"""强化单租户项目 IAM 安全状态。

Revision ID: 20260723_0001
Revises:
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa

revision = "20260723_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    missing_user_columns = {
        "must_change_password",
        "failed_login_attempts",
        "locked_until",
    } - user_columns
    if missing_user_columns:
        with op.batch_alter_table("users") as batch:
            if "must_change_password" in missing_user_columns:
                batch.add_column(
                    sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false())
                )
            if "failed_login_attempts" in missing_user_columns:
                batch.add_column(
                    sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0")
                )
            if "locked_until" in missing_user_columns:
                batch.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))

    refresh_columns = {column["name"] for column in inspector.get_columns("refresh_tokens")}
    missing_refresh_columns = {"family_id", "consumed_at"} - refresh_columns
    if missing_refresh_columns:
        with op.batch_alter_table("refresh_tokens") as batch:
            if "family_id" in missing_refresh_columns:
                batch.add_column(sa.Column("family_id", sa.String(length=64), nullable=True))
            if "consumed_at" in missing_refresh_columns:
                batch.add_column(sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE refresh_tokens SET family_id = token_id WHERE family_id IS NULL"))
    refresh_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("refresh_tokens")}
    refresh_indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("refresh_tokens")
    }
    with op.batch_alter_table("refresh_tokens") as batch:
        if "family_id" in refresh_columns:
            batch.alter_column("family_id", existing_type=sa.String(length=64), nullable=False)
        if "ix_refresh_tokens_family_id" not in refresh_indexes:
            batch.create_index("ix_refresh_tokens_family_id", ["family_id"], unique=False)

    if "service_account_project_grants" not in inspector.get_table_names():
        op.create_table(
            "service_account_project_grants",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("service_account_id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("created_by", sa.String(length=64), nullable=True),
            sa.Column("updated_by", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["service_account_id"], ["service_accounts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("service_account_id", "project_id", name="uq_service_account_project_grant"),
        )
    grant_indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("service_account_project_grants")
    }
    if "ix_service_account_project_grants_project_id" not in grant_indexes:
        op.create_index(
            "ix_service_account_project_grants_project_id",
            "service_account_project_grants",
            ["project_id"],
        )


def downgrade() -> None:
    # 非破坏性回滚：旧应用可忽略新增列和表，IAM 数据必须保留。
    pass
