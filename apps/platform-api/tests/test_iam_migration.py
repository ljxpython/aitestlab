from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config


class IamMigrationTest(unittest.TestCase):
    def test_upgrade_existing_identity_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "legacy-platform.db"
            connection = sqlite3.connect(database_path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE users (
                        id CHAR(32) PRIMARY KEY,
                        external_subject VARCHAR(255) NOT NULL UNIQUE,
                        email VARCHAR(255),
                        username VARCHAR(64) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        is_super_admin BOOLEAN NOT NULL,
                        platform_roles_json JSON NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    );
                    CREATE TABLE refresh_tokens (
                        id CHAR(32) PRIMARY KEY,
                        user_id CHAR(32) NOT NULL,
                        token_id VARCHAR(64) NOT NULL UNIQUE,
                        expires_at DATETIME NOT NULL,
                        revoked_at DATETIME,
                        created_at DATETIME NOT NULL
                    );
                    CREATE TABLE projects (id CHAR(32) PRIMARY KEY);
                    CREATE TABLE service_accounts (id CHAR(32) PRIMARY KEY);
                    CREATE TABLE agents (
                        id CHAR(32) PRIMARY KEY,
                        project_id CHAR(32) NOT NULL,
                        name VARCHAR(128) NOT NULL,
                        graph_id VARCHAR(128) NOT NULL,
                        langgraph_assistant_id VARCHAR(128) NOT NULL
                    );
                    CREATE UNIQUE INDEX uq_agents_project_name ON agents(project_id, name);
                    CREATE UNIQUE INDEX uq_agents_project_langgraph_assistant
                        ON agents(project_id, langgraph_assistant_id);
                    INSERT INTO users VALUES (
                        '00000000000000000000000000000001', 'legacy', NULL, 'legacy',
                        'hash', 'active', 0, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                    INSERT INTO refresh_tokens VALUES (
                        '00000000000000000000000000000002',
                        '00000000000000000000000000000001',
                        'legacy-token', '2099-01-01 00:00:00', NULL, CURRENT_TIMESTAMP
                    );
                    """
                )
                connection.commit()
            finally:
                connection.close()

            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
            command.upgrade(config, "head")

            connection = sqlite3.connect(database_path)
            try:
                user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
                refresh_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(refresh_tokens)")
                }
                family_id = connection.execute(
                    "SELECT family_id FROM refresh_tokens WHERE token_id = 'legacy-token'"
                ).fetchone()[0]
                grant_table = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='service_account_project_grants'"
                ).fetchone()
                agent_indexes = {
                    tuple(
                        item[2]
                        for item in connection.execute(f"PRAGMA index_info('{row[1]}')")
                    )
                    for row in connection.execute("PRAGMA index_list(agents)")
                    if row[2]
                }
            finally:
                connection.close()

            self.assertTrue({"must_change_password", "failed_login_attempts", "locked_until"} <= user_columns)
            self.assertTrue({"family_id", "consumed_at"} <= refresh_columns)
            self.assertEqual(family_id, "legacy-token")
            self.assertIsNotNone(grant_table)
            self.assertIn(("project_id", "graph_id"), agent_indexes)


if __name__ == "__main__":
    unittest.main()
