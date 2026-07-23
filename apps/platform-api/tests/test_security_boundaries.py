from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.context import build_request_context
from app.core.db import build_engine, create_core_tables, session_scope
from app.core.security import hash_password
from app.entrypoints.http.middleware.audit_log import _should_capture_response
from app.factory import create_app
from app.modules.audit.infra.sqlalchemy.models import AuditLogRecord
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository


class SecurityBoundariesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "security-boundaries.db"
        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = True
        settings.database_url = f"sqlite:///{database_path}"
        settings.bootstrap_admin_enabled = False
        settings.api_docs_enabled = False
        settings.auth_required = False
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._tmpdir.cleanup()

    def test_optional_auth_does_not_trust_actor_headers(self) -> None:
        response = self.client.get(
            "/api/users",
            headers={
                "x-user-id": "forged-user",
                "x-platform-roles": "platform_super_admin",
            },
        )

        self.assertEqual(response.status_code, 401, response.text)

    def test_request_context_actor_is_anonymous_despite_identity_headers(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/users",
                "query_string": b"",
                "headers": [
                    (b"x-user-id", b"forged-user"),
                    (b"x-platform-roles", b"platform_super_admin"),
                ],
                "client": ("127.0.0.1", 1),
                "server": ("testserver", 80),
                "scheme": "http",
            }
        )

        self.assertFalse(build_request_context(request).actor.is_authenticated)

    def test_successful_login_audit_records_authenticated_actor(self) -> None:
        session_factory = self.app.state.db_session_factory
        with session_scope(session_factory) as session:
            repository = SqlAlchemyIdentityRepository(session)
            user = repository.create_user(
                username="login-user",
                password_hash=hash_password("password123"),
                external_subject="login-subject",
                email="login@example.com",
                platform_roles=("platform_viewer",),
                is_super_admin=False,
            )
            user_id = str(user.id)

        response = self.client.post(
            "/api/identity/session",
            json={"username": "login-user", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200, response.text)

        with session_scope(session_factory) as session:
            event = session.scalar(
                select(AuditLogRecord)
                .where(AuditLogRecord.action == "identity.session.created")
                .order_by(AuditLogRecord.created_at.desc())
                .limit(1)
            )
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual(event.actor_user_id, user_id)
            self.assertEqual(event.actor_subject, "login-subject")
            self.assertEqual(event.target_id, user_id)

        failed_response = self.client.post(
            "/api/identity/session",
            json={"username": "login-user", "password": "wrong-password"},
        )
        self.assertEqual(failed_response.status_code, 401, failed_response.text)
        with session_scope(session_factory) as session:
            failed_event = session.scalar(
                select(AuditLogRecord)
                .where(
                    AuditLogRecord.action == "identity.session.created",
                    AuditLogRecord.status_code == 401,
                )
                .order_by(AuditLogRecord.created_at.desc())
                .limit(1)
            )
            self.assertIsNotNone(failed_event)
            assert failed_event is not None
            self.assertIsNone(failed_event.actor_user_id)
            self.assertIsNone(failed_event.actor_subject)

    def test_audit_capture_requires_bounded_json(self) -> None:
        bounded = Response(
            content=b'{"ok":true}',
            media_type="application/json",
            headers={"content-length": "11"},
        )
        unbounded = Response(content=b"", media_type="application/json")
        del unbounded.headers["content-length"]
        file_response = Response(
            content=b'{"ok":true}',
            media_type="application/json",
            headers={
                "content-length": "11",
                "content-disposition": 'attachment; filename="result.json"',
            },
        )

        self.assertTrue(_should_capture_response(bounded))
        self.assertFalse(_should_capture_response(unbounded))
        self.assertFalse(_should_capture_response(file_response))

        stream_response = StreamingResponse(
            iter([b'{"ok":true}']),
            media_type="application/json",
        )
        self.assertFalse(_should_capture_response(stream_response))


if __name__ == "__main__":
    unittest.main()
