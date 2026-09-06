from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import jwt
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.adapters.langgraph.runtime_client import LangGraphRuntimeClient
from app.core.config import Settings
from app.core.context.models import ActorContext
from app.core.db import build_engine, create_core_tables
from app.core.errors import BadRequestError, NotAuthenticatedError, ServiceUnavailableError
from app.modules.runtime_catalog.infra.sqlalchemy.repository import (
    SqlAlchemyRuntimeCatalogRepository,
)
from app.modules.runtime_catalog.application.service import (
    RuntimeCatalogService,
)
from app.modules.runtime_catalog.application.credentials import (
    ModelCredentialError,
    decrypt_api_key,
    encrypt_api_key,
)
from app.modules.runtime_catalog.domain import RuntimeModelCreate


class RuntimeCatalogDelegationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.project_id = "project-1"
        self.settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes",
            model_config_master_key=Fernet.generate_key().decode(),
        )
        self.actor = ActorContext(
            user_id="user-1",
            project_roles={self.project_id: ("project_editor",)},
        )

    def _service(self, *, upstream: object | None = None) -> RuntimeCatalogService:
        return RuntimeCatalogService(
            session_factory=None,
            upstream=upstream or SimpleNamespace(),
            runtime_base_url="http://runtime.test",
            settings=self.settings,
            tenant_id="tenant-1",
        )

    def test_runtime_headers_use_project_delegation(self) -> None:
        service = self._service()
        with patch(
            "app.modules.runtime_catalog.application.service.RuntimePolicyOverlayService"
        ) as policy_factory:
            policy_factory.return_value.build_delegation_policy.return_value = {
                "version": "policy-1",
                "allowed_model_ids": ["model-1"],
                "allowed_tool_names": [],
                "runtime_permissions": [],
            }
            headers = service._runtime_headers(actor=self.actor, project_id=self.project_id)

        token = headers["authorization"].removeprefix("Bearer ")
        claims = jwt.decode(
            token,
            self.settings.runtime_delegation_secret,
            algorithms=["HS256"],
            audience=self.settings.runtime_delegation_audience,
            issuer=self.settings.runtime_delegation_issuer,
        )
        self.assertEqual(claims["sub"], "user-1")
        self.assertEqual(claims["project_id"], self.project_id)
        self.assertEqual(claims["scope"], {"tenant_id": "tenant-1", "project_id": self.project_id})

    def test_runtime_headers_include_permissions_for_allowed_runtime_tool(self) -> None:
        service = self._service()
        with patch(
            "app.modules.runtime_catalog.application.service.RuntimePolicyOverlayService"
        ) as policy_factory:
            policy_factory.return_value.build_delegation_policy.return_value = {
                "version": "policy-1",
                "allowed_model_ids": ["model-1"],
                "allowed_tool_names": ["read_reference"],
                "runtime_permissions": ["runtime.tool.read"],
            }
            headers = service._runtime_headers(actor=self.actor, project_id=self.project_id)

        token = headers["authorization"].removeprefix("Bearer ")
        claims = jwt.decode(
            token,
            self.settings.runtime_delegation_secret,
            algorithms=["HS256"],
            audience=self.settings.runtime_delegation_audience,
            issuer=self.settings.runtime_delegation_issuer,
        )
        self.assertEqual(
            claims["permissions"],
            ["project.runtime.read", "project.runtime.write", "runtime.tool.read"],
        )

    def test_runtime_headers_reject_missing_subject(self) -> None:
        with self.assertRaises(NotAuthenticatedError):
            self._service()._runtime_headers(actor=ActorContext(), project_id=self.project_id)

    async def test_refresh_passes_delegation_to_upstream(self) -> None:
        upstream = SimpleNamespace(require_json=AsyncMock(return_value={}))
        service = self._service(upstream=upstream)
        service._prepare_project_scope = AsyncMock()  # type: ignore[method-assign]
        service._require_refresh_access = Mock()  # type: ignore[method-assign]
        service._runtime_headers = Mock(return_value={"authorization": "Bearer delegation"})  # type: ignore[method-assign]

        with self.assertRaises(ServiceUnavailableError):
            await service.refresh_models(actor=self.actor, project_id=self.project_id)

        upstream.require_json.assert_awaited_once_with(
            "GET",
            "/internal/capabilities/models",
            forwarded_headers={"authorization": "Bearer delegation"},
        )

    def test_model_credential_round_trip_is_not_returned(self) -> None:
        secret = "provider-secret"
        ciphertext = encrypt_api_key(secret, master_key=self.settings.model_config_master_key)
        self.assertNotEqual(ciphertext, secret)
        self.assertEqual(decrypt_api_key(ciphertext, master_key=self.settings.model_config_master_key), secret)

    def test_model_credential_decryption_fails_closed(self) -> None:
        with self.assertRaises(ModelCredentialError):
            decrypt_api_key("not-a-fernet-token", master_key=self.settings.model_config_master_key)
        with self.assertRaises(ModelCredentialError):
            decrypt_api_key(
                encrypt_api_key("provider-secret", master_key=self.settings.model_config_master_key),
                master_key=Fernet.generate_key().decode(),
            )

    def test_model_validation_rejects_invalid_url_and_protocol(self) -> None:
        with self.assertRaises(BadRequestError):
            RuntimeCatalogService._validated_model_values(
                RuntimeModelCreate(
                    provider="openai",
                    display_name="demo",
                    base_url="file:///tmp/key",
                    protocol="openai",
                    model="gpt-test",
                    api_key="secret",
                ),
                partial=False,
            )

    def test_model_item_exposes_only_credential_status(self) -> None:
        item = self._service()._model_item(
            SimpleNamespace(
                id="model-id",
                runtime_id="runtime",
                model_key="gpt-test",
                display_name="Demo",
                is_default_runtime=False,
                sync_status="ready",
                last_seen_at=None,
                last_synced_at=None,
                provider="openai",
                base_url="https://example.com",
                protocol="openai",
                model_name="gpt-test",
                api_key_ciphertext="ciphertext",
                enabled=True,
            )
        )
        self.assertTrue(item.credential_configured)
        self.assertNotIn("api_key", item.model_dump())
        with self.assertRaises(BadRequestError):
            RuntimeCatalogService._validated_model_values(
                RuntimeModelCreate(
                    provider="openai",
                    display_name="demo",
                    base_url="https://example.com",
                    protocol="unknown",
                    model="gpt-test",
                    api_key="secret",
                ),
                partial=False,
            )

    def test_configured_model_is_encrypted_and_can_be_disabled(self) -> None:
        engine = build_engine("sqlite+pysqlite:///:memory:")
        create_core_tables(engine)
        try:
            with Session(engine) as session:
                repository = SqlAlchemyRuntimeCatalogRepository(session)
                ciphertext = encrypt_api_key(
                    "provider-secret",
                    master_key=self.settings.model_config_master_key,
                )
                created = repository.create_configured_model(
                    runtime_id="runtime",
                    values={
                        "provider": "openai",
                        "display_name": "Demo",
                        "base_url": "https://example.com",
                        "protocol": "openai",
                        "model": "gpt-test",
                        "api_key_ciphertext": ciphertext,
                        "enabled": True,
                    },
                )
                updated = repository.update_configured_model(
                    created.id,
                    values={
                        "model_key": "gpt-next",
                        "model_name": "gpt-next",
                        "enabled": False,
                    },
                )
                session.commit()

            assert updated is not None
            self.assertEqual(updated.model_key, "gpt-next")
            self.assertFalse(updated.enabled)
            self.assertEqual(
                decrypt_api_key(
                    updated.api_key_ciphertext,
                    master_key=self.settings.model_config_master_key,
                ),
                "provider-secret",
            )
        finally:
            engine.dispose()


class LangGraphRuntimeClientHeadersTest(unittest.TestCase):
    def test_request_headers_override_default_forwarded_headers(self) -> None:
        client = LangGraphRuntimeClient(
            base_url="http://runtime.test",
            timeout_seconds=1.0,
            forwarded_headers={"authorization": "Bearer browser-token", "x-request-id": "request-1"},
        )

        headers = client._headers(
            accept="application/json",
            forwarded_headers={"authorization": "Bearer delegation"},
        )

        self.assertEqual(headers["authorization"], "Bearer delegation")
        self.assertEqual(headers["x-request-id"], "request-1")
        self.assertEqual(headers["accept"], "application/json")


if __name__ == "__main__":
    unittest.main()
