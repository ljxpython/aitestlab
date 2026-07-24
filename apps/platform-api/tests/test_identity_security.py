from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID

import jwt
from fastapi.testclient import TestClient

from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.core.security import InvalidTokenError, create_access_token, decode_access_token, hash_password
from app.factory import create_app
from app.modules.identity.infra.sqlalchemy.models import UserRecord
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository


class IdentitySecurityTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "identity-security.db"
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
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _create_user(
        self,
        *,
        username: str = "security-user",
        must_change_password: bool = False,
        platform_roles: tuple[str, ...] = (),
    ) -> str:
        with session_scope(self._session_factory) as session:
            user = SqlAlchemyIdentityRepository(session).create_user(
                username=username,
                password_hash=hash_password("password123"),
                external_subject=username,
                email=None,
                is_super_admin=False,
                platform_roles=platform_roles,
                must_change_password=must_change_password,
            )
            return str(user.id)

    def test_jwt_rejects_wrong_audience_and_unknown_kid(self) -> None:
        settings = self.app.state.settings
        valid = create_access_token(user_id="user-id", username="user", settings=settings)
        payload = jwt.decode(valid, options={"verify_signature": False})
        wrong_audience = jwt.encode(
            {**payload, "aud": "other-service"},
            settings.jwt_access_secret,
            algorithm=settings.jwt_algorithm,
            headers={"kid": settings.jwt_access_kid},
        )
        unknown_kid = jwt.encode(
            payload,
            settings.jwt_access_secret,
            algorithm=settings.jwt_algorithm,
            headers={"kid": "unknown"},
        )
        with self.assertRaises(InvalidTokenError):
            decode_access_token(wrong_audience, settings)
        with self.assertRaises(InvalidTokenError):
            decode_access_token(unknown_kid, settings)

    def test_application_starts_with_bootstrap_admin_enabled(self) -> None:
        app = create_app()
        settings = app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = True
        settings.database_url = f"sqlite:///{Path(self._tmpdir.name) / 'bootstrap.db'}"
        settings.bootstrap_admin_enabled = True

        with TestClient(app) as client:
            response = client.get("/_system/health")

        self.assertEqual(response.status_code, 200, response.text)

    def test_fifth_failed_login_locks_account(self) -> None:
        user_id = self._create_user()
        for _ in range(5):
            response = self.client.post(
                "/api/identity/session",
                json={"username": "security-user", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 401, response.text)
            self.assertEqual(response.json()["error"]["code"], "invalid_credentials")

        locked_response = self.client.post(
            "/api/identity/session",
            json={"username": "security-user", "password": "password123"},
        )
        self.assertEqual(locked_response.status_code, 401, locked_response.text)
        with session_scope(self._session_factory) as session:
            record = session.get(UserRecord, UUID(user_id))
            assert record is not None
            self.assertEqual(record.failed_login_attempts, 6)
            self.assertIsNotNone(record.locked_until)

    def test_legacy_password_change_flag_does_not_restrict_session(self) -> None:
        self._create_user(
            username="legacy-flag-user",
            must_change_password=True,
            platform_roles=("platform_viewer",),
        )
        login = self.client.post(
            "/api/identity/session",
            json={"username": "legacy-flag-user", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        payload = login.json()
        self.assertTrue(payload["user"]["must_change_password"])
        token = payload["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        projects = self.client.get("/api/projects", headers=headers)
        self.assertEqual(projects.status_code, 200, projects.text)

        refreshed = self.client.post(
            "/api/identity/session/refresh",
            json={"refresh_token": payload["tokens"]["refresh_token"]},
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)

        changed = self.client.post(
            "/api/identity/password/change",
            headers=headers,
            json={"old_password": "password123", "new_password": "new-password123"},
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertTrue(changed.json()["access_token"])

    def test_refresh_token_replay_revokes_family(self) -> None:
        self._create_user(username="refresh-user")
        login = self.client.post(
            "/api/identity/session",
            json={"username": "refresh-user", "password": "password123"},
        )
        refresh_token = login.json()["tokens"]["refresh_token"]
        first = self.client.post(
            "/api/identity/session/refresh",
            json={"refresh_token": refresh_token},
        )
        self.assertEqual(first.status_code, 200, first.text)
        replay = self.client.post(
            "/api/identity/session/refresh",
            json={"refresh_token": refresh_token},
        )
        self.assertEqual(replay.status_code, 401, replay.text)
        self.assertEqual(replay.json()["error"]["code"], "refresh_token_replayed")
        replacement = self.client.post(
            "/api/identity/session/refresh",
            json={"refresh_token": first.json()["refresh_token"]},
        )
        self.assertEqual(replacement.status_code, 401, replacement.text)

    def test_refresh_token_conditional_update_has_single_concurrent_winner(self) -> None:
        self._create_user(username="concurrent-refresh-user")
        login = self.client.post(
            "/api/identity/session",
            json={"username": "concurrent-refresh-user", "password": "password123"},
        )
        refresh_token = login.json()["tokens"]["refresh_token"]
        token_id = jwt.decode(refresh_token, options={"verify_signature": False})["jti"]
        barrier = Barrier(2)

        def consume() -> str | None:
            session = self._session_factory()
            try:
                barrier.wait()
                _, state = SqlAlchemyIdentityRepository(session).consume_refresh_token(token_id)
                session.commit()
                return state
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            states = sorted(executor.map(lambda _: consume(), range(2)))

        self.assertEqual(states, ["consumed", "replayed"])


if __name__ == "__main__":
    unittest.main()
