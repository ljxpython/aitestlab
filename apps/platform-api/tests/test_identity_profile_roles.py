from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.factory import create_app
from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.core.security import create_access_token, hash_password
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository
from app.modules.iam.domain import ProjectRole
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class IdentityProfileRolesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "identity-profile-roles.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.username = "profile-user"
        self.password = "admin123456"
        self.user_id, self.project_id = self._create_user_and_project()

        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.database_url = str(self._engine.url)
        settings.bootstrap_admin_enabled = False
        settings.api_docs_enabled = False
        settings.auth_required = True

        self.access_token = create_access_token(
            user_id=self.user_id,
            username=self.username,
            settings=settings,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _create_user_and_project(self) -> tuple[str, str]:
        with session_scope(self._session_factory) as session:
            identity_repository = SqlAlchemyIdentityRepository(session)
            user = identity_repository.create_user(
                username=self.username,
                password_hash=hash_password(self.password),
                external_subject=self.username,
                email="profile-user@example.com",
                is_super_admin=False,
            )
            projects_repository = SqlAlchemyProjectsRepository(session)
            tenant = projects_repository.get_or_create_default_tenant()
            project = projects_repository.create_project(
                tenant_id=tenant.id,
                name="Identity Roles Project",
                description="identity profile role test",
            )
            projects_repository.upsert_project_member(
                project_id=project.id,
                user_id=user.id,
                role=ProjectRole.ADMIN,
            )
            return str(user.id), str(project.id)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def test_identity_me_omits_project_roles(self) -> None:
        response = self.client.get("/api/identity/me", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["username"], self.username)
        self.assertEqual(payload["platform_roles"], [])
        self.assertNotIn("project_roles", payload)

    def test_login_response_omits_project_roles_and_access_is_project_scoped(self) -> None:
        response = self.client.post(
            "/api/identity/session",
            json={
                "username": self.username,
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["user"]["username"], self.username)
        self.assertEqual(payload["user"]["platform_roles"], [])
        self.assertNotIn("project_roles", payload["user"])

        access_response = self.client.get(
            f"/api/projects/{self.project_id}/access",
            headers=self._auth_headers(),
        )
        self.assertEqual(access_response.status_code, 200, access_response.text)
        access = access_response.json()
        self.assertEqual(access["roles"], ["project_admin"])
        self.assertIn("project.member.write", access["permissions"])


if __name__ == "__main__":
    unittest.main()
