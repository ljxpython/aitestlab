from __future__ import annotations

import time

import jwt
import pytest

from runtime_service.runtime.auth import verify_delegation_token
from runtime_service.runtime.errors import RuntimeAuthError

SECRET = "r1-test-secret-with-at-least-32-bytes"


def _token(**overrides: object) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "type": "runtime_delegation",
        "sub": "user-a",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "role": "developer",
        "permissions": ["runtime.read"],
        "policy_version": "policy-1",
        "allowed_model_ids": ["deepseek:deepseek-chat"],
        "allowed_tool_names": ["search"],
        "iat": now,
        "exp": now + 60,
        "iss": "runtime-test",
        "aud": "runtime-service",
    }
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _verify(token: str, *, secret: str = SECRET) -> tuple[object, object]:
    return verify_delegation_token(
        token,
        secret=secret,
        issuer="runtime-test",
        audience="runtime-service",
    )


def test_valid_delegation_token_maps_principal_and_policy() -> None:
    principal, policy = _verify(_token())
    assert principal.user_id == "user-a"
    assert principal.tenant_id == "tenant-a"
    assert policy.version == "policy-1"
    assert policy.allowed_model_ids == ("deepseek:deepseek-chat",)


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"type": "other"}, "runtime.auth.invalid_claim"),
        ({"policy_tenant_id": "tenant-b"}, "runtime.auth.invalid_principal"),
        ({"allowed_model_ids": []}, "runtime.auth.invalid_claim"),
    ],
)
def test_invalid_claims_fail_closed(overrides: dict[str, object], expected: str) -> None:
    with pytest.raises(RuntimeAuthError) as error:
        _verify(_token(**overrides))
    assert error.value.code == expected


def test_bad_signature_and_expiry_are_not_retried_or_leaked() -> None:
    with pytest.raises(RuntimeAuthError) as signature:
        _verify(_token(), secret="wrong-secret-with-at-least-32-bytes")
    assert signature.value.code == "runtime.auth.invalid_token"
    assert "wrong-secret" not in str(signature.value)

    now = int(time.time())
    with pytest.raises(RuntimeAuthError) as expired:
        _verify(_token(iat=now - 120, exp=now - 1))
    assert expired.value.code == "runtime.auth.invalid_token"


def test_unknown_claim_is_rejected() -> None:
    with pytest.raises(RuntimeAuthError) as error:
        _verify(_token(unexpected="value"))
    assert error.value.code == "runtime.auth.invalid_claim"
