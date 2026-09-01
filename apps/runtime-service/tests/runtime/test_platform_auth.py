from __future__ import annotations

import asyncio
import time

import jwt
import pytest
from langgraph_sdk import Auth

from runtime_service.auth.platform import authenticate
from runtime_service.runtime.resolver import runtime_context_hash


SECRET = "r1-test-secret-with-at-least-32-bytes"


def _token() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "type": "runtime_delegation",
            "sub": "user-a",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "role": "developer",
            "permissions": ["runtime.tool.read"],
            "policy_version": "policy-1",
            "allowed_model_ids": ["deepseek:deepseek-chat"],
            "allowed_tool_names": ["read_reference"],
            "iat": now,
            "exp": now + 60,
            "iss": "runtime-test",
            "aud": "runtime-service",
            "scope": {"tenant_id": "tenant-a", "project_id": "project-a"},
            "context_hash": runtime_context_hash(None),
        },
        SECRET,
        algorithm="HS256",
    )


def test_platform_auth_returns_runtime_facts_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    user = asyncio.run(authenticate(authorization=f"Bearer {_token()}"))

    assert user["identity"] == "user-a"
    assert user["runtime_principal"]["tenant_id"] == "tenant-a"
    assert user["runtime_policy"]["version"] == "policy-1"
    assert user["runtime_context_hash"].startswith("sha256:")
    assert "Bearer" not in str(user)


def test_platform_auth_rejects_missing_or_invalid_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    with pytest.raises(Auth.exceptions.HTTPException) as missing:
        asyncio.run(authenticate(authorization=None))
    assert missing.value.status_code == 401

    with pytest.raises(Auth.exceptions.HTTPException) as invalid:
        asyncio.run(authenticate(authorization="Bearer invalid"))
    assert invalid.value.status_code == 401
