from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from fastapi import FastAPI, Request

from app.core.config import Settings
from app.core.context.models import (
    ActorContext,
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)
from app.core.runtime_contract import (
    normalize_protocol_v2_command,
    normalize_protocol_v2_event_request,
)
from app.core.security import create_runtime_delegation_token, empty_runtime_context_hash
from app.modules.runtime_gateway.presentation.http import get_runtime_gateway_service


class RuntimeDelegationTokenTest(unittest.TestCase):
    def test_signs_runtime_service_claim_contract(self) -> None:
        settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes",
            runtime_delegation_ttl_seconds=60,
        )

        token = create_runtime_delegation_token(
            subject="user-1",
            tenant_id="__default",
            project_id="project-1",
            role="project_editor",
            permissions=["project.runtime.write", "project.runtime.read"],
            policy_version="policy-1",
            allowed_model_ids=["model-1"],
            allowed_tool_names=["tool-1"],
            scope={"tenant_id": "__default", "project_id": "project-1"},
            context_hash=empty_runtime_context_hash(),
            settings=settings,
        )

        claims = jwt.decode(
            token,
            settings.runtime_delegation_secret,
            algorithms=["HS256"],
            issuer=settings.runtime_delegation_issuer,
            audience=settings.runtime_delegation_audience,
            options={
                "require": [
                    "sub",
                    "tenant_id",
                    "project_id",
                    "role",
                    "permissions",
                    "iss",
                    "aud",
                    "iat",
                    "nbf",
                    "exp",
                    "jti",
                    "type",
                    "policy_version",
                    "allowed_model_ids",
                    "allowed_tool_names",
                    "scope",
                    "context_hash",
                ]
            },
        )
        self.assertEqual(claims["sub"], "user-1")
        self.assertEqual(claims["tenant_id"], "__default")
        self.assertEqual(claims["project_id"], "project-1")
        self.assertEqual(claims["role"], "project_editor")
        self.assertEqual(
            claims["permissions"],
            ["project.runtime.read", "project.runtime.write"],
        )
        self.assertEqual(claims["type"], "runtime_delegation")
        self.assertEqual(claims["policy_version"], "policy-1")
        self.assertEqual(claims["allowed_model_ids"], ["model-1"])
        self.assertEqual(claims["allowed_tool_names"], ["tool-1"])
        self.assertEqual(
            claims["scope"],
            {"tenant_id": "__default", "project_id": "project-1"},
        )
        self.assertTrue(claims["context_hash"].startswith("sha256:"))
        self.assertEqual(jwt.get_unverified_header(token)["kid"], "runtime-delegation-v1")

    def test_rejects_unconfigured_secret(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 32 bytes"):
            create_runtime_delegation_token(
                subject="user-1",
                tenant_id="__default",
                project_id="project-1",
                role="project_editor",
                permissions=[],
                policy_version="policy-1",
                allowed_model_ids=["model-1"],
                allowed_tool_names=[],
                scope={"tenant_id": "__default", "project_id": "project-1"},
                context_hash=empty_runtime_context_hash(),
                settings=Settings(runtime_delegation_secret=""),
            )

    def test_operation_scope_is_restricted_to_read_or_run_create(self) -> None:
        settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes"
        )
        token = create_runtime_delegation_token(
            subject="user-1",
            tenant_id="__default",
            project_id="project-1",
            role="project_editor",
            permissions=["project.runtime.read"],
            policy_version="policy-1",
            allowed_model_ids=[],
            allowed_tool_names=[],
            scope={
                "tenant_id": "__default",
                "project_id": "project-1",
                "operation": "read",
            },
            settings=settings,
        )
        claims = jwt.decode(token, settings.runtime_delegation_secret, algorithms=["HS256"], options={"verify_signature": False})
        self.assertEqual(claims["scope"]["operation"], "read")
        with self.assertRaisesRegex(ValueError, "operation must be read or run-create"):
            create_runtime_delegation_token(
                subject="user-1",
                tenant_id="__default",
                project_id="project-1",
                role="project_editor",
                permissions=["project.runtime.read"],
                policy_version="policy-1",
                allowed_model_ids=[],
                allowed_tool_names=[],
                scope={
                    "tenant_id": "__default",
                    "project_id": "project-1",
                    "operation": "admin",
                },
                settings=settings,
            )

    def test_gateway_replaces_client_identity_headers_with_delegation(self) -> None:
        project_id = "project-1"
        app = FastAPI()
        app.state.settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes"
        )
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": f"/api/langgraph/threads/{project_id}/commands",
                "query_string": b"",
                "headers": [
                    (b"authorization", b"Bearer browser-token"),
                    (b"x-project-id", b"forged-project"),
                ],
                "app": app,
                "client": ("127.0.0.1", 1),
                "server": ("testserver", 80),
                "scheme": "http",
            }
        )
        request.state.request_id = "request-1"
        request.state.platform_context = PlatformRequestContext(
            request=RequestContext(
                request_id="request-1",
                trace_id="request-1",
                method="POST",
                path=request.url.path,
                started_at=0.0,
            ),
            tenant=TenantContext(tenant_id="__default"),
            project=ProjectContext(project_id=project_id),
            actor=ActorContext(),
        )
        actor = ActorContext(
            user_id="user-1",
            subject="subject-1",
            project_roles={project_id: ("project_editor",)},
        )

        with patch(
            "app.modules.runtime_gateway.presentation.http.LangGraphRuntimeGatewayUpstream",
            return_value=SimpleNamespace(),
        ) as upstream_factory, patch(
            "app.modules.runtime_gateway.presentation.http.RuntimePolicyOverlayService",
        ) as policy_factory:
            policy_factory.return_value.build_delegation_policy.return_value = {
                "version": "policy-1",
                "allowed_model_ids": ["model-1"],
                "allowed_tool_names": ["read_reference"],
                "runtime_permissions": ["runtime.tool.read"],
            }
            asyncio.run(get_runtime_gateway_service(request, actor))

        forwarded = upstream_factory.call_args.kwargs["forwarded_headers"]
        self.assertEqual(set(forwarded), {"authorization", "x-request-id"})
        self.assertNotIn("browser-token", forwarded["authorization"])
        token = forwarded["authorization"].removeprefix("Bearer ")
        claims = jwt.decode(
            token,
            app.state.settings.runtime_delegation_secret,
            algorithms=["HS256"],
            audience="runtime-service",
            issuer="platform-api",
        )
        self.assertEqual(claims["sub"], "user-1")
        self.assertEqual(claims["project_id"], project_id)
        self.assertEqual(claims["policy_version"], "policy-1")
        self.assertEqual(
            claims["permissions"],
            ["project.runtime.read", "project.runtime.write", "runtime.tool.read"],
        )


class ProtocolV2RuntimeNormalizationTest(unittest.TestCase):
    def test_moves_runtime_options_into_standard_config_namespace(self) -> None:
        normalized = normalize_protocol_v2_command(
            payload={
                "id": 7,
                "method": "run.start",
                "params": {
                    "assistant_id": "assistant-1",
                    "input": {"messages": []},
                    "config": {
                        "recursion_limit": 10,
                        "temperature": 0.2,
                        "configurable": {
                            "checkpoint_id": "checkpoint-1",
                            "tools": ["utc_now"],
                        },
                    },
                },
            },
            default_model_id="project-default",
        )

        self.assertEqual(
            normalized["params"]["config"],
            {
                "recursion_limit": 10,
                "configurable": {
                    "checkpoint_id": "checkpoint-1",
                    "platform_runtime": {
                        "model_id": "project-default",
                        "temperature": 0.2,
                        "tools": ["utc_now"],
                    },
                },
            },
        )
        self.assertNotIn("context", normalized["params"])

    def test_rejects_identity_in_platform_runtime(self) -> None:
        with self.assertRaisesRegex(ValueError, "trusted identity fields: project_id"):
            normalize_protocol_v2_command(
                payload={
                    "id": 8,
                    "method": "run.start",
                    "params": {
                        "assistant_id": "assistant-1",
                        "config": {
                            "configurable": {
                                "platform_runtime": {
                                    "project_id": "forged-project",
                                }
                            }
                        },
                    },
                }
            )

    def test_rejects_invalid_runtime_option_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "tools must be an array"):
            normalize_protocol_v2_command(
                payload={
                    "id": 10,
                    "method": "run.start",
                    "params": {
                        "assistant_id": "assistant-1",
                        "config": {
                            "configurable": {
                                "platform_runtime": {"tools": "utc_now"}
                            }
                        },
                    },
                }
            )

    def test_rejects_legacy_context_fields_before_upstream(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "Unsupported run.start context fields: system_prompt"
        ):
            normalize_protocol_v2_command(
                payload={
                    "id": 15,
                    "method": "run.start",
                    "params": {
                        "assistant_id": "assistant-1",
                        "context": {"system_prompt": "legacy"},
                    },
                }
            )

    def test_rejects_invalid_durable_run_parameters(self) -> None:
        base_params = {"assistant_id": "assistant-1", "input": {"messages": []}}

        with self.assertRaisesRegex(ValueError, "durability must be one of"):
            normalize_protocol_v2_command(
                payload={
                    "id": 11,
                    "method": "run.start",
                    "params": {**base_params, "durability": "eventual"},
                }
            )

        with self.assertRaisesRegex(ValueError, "durability must be one of"):
            normalize_protocol_v2_command(
                payload={
                    "id": 14,
                    "method": "run.start",
                    "params": {**base_params, "durability": {"mode": "sync"}},
                }
            )

        with self.assertRaisesRegex(ValueError, "stream_resumable must be a boolean"):
            normalize_protocol_v2_command(
                payload={
                    "id": 12,
                    "method": "run.start",
                    "params": {**base_params, "stream_resumable": "true"},
                }
            )

        with self.assertRaisesRegex(ValueError, "on_disconnect must be cancel or continue"):
            normalize_protocol_v2_command(
                payload={
                    "id": 13,
                    "method": "run.start",
                    "params": {**base_params, "on_disconnect": "pause"},
                }
            )

        with self.assertRaisesRegex(ValueError, "on_disconnect must be cancel or continue"):
            normalize_protocol_v2_command(
                payload={
                    "id": 15,
                    "method": "run.start",
                    "params": {**base_params, "on_disconnect": ["continue"]},
                }
            )

    def test_preserves_non_run_command_envelope(self) -> None:
        payload = {
            "id": 9,
            "method": "input.respond",
            "params": {"interrupt_id": "interrupt-1", "response": {"approve": True}},
        }
        self.assertEqual(normalize_protocol_v2_command(payload=payload), payload)

    def test_validates_event_replay_subscription(self) -> None:
        payload = {
            "channels": ["messages", "values", "tasks", "checkpoints"],
            "namespaces": [[], ["worker"]],
            "depth": 2,
            "since": 41,
        }
        self.assertEqual(normalize_protocol_v2_event_request(payload), payload)

        with self.assertRaisesRegex(ValueError, "since must be a non-negative integer"):
            normalize_protocol_v2_event_request(
                {"channels": ["messages"], "since": -1}
            )


if __name__ == "__main__":
    unittest.main()
