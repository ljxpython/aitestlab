from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.core.security import create_access_token, hash_password
from app.factory import create_app
from app.modules.audit.infra.sqlalchemy.models import AuditLogRecord
from app.modules.iam.domain import ProjectRole
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class IamProjectGovernanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "iam-project-governance.db"
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
        self.admin_id = self._create_user("admin", ("platform_super_admin",))
        self.viewer_id = self._create_user("viewer", ("platform_viewer",))
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _create_user(self, username: str, roles: tuple[str, ...]) -> str:
        with session_scope(self._session_factory) as session:
            user = SqlAlchemyIdentityRepository(session).create_user(
                username=username,
                password_hash=hash_password("password123"),
                external_subject=username,
                email=None,
                platform_roles=roles,
                is_super_admin="platform_super_admin" in roles,
            )
            return str(user.id)

    def _headers(self, user_id: str, username: str, project_id: str | None = None) -> dict[str, str]:
        token = create_access_token(user_id=user_id, username=username, settings=self.app.state.settings)
        headers = {"Authorization": f"Bearer {token}"}
        if project_id:
            headers["x-project-id"] = project_id
        return headers

    def test_project_creation_takeover_and_scope_mismatch(self) -> None:
        denied = self.client.post(
            "/api/projects",
            headers=self._headers(self.viewer_id, "viewer"),
            json={"name": "Denied"},
        )
        self.assertEqual(denied.status_code, 403, denied.text)

        created = self.client.post(
            "/api/projects",
            headers=self._headers(self.admin_id, "admin"),
            json={"name": "Project A"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        project_id = created.json()["id"]
        access = self.client.get(
            f"/api/projects/{project_id}/access",
            headers=self._headers(self.admin_id, "admin"),
        )
        self.assertEqual(access.json()["roles"], ["project_admin"])

        mismatch = self.client.get(
            f"/api/projects/{project_id}/access",
            headers=self._headers(self.admin_id, "admin", "00000000-0000-0000-0000-000000000000"),
        )
        self.assertEqual(mismatch.status_code, 400, mismatch.text)
        self.assertEqual(mismatch.json()["error"]["code"], "project_scope_mismatch")

    def test_project_member_candidates_do_not_require_global_user_directory(self) -> None:
        created = self.client.post(
            "/api/projects",
            headers=self._headers(self.admin_id, "admin"),
            json={"name": "Project Candidates"},
        )
        project_id = created.json()["id"]
        candidates = self.client.get(
            f"/api/projects/{project_id}/member-candidates",
            headers=self._headers(self.admin_id, "admin"),
        )
        self.assertEqual(candidates.status_code, 200, candidates.text)
        self.assertEqual(candidates.json()["items"][0]["username"], "viewer")

    def test_super_admin_needs_explicit_takeover_and_last_admin_is_protected(self) -> None:
        owner_id = self._create_user("owner", ())
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyIdentityRepository(session)
            owner = repository.get_user_by_id(UUID(owner_id))
            assert owner is not None
            projects = SqlAlchemyProjectsRepository(session)
            tenant = projects.get_or_create_default_tenant()
            project = projects.create_project(
                tenant_id=tenant.id,
                name="Owned Project",
                description="",
            )
            projects.upsert_project_member(
                project_id=project.id,
                user_id=owner.id,
                role=ProjectRole.ADMIN,
            )
            project_id = str(project.id)

        before = self.client.get(
            f"/api/projects/{project_id}/members",
            headers=self._headers(self.admin_id, "admin", project_id),
        )
        self.assertEqual(before.status_code, 403, before.text)

        empty_reason = self.client.post(
            f"/api/projects/{project_id}/takeover",
            headers=self._headers(self.admin_id, "admin"),
            json={"reason": ""},
        )
        self.assertEqual(empty_reason.status_code, 422, empty_reason.text)

        takeover = self.client.post(
            f"/api/projects/{project_id}/takeover",
            headers={**self._headers(self.admin_id, "admin"), "x-tenant-id": "forged-tenant"},
            json={"reason": "owner unavailable"},
        )
        self.assertEqual(takeover.status_code, 200, takeover.text)
        self.assertEqual(takeover.json()["role"], "project_admin")
        with session_scope(self._session_factory) as session:
            event = session.scalar(
                select(AuditLogRecord)
                .where(
                    AuditLogRecord.action == "project.takeover.completed",
                    AuditLogRecord.status_code == 200,
                )
                .order_by(AuditLogRecord.created_at.desc())
                .limit(1)
            )
            assert event is not None
            self.assertNotEqual(event.tenant_id, "forged-tenant")
            self.assertEqual(event.project_id, project_id)
            self.assertEqual(event.metadata_json.get("reason"), "owner unavailable")
            self.assertEqual(set(event.metadata_json) & {"password", "token", "authorization"}, set())

        recovery = self.client.post(
            f"/api/projects/{project_id}/admin-recovery",
            headers=self._headers(self.admin_id, "admin"),
            json={"user_id": self.viewer_id},
        )
        self.assertEqual(recovery.status_code, 200, recovery.text)
        self.assertEqual(recovery.json()["user_id"], self.viewer_id)
        self.assertEqual(recovery.json()["role"], "project_admin")

        after = self.client.get(
            f"/api/projects/{project_id}/members",
            headers=self._headers(self.admin_id, "admin", project_id),
        )
        self.assertEqual(after.status_code, 200, after.text)

        remove_owner = self.client.delete(
            f"/api/projects/{project_id}/members/{owner_id}",
            headers=self._headers(self.admin_id, "admin", project_id),
        )
        self.assertEqual(remove_owner.status_code, 200, remove_owner.text)
        remove_recovered = self.client.delete(
            f"/api/projects/{project_id}/members/{self.viewer_id}",
            headers=self._headers(self.admin_id, "admin", project_id),
        )
        self.assertEqual(remove_recovered.status_code, 200, remove_recovered.text)
        remove_last = self.client.delete(
            f"/api/projects/{project_id}/members/{self.admin_id}",
            headers=self._headers(self.admin_id, "admin", project_id),
        )
        self.assertEqual(remove_last.status_code, 409, remove_last.text)
        self.assertEqual(remove_last.json()["error"]["code"], "cannot_remove_last_admin")

    def test_archived_project_loses_content_access_and_can_be_restored(self) -> None:
        created = self.client.post(
            "/api/projects",
            headers=self._headers(self.admin_id, "admin"),
            json={"name": "Lifecycle"},
        )
        project_id = created.json()["id"]

        archived = self.client.post(
            f"/api/projects/{project_id}/archive",
            headers=self._headers(self.admin_id, "admin"),
        )
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()["status"], "disabled")

        access = self.client.get(
            f"/api/projects/{project_id}/access",
            headers=self._headers(self.admin_id, "admin"),
        )
        self.assertEqual(access.status_code, 200, access.text)
        self.assertEqual(access.json()["permissions"], [])

        members = self.client.get(
            f"/api/projects/{project_id}/members",
            headers=self._headers(self.admin_id, "admin", project_id),
        )
        self.assertEqual(members.status_code, 404, members.text)

        member_write = self.client.put(
            f"/api/projects/{project_id}/members/{self.viewer_id}",
            headers=self._headers(self.admin_id, "admin", project_id),
            json={"role": "project_editor"},
        )
        self.assertEqual(member_write.status_code, 404, member_write.text)

        restored = self.client.post(
            f"/api/projects/{project_id}/restore",
            headers=self._headers(self.admin_id, "admin"),
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["status"], "active")


if __name__ == "__main__":
    unittest.main()
