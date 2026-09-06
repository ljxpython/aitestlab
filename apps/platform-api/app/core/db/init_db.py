from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.db.base import Base


def import_core_models() -> None:
    # Import modules here so metadata is fully populated before create_all runs.
    import app.modules.identity.infra.sqlalchemy.models  # noqa: F401
    import app.modules.projects.infra.sqlalchemy.models  # noqa: F401
    import app.modules.announcements.infra.sqlalchemy.models  # noqa: F401
    import app.modules.agents.infra.sqlalchemy.models  # noqa: F401
    import app.modules.audit.infra.sqlalchemy.models  # noqa: F401
    import app.modules.operations.infra.sqlalchemy.models  # noqa: F401
    import app.modules.runtime_catalog.infra.sqlalchemy.models  # noqa: F401
    import app.modules.runtime_gateway.infra.sqlalchemy.models  # noqa: F401
    import app.modules.runtime_policies.infra.sqlalchemy.models  # noqa: F401
    import app.modules.platform_config.infra.sqlalchemy.models  # noqa: F401
    import app.modules.project_knowledge.infra.sqlalchemy.models  # noqa: F401
    import app.modules.service_accounts.infra.sqlalchemy.models  # noqa: F401


def create_core_tables(engine: Engine) -> None:
    import_core_models()

    Base.metadata.create_all(engine)
    _ensure_user_columns(engine)
    _ensure_runtime_columns(engine)


def _ensure_user_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []
    dialect = engine.dialect.name

    if "platform_roles_json" not in columns:
        if dialect == "postgresql":
            statements.append(
                """
                ALTER TABLE users
                ADD COLUMN platform_roles_json JSON NOT NULL DEFAULT '[]'::json
                """
            )
            statements.append(
                """
                UPDATE users
                SET platform_roles_json = '["platform_super_admin"]'::json
                WHERE is_super_admin = TRUE
                """
            )
        else:
            statements.append(
                """
                ALTER TABLE users
                ADD COLUMN platform_roles_json JSON NOT NULL DEFAULT '[]'
                """
            )
            statements.append(
                """
                UPDATE users
                SET platform_roles_json = '["platform_super_admin"]'
                WHERE is_super_admin = 1
                """
            )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_runtime_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "operations" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("operations")}
    statements: list[str] = []

    if "archived_at" not in columns:
        statements.append("ALTER TABLE operations ADD COLUMN archived_at DATETIME")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
