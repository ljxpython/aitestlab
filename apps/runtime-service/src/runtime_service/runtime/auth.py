"""Verification of short-lived Runtime Delegation JWTs."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import jwt

from runtime_service.runtime.contracts import RuntimePolicy, RuntimePrincipal
from runtime_service.runtime.errors import RuntimeAuthError, RuntimeResolutionError
from runtime_service.runtime.resolver import (
    parse_runtime_policy,
    parse_runtime_principal,
    runtime_context_hash,
)

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
    "scope",
    "context_hash",
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
        "scope",
        "context_hash",
        "request_id",
        "platform_trace_id",
    }
)

_SCOPE_FIELDS = frozenset({"tenant_id", "project_id", "assistant_id", "thread_id"})
_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class RuntimeScope:
    tenant_id: str
    project_id: str
    assistant_id: str | None = None
    thread_id: str | None = None


@dataclass(frozen=True, slots=True)
class VerifiedDelegation:
    principal: RuntimePrincipal
    policy: RuntimePolicy
    scope: RuntimeScope
    context_hash: str
    request_id: str | None = None
    platform_trace_id: str | None = None


def _invalid(code: str = "runtime.auth.invalid_claim", field: str | None = None) -> RuntimeAuthError:
    return RuntimeAuthError(code, field)


def _optional_correlation(claims: Mapping[str, Any], name: str) -> str | None:
    value = claims.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise _invalid("runtime.auth.invalid_claim", name)
    return value.strip()


def _parse_scope(raw: object) -> RuntimeScope:
    if not isinstance(raw, Mapping) or set(raw) - _SCOPE_FIELDS or "tenant_id" not in raw or "project_id" not in raw:
        raise _invalid("runtime.auth.invalid_principal", "scope")
    values: dict[str, str | None] = {}
    for field in _SCOPE_FIELDS:
        value = raw.get(field)
        if value is not None and (not isinstance(value, str) or not value or value != value.strip()):
            raise _invalid("runtime.auth.invalid_principal", field)
        values[field] = value
    return RuntimeScope(
        tenant_id=values["tenant_id"] or "",
        project_id=values["project_id"] or "",
        assistant_id=values["assistant_id"],
        thread_id=values["thread_id"],
    )


def verify_delegation_claims(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str | None = None,
    algorithms: Sequence[str] = ("HS256",),
    context: Mapping[str, Any] | object | None = None,
    expected_scope: Mapping[str, str | None] | None = None,
) -> VerifiedDelegation:
    """Verify a Delegation JWT and return immutable auth facts."""

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
        raise _invalid(field=min(unknown))
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
    scope = _parse_scope(claims["scope"])
    if scope.tenant_id != principal.tenant_id or scope.project_id != principal.project_id:
        raise _invalid("runtime.auth.invalid_principal", "scope")
    context_claim = claims["context_hash"]
    if not isinstance(context_claim, str) or not _HASH_PATTERN.fullmatch(context_claim):
        raise _invalid("runtime.auth.invalid_claim", "context_hash")
    if context is not None and runtime_context_hash(context) != context_claim:
        raise _invalid("runtime.auth.context_hash_mismatch", "context_hash")
    if expected_scope is not None:
        actual = {
            "tenant_id": scope.tenant_id,
            "project_id": scope.project_id,
            "assistant_id": scope.assistant_id,
            "thread_id": scope.thread_id,
        }
        if any(actual.get(key) != value for key, value in expected_scope.items()):
            raise _invalid("runtime.auth.invalid_principal", "scope")
    return VerifiedDelegation(
        principal,
        policy,
        scope,
        context_claim,
        _optional_correlation(claims, "request_id"),
        _optional_correlation(claims, "platform_trace_id"),
    )


def verify_delegation_token(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str | None = None,
    algorithms: Sequence[str] = ("HS256",),
    context: Mapping[str, Any] | object | None = None,
    expected_scope: Mapping[str, str | None] | None = None,
) -> tuple[RuntimePrincipal, RuntimePolicy]:
    """Verify a Delegation JWT and return immutable Principal/Policy values."""

    verified = verify_delegation_claims(
        token,
        secret=secret,
        issuer=issuer,
        audience=audience,
        algorithms=algorithms,
        context=context,
        expected_scope=expected_scope,
    )
    return verified.principal, verified.policy


def _user_value(user: object, key: str) -> object:
    if isinstance(user, Mapping):
        return user.get(key)
    try:
        return user[key]  # type: ignore[index]
    except (KeyError, TypeError, AttributeError):
        return getattr(user, key, None)


def verified_delegation_from_user(user: object) -> VerifiedDelegation:
    """Parse the non-secret facts placed on a LangGraph authenticated user."""

    raw_principal = _user_value(user, "runtime_principal")
    raw_policy = _user_value(user, "runtime_policy")
    raw_scope = _user_value(user, "runtime_scope")
    context_claim = _user_value(user, "runtime_context_hash")
    if not isinstance(raw_principal, Mapping) or not isinstance(raw_policy, Mapping):
        raise _invalid("runtime.auth.invalid_principal")
    try:
        principal = parse_runtime_principal(raw_principal)
        policy = parse_runtime_policy(raw_policy)
    except RuntimeResolutionError as exc:
        raise _invalid("runtime.auth.invalid_claim", exc.field) from exc
    scope = _parse_scope(raw_scope)
    if scope.tenant_id != principal.tenant_id or scope.project_id != principal.project_id:
        raise _invalid("runtime.auth.invalid_principal", "scope")
    if not isinstance(context_claim, str) or not _HASH_PATTERN.fullmatch(context_claim):
        raise _invalid("runtime.auth.invalid_claim", "context_hash")
    request_id = _user_value(user, "request_id")
    platform_trace_id = _user_value(user, "platform_trace_id")
    for name, value in (("request_id", request_id), ("platform_trace_id", platform_trace_id)):
        if value is not None and (
            not isinstance(value, str) or not value.strip() or len(value) > 256
        ):
            raise _invalid("runtime.auth.invalid_claim", name)
    return VerifiedDelegation(
        principal,
        policy,
        scope,
        context_claim,
        request_id.strip() if isinstance(request_id, str) else None,
        platform_trace_id.strip() if isinstance(platform_trace_id, str) else None,
    )


__all__ = [
    "RuntimeScope",
    "VerifiedDelegation",
    "verified_delegation_from_user",
    "verify_delegation_claims",
    "verify_delegation_token",
]
