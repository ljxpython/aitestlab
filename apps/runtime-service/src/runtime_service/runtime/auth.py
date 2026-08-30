"""Verification of short-lived Runtime Delegation JWTs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import jwt

from runtime_service.runtime.contracts import RuntimePolicy, RuntimePrincipal
from runtime_service.runtime.errors import RuntimeAuthError, RuntimeResolutionError
from runtime_service.runtime.resolver import parse_runtime_policy, parse_runtime_principal

_REQUIRED_CLAIMS = (
    "type",
    "sub",
    "tenant_id",
    "project_id",
    "role",
    "permissions",
    "policy_version",
    "allowed_model_ids",
    "allowed_tool_names",
    "iat",
    "exp",
)
_ALLOWED_CLAIMS = frozenset(
    {
        *_REQUIRED_CLAIMS,
        "iss",
        "aud",
        "nbf",
        "jti",
        "policy_tenant_id",
        "policy_project_id",
    }
)


def _invalid(code: str = "runtime.auth.invalid_claim", field: str | None = None) -> RuntimeAuthError:
    return RuntimeAuthError(code, field)


def verify_delegation_token(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str | None = None,
    algorithms: Sequence[str] = ("HS256",),
) -> tuple[RuntimePrincipal, RuntimePolicy]:
    """Verify a Delegation JWT and return immutable Principal/Policy values."""

    if not isinstance(token, str) or not token.strip() or not isinstance(secret, str) or not secret:
        raise _invalid("runtime.auth.invalid_token")
    if not isinstance(issuer, str) or not issuer.strip():
        raise _invalid("runtime.auth.invalid_token", "issuer")
    if not algorithms or any(not isinstance(item, str) or not item for item in algorithms):
        raise _invalid("runtime.auth.invalid_token", "algorithms")

    options = {"require": list(_REQUIRED_CLAIMS), "verify_aud": audience is not None}
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=list(algorithms),
            issuer=issuer,
            audience=audience,
            options=options,
        )
    except jwt.InvalidTokenError as exc:
        raise _invalid("runtime.auth.invalid_token") from exc

    unknown = set(claims) - _ALLOWED_CLAIMS
    if unknown:
        raise _invalid(field=sorted(unknown)[0])
    if claims.get("type") != "runtime_delegation":
        raise _invalid(field="type")

    try:
        principal = parse_runtime_principal(
            {
                "user_id": claims["sub"],
                "tenant_id": claims["tenant_id"],
                "project_id": claims["project_id"],
                "role": claims["role"],
                "permissions": claims["permissions"],
            }
        )
        policy = parse_runtime_policy(
            {
                "version": claims["policy_version"],
                "allowed_model_ids": claims["allowed_model_ids"],
                "allowed_tool_names": claims["allowed_tool_names"],
            }
        )
    except RuntimeResolutionError as exc:
        raise _invalid("runtime.auth.invalid_claim", exc.field) from exc

    if claims.get("policy_tenant_id", principal.tenant_id) != principal.tenant_id:
        raise _invalid("runtime.auth.invalid_principal", "tenant_id")
    if claims.get("policy_project_id", principal.project_id) != principal.project_id:
        raise _invalid("runtime.auth.invalid_principal", "project_id")
    return principal, policy


__all__ = ["verify_delegation_token"]
