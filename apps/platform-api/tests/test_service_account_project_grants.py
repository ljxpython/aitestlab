from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.core.security import create_access_token, hash_password
from app.factory import create_app
from app.modules.audit.infra.sqlalchemy.models import AuditLogRecord
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository
from app.modules.service_accounts.infra.sqlalchemy.models import ServiceAccountTokenRecord


class ServiceAccountProjectGrantsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "service-account-project-grants.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)
        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.database_url = str(self._engine.url)
        settings.bootstrap_admin_enabled = False
        settings.api_docs_enabled = False
        settings.auth_required = True
        with session_scope(self._session_factory) as session:
            admin = SqlAlchemyIdentityRepository(session).create_user(
                username="admin",
                password_hash=hash_password("password123"),
                external_subject="admin",
                email=None,
                platform_roles=("platform_super_admin",),
                is_super_admin=True,
            )
        self.admin_id = str(admin.id)
        with session_scope(self._session_factory) as session:
            operator = SqlAlchemyIdentityRepository(session).create_user(
                username="operator",
                password_hash=hash_password("password123"),
                external_subject="operator",
                email=None,
                platform_roles=("platform_operator",),
                is_super_admin=False,
            )
            self.operator_id = str(operator.id)
        self.admin_token = create_access_token(
            user_id=self.admin_id,
            username="admin",
            settings=settings,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.admin_token}"}

    def _operator_headers(self) -> dict[str, str]:
        token = create_access_token(
            user_id=self.operator_id,
            username="operator",
            settings=self.app.state.settings,
        )
        return {"Authorization": f"Bearer {token}"}

    def test_grant_controls_api_key_project_access_without_key_rotation(self) -> None:
        project = self.client.post(
            "/api/projects",
            headers=self._admin_headers(),
            json={"name": "Machine Project"},
        ).json()
        account = self.client.post(
            "/api/service-accounts",
            headers=self._admin_headers(),
            json={"name": "machine-reader", "platform_roles": ["platform_viewer"]},
        ).json()
        token = self.client.post(
            f"/api/service-accounts/{account['id']}/tokens",
            headers=self._admin_headers(),
            json={"name": "default"},
        ).json()["plain_text_token"]

        api_headers = {"x-platform-api-key": token, "x-project-id": project["id"]}
        before = self.client.get(f"/api/projects/{project['id']}/access", headers=api_headers)
        self.assertEqual(before.status_code, 200, before.text)
        self.assertEqual(before.json()["roles"], [])

        grant = self.client.put(
            f"/api/service-accounts/{account['id']}/project-grants/{project['id']}",
            headers=self._admin_headers(),
            json={"role": "project_executor"},
        )
        self.assertEqual(grant.status_code, 200, grant.text)
        after = self.client.get(f"/api/projects/{project['id']}/access", headers=api_headers)
        self.assertEqual(after.json()["roles"], ["project_executor"])

        removed = self.client.delete(
            f"/api/service-accounts/{account['id']}/project-grants/{project['id']}",
            headers=self._admin_headers(),
        )
        self.assertEqual(removed.status_code, 204, removed.text)
        revoked = self.client.get(f"/api/projects/{project['id']}/access", headers=api_headers)
        self.assertEqual(revoked.json()["roles"], [])

    def test_grant_management_requires_super_admin_and_is_project_scoped(self) -> None:
        project_a = self.client.post(
            "/api/projects",
            headers=self._admin_headers(),
            json={"name": "Machine A"},
        ).json()
        project_b = self.client.post(
            "/api/projects",
            headers=self._admin_headers(),
            json={"name": "Machine B"},
        ).json()
        account = self.client.post(
            "/api/service-accounts",
            headers=self._admin_headers(),
            json={"name": "machine-scoped", "platform_roles": ["platform_viewer"]},
        ).json()

        denied = self.client.put(
            f"/api/service-accounts/{account['id']}/project-grants/{project_a['id']}",
            headers=self._operator_headers(),
            json={"role": "project_executor"},
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        with session_scope(self._session_factory) as session:
            event = session.scalar(
                select(AuditLogRecord)
                .where(
                    AuditLogRecord.action == "service_account.project_grant.upserted",
                    AuditLogRecord.status_code == 403,
                )
                .order_by(AuditLogRecord.created_at.desc())
                .limit(1)
            )
            assert event is not None
            self.assertEqual(event.result, "failed")
            self.assertEqual(event.target_id, project_a["id"])

        token = self.client.post(
            f"/api/service-accounts/{account['id']}/tokens",
            headers=self._admin_headers(),
            json={"name": "scoped"},
        ).json()["plain_text_token"]
        self.client.put(
            f"/api/service-accounts/{account['id']}/project-grants/{project_a['id']}",
            headers=self._admin_headers(),
            json={"role": "project_executor"},
        )
        access_b = self.client.get(
            f"/api/projects/{project_b['id']}/access",
            headers={"x-platform-api-key": token, "x-project-id": project_b["id"]},
        )
        self.assertEqual(access_b.status_code, 200, access_b.text)
        self.assertEqual(access_b.json()["roles"], [])

    def test_inactive_account_token_or_project_rejects_granted_access(self) -> None:
        project = self.client.post(
            "/api/projects",
            headers=self._admin_headers(),
            json={"name": "Machine Lifecycle"},
        ).json()
        account = self.client.post(
            "/api/service-accounts",
            headers=self._admin_headers(),
            json={"name": "machine-lifecycle", "platform_roles": ["platform_viewer"]},
        ).json()
        token_payload = self.client.post(
            f"/api/service-accounts/{account['id']}/tokens",
            headers=self._admin_headers(),
            json={"name": "lifecycle"},
        ).json()
        token = token_payload["plain_text_token"]
        token_id = token_payload["token"]["id"]
        self.client.put(
            f"/api/service-accounts/{account['id']}/project-grants/{project['id']}",
            headers=self._admin_headers(),
            json={"role": "project_executor"},
        )
        api_headers = {"x-platform-api-key": token, "x-project-id": project["id"]}
        self.assertEqual(
            self.client.get(f"/api/projects/{project['id']}/access", headers=api_headers).json()["roles"],
            ["project_executor"],
        )

        archived = self.client.post(
            f"/api/projects/{project['id']}/archive",
            headers=self._admin_headers(),
        )
        self.assertEqual(archived.status_code, 200, archived.text)
        archived_access = self.client.get(
            f"/api/projects/{project['id']}/access",
            headers=api_headers,
        )
        self.assertEqual(archived_access.status_code, 200, archived_access.text)
        self.assertEqual(archived_access.json()["roles"], [])

        self.client.post(
            f"/api/projects/{project['id']}/restore",
            headers=self._admin_headers(),
        )
        self.client.delete(
            f"/api/service-accounts/{account['id']}/tokens/{token_id}",
            headers=self._admin_headers(),
        )
        revoked = self.client.get(f"/api/projects/{project['id']}/access", headers=api_headers)
        self.assertEqual(revoked.status_code, 401, revoked.text)

        replacement = self.client.post(
            f"/api/service-accounts/{account['id']}/tokens",
            headers=self._admin_headers(),
            json={"name": "replacement"},
        ).json()["plain_text_token"]
        self.client.patch(
            f"/api/service-accounts/{account['id']}",
            headers=self._admin_headers(),
            json={"status": "disabled"},
        )
        disabled = self.client.get(
            f"/api/projects/{project['id']}/access",
            headers={"x-platform-api-key": replacement, "x-project-id": project["id"]},
        )
        self.assertEqual(disabled.status_code, 401, disabled.text)

        self.client.patch(
            f"/api/service-accounts/{account['id']}",
            headers=self._admin_headers(),
            json={"status": "active"},
        )
        expiring_payload = self.client.post(
            f"/api/service-accounts/{account['id']}/tokens",
            headers=self._admin_headers(),
            json={"name": "expired"},
        ).json()
        with session_scope(self._session_factory) as session:
            record = session.get(ServiceAccountTokenRecord, UUID(expiring_payload["token"]["id"]))
            assert record is not None
            record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        expired = self.client.get(
            f"/api/projects/{project['id']}/access",
            headers={
                "x-platform-api-key": expiring_payload["plain_text_token"],
                "x-project-id": project["id"],
            },
        )
        self.assertEqual(expired.status_code, 401, expired.text)


if __name__ == "__main__":
    unittest.main()
