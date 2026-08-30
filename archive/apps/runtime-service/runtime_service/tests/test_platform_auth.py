from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from langgraph_sdk import Auth

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.auth.platform import (
    authenticate_runtime_delegation,
    authorize_platform_runtime,
)

_SECRET = "test-runtime-delegation-secret-at-least-32-bytes"
_PROJECT_ID = "3be6877b-738b-466d-ab86-d4f3ec2e75cb"


def _claims(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": "user-1",
        "tenant_id": "tenant-1",
        "project_id": _PROJECT_ID,
        "role": "project_editor",
        "permissions": ["runtime:write"],
        "iss": "platform-api",
        "aud": "runtime-service",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=2),
        "jti": "delegation-1",
        "type": "runtime_delegation",
    }
    claims.update(overrides)
    return claims


def _token(*, secret: str = _SECRET, **overrides: Any) -> str:
    return jwt.encode(_claims(**overrides), secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def _delegation_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", _SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "platform-api")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("PLATFORM_RUNTIME_MANAGEMENT_API_KEY", _SECRET)


def test_authenticate_runtime_delegation_returns_trusted_project_user() -> None:
    user = asyncio.run(authenticate_runtime_delegation(f"Bearer {_token()}"))

    assert user["identity"] == "user-1"
    assert user["project_id"] == _PROJECT_ID
    assert user["tenant_id"] == "tenant-1"
    assert user["permissions"] == ["runtime:write"]
    assert user["credential_type"] == "runtime_delegation"


def test_authenticate_management_api_key_for_non_thread_resources() -> None:
    user = asyncio.run(
        authenticate_runtime_delegation(
            None,
            {b"x-api-key": _SECRET.encode("utf-8")},
        )
    )
    assert user["identity"] == "platform-api"
    assert user["credential_type"] == "runtime_management"

    result = asyncio.run(
        authorize_platform_runtime(
            SimpleNamespace(resource="assistants", action="read", user=user),
            {},
        )
    )
    assert result == {}


def test_authenticate_management_api_key_missing_returns_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLATFORM_RUNTIME_MANAGEMENT_API_KEY", raising=False)

    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        asyncio.run(authenticate_runtime_delegation(None, {}))

    assert exc_info.value.status_code == 401


def test_management_api_key_cannot_access_threads() -> None:
    ctx = SimpleNamespace(
        resource="threads",
        action="search",
        user={"credential_type": "runtime_management"},
    )
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        asyncio.run(authorize_platform_runtime(ctx, {}))
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Basic token", "Bearer"],
)
def test_authenticate_runtime_delegation_rejects_missing_token(
    authorization: str | None,
) -> None:
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        asyncio.run(authenticate_runtime_delegation(authorization, {}))
    assert exc_info.value.status_code == 401


def test_authenticate_runtime_delegation_rejects_expired_token() -> None:
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        asyncio.run(
            authenticate_runtime_delegation(
                f"Bearer {_token(exp=datetime.now(UTC) - timedelta(seconds=1))}"
            )
        )
    assert exc_info.value.status_code == 401


def test_authenticate_runtime_delegation_rejects_invalid_signature() -> None:
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        asyncio.run(
            authenticate_runtime_delegation(
            f"Bearer {_token(secret='wrong-signing-secret-at-least-32-bytes')}"
            )
        )
    assert exc_info.value.status_code == 401


def test_authenticate_runtime_delegation_rejects_invalid_audience() -> None:
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        asyncio.run(
            authenticate_runtime_delegation(
                f"Bearer {_token(aud='another-service')}"
            )
        )
    assert exc_info.value.status_code == 401


def test_thread_create_rejects_project_mismatch() -> None:
    ctx = SimpleNamespace(
        resource="threads",
        action="create",
        user={
            "project_id": _PROJECT_ID,
            "credential_type": "runtime_delegation",
        },
    )
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        asyncio.run(
            authorize_platform_runtime(
                ctx,
                {"metadata": {"project_id": "different-project"}},
            )
        )
    assert exc_info.value.status_code == 403


def test_thread_scope_is_written_and_returned() -> None:
    ctx = SimpleNamespace(
        resource="threads",
        action="create",
        user={
            "project_id": _PROJECT_ID,
            "credential_type": "runtime_delegation",
        },
    )
    value: dict[str, Any] = {"metadata": {}}

    result = asyncio.run(authorize_platform_runtime(ctx, value))

    assert result == {"project_id": _PROJECT_ID}
    assert value["metadata"] == {"project_id": _PROJECT_ID}
