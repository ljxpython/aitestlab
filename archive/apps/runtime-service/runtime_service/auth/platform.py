from __future__ import annotations

import hmac
import os
from collections.abc import Mapping, Sequence
from typing import Any, cast

import jwt
from langgraph_sdk import Auth

platform_auth = Auth()

_ALGORITHM = "HS256"
_CREDENTIAL_TYPE = "runtime_delegation"
_DEFAULT_ISSUER = "platform-api"
_DEFAULT_AUDIENCE = "runtime-service"
_REQUIRED_CLAIMS = (
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
)
_THREAD_ACTIONS = {"create", "create_run", "read", "search", "update", "delete"}


def _http_error(status_code: int, detail: str) -> Auth.exceptions.HTTPException:
    return Auth.exceptions.HTTPException(status_code=status_code, detail=detail)


def _decode_credential(token: str) -> dict[str, Any]:
    secret = os.environ.get("PLATFORM_RUNTIME_DELEGATION_SECRET", "").strip()
    if len(secret.encode("utf-8")) < 32:
        raise _http_error(503, "Runtime delegation verifier is not configured")

    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            issuer=os.environ.get(
                "PLATFORM_RUNTIME_DELEGATION_ISSUER", _DEFAULT_ISSUER
            ),
            audience=os.environ.get(
                "PLATFORM_RUNTIME_DELEGATION_AUDIENCE", _DEFAULT_AUDIENCE
            ),
            options={"require": list(_REQUIRED_CLAIMS)},
        )
    except jwt.PyJWTError as exc:
        raise _http_error(401, "Invalid runtime delegation credential") from exc

    permissions = claims.get("permissions")
    if claims.get("type") != _CREDENTIAL_TYPE:
        raise _http_error(401, "Invalid runtime delegation credential type")
    if not isinstance(permissions, Sequence) or isinstance(permissions, (str, bytes)):
        raise _http_error(401, "Invalid runtime delegation permissions")

    for key in ("sub", "tenant_id", "project_id", "role", "jti"):
        if not isinstance(claims.get(key), str) or not claims[key].strip():
            raise _http_error(401, f"Invalid runtime delegation claim: {key}")
    return claims


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise _http_error(401, "Missing runtime delegation credential")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise _http_error(401, "Missing runtime delegation credential")
    return token.strip()


def _header_value(headers: Mapping[bytes, bytes] | None, key: bytes) -> str:
    if not headers:
        return ""
    value = headers.get(key, b"")
    return value.decode("utf-8").strip() if isinstance(value, bytes) else ""


def _user_value(user: Any, key: str) -> Any:
    if isinstance(user, Mapping):
        return user.get(key)
    try:
        return user[key]
    except (KeyError, TypeError):
        return getattr(user, key, None)


@platform_auth.authenticate
async def authenticate_runtime_delegation(
    authorization: str | None,
    headers: Mapping[bytes, bytes] | None = None,
) -> Auth.types.MinimalUserDict:
    if not authorization:
        expected = os.environ.get("PLATFORM_RUNTIME_MANAGEMENT_API_KEY", "").strip()
        provided = _header_value(headers, b"x-api-key")
        if len(expected.encode("utf-8")) < 32:
            # LangGraph custom auth maps 401/403 exceptions to HTTP responses;
            # other statuses escape the auth middleware and become HTTP 500.
            raise _http_error(401, "Runtime management authentication is not configured")
        if not provided or not hmac.compare_digest(provided, expected):
            raise _http_error(401, "Invalid runtime management credential")
        return cast(
            Auth.types.MinimalUserDict,
            {
                "identity": "platform-api",
                "display_name": "platform-api",
                "is_authenticated": True,
                "tenant_id": "__default",
                "role": "platform_service",
                "permissions": ["runtime:manage"],
                "credential_type": "runtime_management",
            },
        )

    claims = _decode_credential(_extract_bearer(authorization))
    return cast(
        Auth.types.MinimalUserDict,
        {
            "identity": claims["sub"],
            "display_name": claims["sub"],
            "is_authenticated": True,
            "tenant_id": claims["tenant_id"],
            "project_id": claims["project_id"],
            "role": claims["role"],
            "permissions": list(claims["permissions"]),
            "delegation_id": claims["jti"],
            "credential_type": "runtime_delegation",
        },
    )


@platform_auth.on
async def authorize_platform_runtime(
    ctx: Auth.types.AuthContext,
    value: dict[str, Any],
) -> dict[str, str]:
    if ctx.resource != "threads":
        return {}
    if ctx.action not in _THREAD_ACTIONS:
        raise _http_error(403, "Runtime credential does not allow this operation")
    if _user_value(ctx.user, "credential_type") != "runtime_delegation":
        raise _http_error(403, "Runtime management credential cannot access threads")

    project_id = str(_user_value(ctx.user, "project_id") or "").strip()
    if not project_id:
        raise _http_error(403, "Runtime delegation project is missing")

    project_filter = {"project_id": project_id}
    if ctx.action == "create":
        metadata = value.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            raise _http_error(400, "Thread metadata must be an object")
        requested_project = str(metadata.get("project_id") or "").strip()
        if requested_project and requested_project != project_id:
            raise _http_error(403, "Thread project does not match delegation")
        metadata.update(project_filter)
    return project_filter


__all__ = [
    "authenticate_runtime_delegation",
    "authorize_platform_runtime",
    "platform_auth",
]
