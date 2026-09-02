"""LangGraph Agent Server authentication adapter for Runtime Delegation JWTs."""

from __future__ import annotations

import os

from langgraph_sdk import Auth

from runtime_service.runtime.auth import verify_delegation_claims
from runtime_service.runtime.errors import RuntimeAuthError

auth = Auth()


def _setting(name: str, *, required: bool = True) -> str:
    value = os.getenv(name, "")
    if required and not value:
        raise Auth.exceptions.HTTPException(status_code=500, detail="Runtime auth is misconfigured")
    return value


def _bearer_token(authorization: str | None) -> str:
    if not isinstance(authorization, str):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Unauthorized")
    scheme, separator, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise Auth.exceptions.HTTPException(status_code=401, detail="Unauthorized")
    return token.strip()


@auth.authenticate
async def authenticate(authorization: str | None = None) -> Auth.types.MinimalUserDict:
    """Validate the request token and expose only non-secret Runtime auth facts."""

    try:
        verified = verify_delegation_claims(
            _bearer_token(authorization),
            secret=_setting("PLATFORM_RUNTIME_DELEGATION_SECRET"),
            issuer=_setting("PLATFORM_RUNTIME_DELEGATION_ISSUER"),
            audience=_setting("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", required=False) or None,
        )
    except Auth.exceptions.HTTPException:
        raise
    except (RuntimeAuthError, ValueError) as exc:
        raise Auth.exceptions.HTTPException(status_code=401, detail="Unauthorized") from exc

    principal = verified.principal
    policy = verified.policy
    return {
        "identity": principal.user_id,
        "is_authenticated": True,
        "tenant_id": principal.tenant_id,
        "project_id": principal.project_id,
        "role": principal.role,
        "permissions": list(principal.permissions),
        "policy_version": policy.version,
        "allowed_model_ids": list(policy.allowed_model_ids),
        "allowed_tool_names": list(policy.allowed_tool_names),
        "runtime_principal": {
            "user_id": principal.user_id,
            "tenant_id": principal.tenant_id,
            "project_id": principal.project_id,
            "role": principal.role,
            "permissions": list(principal.permissions),
        },
        "runtime_policy": {
            "version": policy.version,
            "allowed_model_ids": list(policy.allowed_model_ids),
            "allowed_tool_names": list(policy.allowed_tool_names),
        },
        "runtime_scope": {
            "tenant_id": verified.scope.tenant_id,
            "project_id": verified.scope.project_id,
            "assistant_id": verified.scope.assistant_id,
            "thread_id": verified.scope.thread_id,
        },
        "runtime_context_hash": verified.context_hash,
        "request_id": verified.request_id,
        "platform_trace_id": verified.platform_trace_id,
    }


__all__ = ["auth", "authenticate"]
