from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.core.security import create_access_token, hash_password
from app.factory import create_app
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository


class UserPlatformRolesApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "user-platform-roles.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.admin_username = "admin-user"
        self.admin_password = "admin123456"
        self.admin_user_id = self._create_admin_user()

        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.database_url = str(self._engine.url)
        settings.bootstrap_admin_enabled = False
        settings.api_docs_enabled = False
        settings.auth_required = True

        self.admin_access_token = create_access_token(
            user_id=self.admin_user_id,
            username=self.admin_username,
            settings=settings,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _create_admin_user(self) -> str:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyIdentityRepository(session)
            user = repository.create_user(
                username=self.admin_username,
                password_hash=hash_password(self.admin_password),
                external_subject=self.admin_username,
                email="admin@example.com",
                platform_roles=("platform_super_admin",),
                is_super_admin=True,
            )
            return str(user.id)

    def _auth_headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.admin_access_token}",
            "Content-Type": "application/json",
        }

    def test_create_update_and_resolve_user_platform_roles(self) -> None:
        create_response = self.client.post(
            "/api/users",
            headers=self._auth_headers(),
            json={
                "username": "operator-user",
                "password": "operator123456",
                "platform_roles": ["platform_operator"],
            },
        )

        self.assertEqual(create_response.status_code, 200, create_response.text)
        created_payload = create_response.json()
        self.assertEqual(created_payload["platform_roles"], ["platform_operator"])
        self.assertFalse(created_payload["is_super_admin"])

        user_id = created_payload["id"]
        operator_token = create_access_token(
            user_id=user_id,
            username="operator-user",
            settings=self.app.state.settings,
        )

        profile_response = self.client.get(
            "/api/identity/me",
            headers=self._auth_headers(operator_token),
        )
        self.assertEqual(profile_response.status_code, 200, profile_response.text)
        self.assertEqual(profile_response.json()["platform_roles"], ["platform_operator"])

        update_response = self.client.patch(
            f"/api/users/{user_id}",
            headers=self._auth_headers(),
            json={
                "platform_roles": ["platform_viewer"],
            },
        )
        self.assertEqual(update_response.status_code, 200, update_response.text)
        updated_payload = update_response.json()
        self.assertEqual(updated_payload["platform_roles"], ["platform_viewer"])
        self.assertFalse(updated_payload["is_super_admin"])

    def test_last_super_admin_remains_protected_after_platform_role_migration(self) -> None:
        response = self.client.patch(
            f"/api/users/{self.admin_user_id}",
            headers=self._auth_headers(),
            json={
                "platform_roles": [],
            },
        )

        self.assertEqual(response.status_code, 409, response.text)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "last_super_admin_protected")

    def test_operator_cannot_create_or_promote_super_admin(self) -> None:
        operator_response = self.client.post(
            "/api/users",
            headers=self._auth_headers(),
            json={
                "username": "limited-operator",
                "password": "operator123456",
                "platform_roles": ["platform_operator"],
            },
        )
        self.assertEqual(operator_response.status_code, 200, operator_response.text)
        operator_id = operator_response.json()["id"]
        operator_token = create_access_token(
            user_id=operator_id,
            username="limited-operator",
            settings=self.app.state.settings,
        )

        create_response = self.client.post(
            "/api/users",
            headers=self._auth_headers(operator_token),
            json={
                "username": "forged-admin",
                "password": "forged123456",
                "platform_roles": ["platform_super_admin"],
            },
        )
        self.assertEqual(create_response.status_code, 403, create_response.text)

        promote_response = self.client.patch(
            f"/api/users/{operator_id}",
            headers=self._auth_headers(operator_token),
            json={"platform_roles": ["platform_super_admin"]},
        )
        self.assertEqual(promote_response.status_code, 403, promote_response.text)

        demote_response = self.client.patch(
            f"/api/users/{self.admin_user_id}",
            headers=self._auth_headers(operator_token),
            json={"platform_roles": []},
        )
        self.assertEqual(demote_response.status_code, 403, demote_response.text)

    def test_create_user_rejects_short_password(self) -> None:
        response = self.client.post(
            "/api/users",
            headers=self._auth_headers(),
            json={"username": "short-password", "password": "x"},
        )

        self.assertEqual(response.status_code, 422, response.text)


if __name__ == "__main__":
    unittest.main()
