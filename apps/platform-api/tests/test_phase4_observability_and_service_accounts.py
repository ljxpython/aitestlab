from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.factory import create_app
from app.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from app.core.security import create_access_token, hash_password
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository
from app.modules.operations.application.execution import OperationExecutorRegistry
from app.modules.operations.application.heartbeat import OperationWorkerHeartbeatReporter
from app.modules.operations.application.worker import OperationWorker


class Phase4ObservabilityAndServiceAccountsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "phase4-observability.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)
        self.user_id = self._create_admin_user()

        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.database_url = str(self._engine.url)
        settings.bootstrap_admin_enabled = False
        settings.api_docs_enabled = False
        settings.service_accounts_enabled = True
        settings.auth_required = True

        self.access_token = create_access_token(
            user_id=self.user_id,
            username="phase4-admin",
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
                username="phase4-admin",
                password_hash=hash_password("admin123456"),
                external_subject="phase4-admin",
                email="phase4@example.com",
                is_super_admin=True,
            )
            return str(user.id)

    def _create_operator_user(self) -> tuple[str, str]:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyIdentityRepository(session)
            user = repository.create_user(
                username="phase4-operator",
                password_hash=hash_password("operator123456"),
                external_subject="phase4-operator",
                email="operator@example.com",
                platform_roles=("platform_operator",),
                is_super_admin=False,
            )
        token = create_access_token(
            user_id=str(user.id),
            username=user.username,
            settings=self.app.state.settings,
        )
        return str(user.id), token

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def test_service_account_api_key_can_read_metrics_but_cannot_write_platform_config(self) -> None:
        create_response = self.client.post(
            "/api/service-accounts",
            headers=self._auth_headers(),
            json={
                "name": "phase4-viewer",
                "description": "phase-4 viewer key",
                "platform_roles": ["platform_viewer"],
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        service_account_id = create_response.json()["id"]

        token_response = self.client.post(
            f"/api/service-accounts/{service_account_id}/tokens",
            headers=self._auth_headers(),
            json={"name": "default"},
        )
        self.assertEqual(token_response.status_code, 200, token_response.text)
        api_key = token_response.json()["plain_text_token"]

        metrics_response = self.client.get(
            "/_system/metrics",
            headers={"x-platform-api-key": api_key},
        )
        self.assertEqual(metrics_response.status_code, 200, metrics_response.text)
        payload = metrics_response.json()
        self.assertIn("requests", payload)
        self.assertIn("operations", payload)
        self.assertIn("workers", payload)

        users_response = self.client.get(
            "/api/users",
            headers={"x-platform-api-key": api_key},
        )
        self.assertEqual(users_response.status_code, 200, users_response.text)

        forbidden_response = self.client.patch(
            "/_system/platform-config/feature-flags",
            headers={"x-platform-api-key": api_key},
            json={"feature_flags": {"operations_enabled": False}},
        )
        self.assertEqual(forbidden_response.status_code, 403, forbidden_response.text)

    def test_ready_probe_turns_ready_after_worker_heartbeat(self) -> None:
        initial_ready = self.client.get("/_system/probes/ready")
        self.assertEqual(initial_ready.status_code, 200, initial_ready.text)
        self.assertEqual(initial_ready.json()["status"], "not_ready")

        worker = OperationWorker(
            session_factory=self._session_factory,
            executor_registry=OperationExecutorRegistry(()),
            poll_interval_seconds=0.01,
            idle_sleep_seconds=0.01,
            heartbeat_reporter=OperationWorkerHeartbeatReporter(
                session_factory=self._session_factory,
                queue_backend="db_polling",
                heartbeat_interval_seconds=5.0,
            ),
        )
        self.assertFalse(self._run_async(worker.run_once()))

        ready_response = self.client.get("/_system/probes/ready")
        self.assertEqual(ready_response.status_code, 200, ready_response.text)
        self.assertEqual(ready_response.json()["status"], "ready")

        health_response = self.client.get("/_system/health")
        self.assertEqual(health_response.status_code, 200, health_response.text)
        self.assertEqual(health_response.json()["status"], "ok")

    def test_operator_cannot_manage_super_admin_service_account_credentials(self) -> None:
        _, operator_token = self._create_operator_user()
        operator_headers = {
            "Authorization": f"Bearer {operator_token}",
            "Content-Type": "application/json",
        }
        create_response = self.client.post(
            "/api/service-accounts",
            headers=operator_headers,
            json={
                "name": "forged-super-admin",
                "platform_roles": ["platform_super_admin"],
            },
        )
        self.assertEqual(create_response.status_code, 403, create_response.text)

        admin_create_response = self.client.post(
            "/api/service-accounts",
            headers=self._auth_headers(),
            json={
                "name": "protected-super-admin",
                "platform_roles": ["platform_super_admin"],
            },
        )
        self.assertEqual(admin_create_response.status_code, 200, admin_create_response.text)
        account_id = admin_create_response.json()["id"]

        token_response = self.client.post(
            f"/api/service-accounts/{account_id}/tokens",
            headers=operator_headers,
            json={"name": "forged-token"},
        )
        self.assertEqual(token_response.status_code, 403, token_response.text)

        demote_response = self.client.patch(
            f"/api/service-accounts/{account_id}",
            headers=operator_headers,
            json={"platform_roles": ["platform_viewer"]},
        )
        self.assertEqual(demote_response.status_code, 403, demote_response.text)


    @staticmethod
    def _run_async(coro):
        import asyncio

        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
