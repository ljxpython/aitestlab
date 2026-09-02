from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt
from langgraph_sdk import get_client

from runtime_service.runtime.resolver import runtime_context_hash


def _local_token(
    *,
    tenant_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    permissions: list[str] | None = None,
    allowed_model_ids: list[str] | None = None,
    allowed_tool_names: list[str] | None = None,
) -> str:
    now = datetime.now(UTC)
    tenant_id = tenant_id or os.getenv("R6_TEST_TENANT", "r6-smoke-tenant")
    project_id = project_id or os.getenv("R6_TEST_PROJECT", "r6-smoke-project")
    return jwt.encode(
        {
            "type": "runtime_delegation",
            "sub": user_id or os.getenv("R6_TEST_USER", "r6-smoke-user"),
            "tenant_id": tenant_id,
            "project_id": project_id,
            "role": "developer",
            "permissions": permissions or ["runtime.tool.read"],
            "policy_version": "r6-smoke-v1",
            "allowed_model_ids": allowed_model_ids or ["deepseek:DeepSeek-V4-Flash"],
            "allowed_tool_names": allowed_tool_names or ["read_reference"],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "iss": os.getenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "platform-api"),
            "aud": os.getenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service"),
            "scope": {"tenant_id": tenant_id, "project_id": project_id},
            "context_hash": runtime_context_hash(None),
        },
        os.getenv(
            "R6_TEST_TOKEN_SECRET",
            os.getenv(
                "PLATFORM_RUNTIME_DELEGATION_SECRET",
                "r6-local-only-secret-at-least-32-bytes",
            ),
        ),
        algorithm="HS256",
    )


def get_authenticated_client(
    base_url: str,
    *,
    tenant_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    permissions: list[str] | None = None,
    allowed_model_ids: list[str] | None = None,
    allowed_tool_names: list[str] | None = None,
):
    token = _local_token(
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=user_id,
        permissions=permissions,
        allowed_model_ids=allowed_model_ids,
        allowed_tool_names=allowed_tool_names,
    )
    return get_client(
        url=base_url,
        headers={"Authorization": f"Bearer {token}"},
    )
