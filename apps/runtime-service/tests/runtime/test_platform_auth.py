from __future__ import annotations

import asyncio
import time

import jwt
import pytest
from langgraph_sdk import Auth

from runtime_service.auth.platform import authenticate
from runtime_service.runtime.resolver import runtime_context_hash

SECRET = "r1-test-secret-with-at-least-32-bytes"


def _token(*, request_id: str | None = None, platform_trace_id: str | None = None) -> str:
    now = int(time.time())
    claims = {
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
    }
    if request_id is not None:
        claims["request_id"] = request_id
    if platform_trace_id is not None:
        claims["platform_trace_id"] = platform_trace_id
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_platform_auth_returns_runtime_facts_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    user = asyncio.run(authenticate(authorization=f"Bearer {_token()}"))

    assert user["identity"] == "user-a"
    assert user["tenant_id"] == "tenant-a"
    assert user["project_id"] == "project-a"
    assert user["role"] == "developer"
    assert user["policy_version"] == "policy-1"
    assert user["allowed_model_ids"] == ["deepseek:deepseek-chat"]
    assert user["allowed_tool_names"] == ["read_reference"]
    assert user["runtime_principal"]["tenant_id"] == "tenant-a"
    assert user["runtime_policy"]["version"] == "policy-1"
    assert user["runtime_context_hash"].startswith("sha256:")
    assert "Bearer" not in str(user)


def test_platform_auth_rejects_missing_or_invalid_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    with pytest.raises(Auth.exceptions.HTTPException) as missing:
        asyncio.run(authenticate(authorization=None))
    assert missing.value.status_code == 401

    with pytest.raises(Auth.exceptions.HTTPException) as invalid:
        asyncio.run(authenticate(authorization="Bearer invalid"))
    assert invalid.value.status_code == 401


def test_platform_auth_preserves_signed_trace_correlation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")

    user = asyncio.run(
        authenticate(
            authorization=(
                "Bearer "
                + _token(request_id="request-1", platform_trace_id="platform-trace-1")
            )
        )
    )

    assert user["request_id"] == "request-1"
    assert user["platform_trace_id"] == "platform-trace-1"


def test_platform_auth_requires_audience_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.delenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", raising=False)

    with pytest.raises(Auth.exceptions.HTTPException) as error:
        asyncio.run(authenticate(authorization=f"Bearer {_token()}"))

    assert error.value.status_code == 500
