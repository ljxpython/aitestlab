from __future__ import annotations

import os
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, cast

import httpx
from langgraph_sdk import Auth

custom_auth = Auth()

_DEMO_USERS: dict[str, dict[str, Any]] = {
    "owner-token": {
        "identity": "owner_user",
        "display_name": "Owner User",
        "role": "user",
        "org_id": "demo-org",
        "permissions": [
            "threads:create",
            "threads:create_run",
            "threads:read",
            "threads:update",
            "threads:delete",
            "threads:search",
            "assistants:read",
            "assistants:search",
            "store:put",
            "store:get",
            "store:list_namespaces",
        ],
    },
    "viewer-token": {
        "identity": "viewer_user",
        "display_name": "Viewer User",
        "role": "viewer",
        "org_id": "demo-org",
        "permissions": [
            "threads:create_run",
            "threads:read",
            "threads:search",
            "assistants:read",
            "assistants:search",
            "store:get",
            "store:list_namespaces",
        ],
    },
    "admin-token": {
        "identity": "admin_user",
        "display_name": "Admin User",
        "role": "admin",
        "org_id": "demo-org",
        "permissions": ["*"],
    },
}

_DEMO_API_KEYS: dict[str, str] = {
    "owner-key": "owner-token",
    "viewer-key": "viewer-token",
    "admin-key": "admin-token",
}


def _normalize_header_name(name: Any) -> str:
    if isinstance(name, bytes):
        return name.decode("latin-1").strip().lower()
    return str(name).strip().lower()


def _normalize_header_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("latin-1").strip()
    return str(value).strip()


def _get_header(headers: Mapping[Any, Any], name: str) -> str | None:
    target = name.strip().lower()
    for key, value in headers.items():
        if _normalize_header_name(key) == target:
            text = _normalize_header_value(value)
            return text if text else None
    return None


def _extract_token(headers: Mapping[Any, Any]) -> str:
    authorization = _get_header(headers, "authorization")
    if authorization:
        prefix = "bearer "
        if authorization.lower().startswith(prefix):
            token = authorization[len(prefix) :].strip()
            if token:
                return token
        mapped = _DEMO_API_KEYS.get(authorization)
        if mapped:
            return mapped
        if authorization in _DEMO_USERS:
            return authorization

    api_key = _get_header(headers, "x-api-key")
    if api_key:
        mapped = _DEMO_API_KEYS.get(api_key)
        if mapped:
            return mapped
        if api_key in _DEMO_USERS:
            return api_key

    raise Auth.exceptions.HTTPException(
        status_code=401,
        detail="Missing or invalid auth token (use Bearer <token> or X-Api-Key: owner-key/viewer-key/admin-key)",
    )


def _resolve_user(token: str) -> Auth.types.MinimalUserDict:
    profile = _DEMO_USERS.get(token)
    if not profile:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Invalid credentials"
        )
    return cast(Auth.types.MinimalUserDict, deepcopy(profile))


def _user_to_mapping(
    user: Auth.types.BaseUser | Mapping[str, Any]
) -> Mapping[str, Any]:
    if isinstance(user, Mapping):
        return user
    return {
        "identity": getattr(user, "identity", ""),
        "permissions": list(getattr(user, "permissions", []) or []),
        "display_name": getattr(user, "display_name", ""),
        "is_authenticated": getattr(user, "is_authenticated", True),
        "role": getattr(user, "role", None) or "",
        "org_id": getattr(user, "org_id", None),
    }


def _is_admin(user: Mapping[str, Any]) -> bool:
    return str(user.get("role", "")).lower() == "admin"


def _has_permission(user: Mapping[str, Any], resource: str, action: str) -> bool:
    if _is_admin(user):
        return True
    permissions = {str(item).strip().lower() for item in user.get("permissions", [])}
    resource_key = resource.strip().lower()
    action_key = action.strip().lower()
    expected = {
        "*",
        f"{resource_key}:*",
        f"{resource_key}:{action_key}",
    }
    return bool(permissions.intersection(expected))


def ensure_permission(user: Mapping[str, Any], resource: str, action: str) -> None:
    if _has_permission(user, resource, action):
        return
    raise Auth.exceptions.HTTPException(
        status_code=403,
        detail=f"Forbidden: missing permission for {resource}:{action}",
    )


def ensure_assistant_write_allowed(user: Mapping[str, Any]) -> None:
    if _is_admin(user):
        return
    raise Auth.exceptions.HTTPException(
        status_code=403,
        detail="Forbidden: only admin can create/update/delete assistants",
    )


def ensure_store_namespace_allowed(
    user: Mapping[str, Any], namespace: tuple[str, ...]
) -> None:
    if _is_admin(user):
        return
    if not namespace:
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Forbidden: namespace is required"
        )
    if namespace[0] != str(user["identity"]):
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Forbidden: cross-user store namespace"
        )


def thread_owner_filter(user: Mapping[str, Any]) -> dict[str, Any]:
    if _is_admin(user):
        return {}
    return {"owner": str(user["identity"])}


def apply_thread_owner(
    value: Mapping[str, Any], user: Mapping[str, Any]
) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata
    metadata.update(thread_owner_filter(user))
    return payload


oauth_auth = Auth()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_TIMEOUT_SECONDS = float(os.environ.get("SUPABASE_TIMEOUT_SECONDS", "10"))

_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer": [
        "threads:create_run",
        "threads:read",
        "threads:search",
        "assistants:read",
        "assistants:search",
        "store:get",
        "store:list_namespaces",
    ],
    "user": [
        "threads:create",
        "threads:create_run",
        "threads:read",
        "threads:update",
        "threads:delete",
        "threads:search",
        "assistants:read",
        "assistants:search",
        "store:put",
        "store:get",
        "store:list_namespaces",
    ],
    "admin": ["*"],
}


def _extract_bearer_token(headers: Mapping[Any, Any]) -> str:
    authorization = _get_header(headers, "authorization")
    if authorization:
        prefix = "bearer "
        if authorization.lower().startswith(prefix):
            token = authorization[len(prefix) :].strip()
            if token:
                return token
    raise Auth.exceptions.HTTPException(
        status_code=401, detail="Missing or invalid bearer token"
    )


def _require_supabase_env() -> None:
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        return
    raise Auth.exceptions.HTTPException(
        status_code=401, detail="Supabase auth environment is not configured"
    )


async def _fetch_supabase_user(authorization: str) -> dict[str, Any]:
    _require_supabase_env()
    try:
        async with httpx.AsyncClient(timeout=SUPABASE_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": authorization,
                    "apiKey": SUPABASE_SERVICE_KEY,
                },
            )
    except httpx.HTTPError as exc:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail=f"Supabase request failed: {exc}"
        ) from exc

    if response.status_code != 200:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Supabase token validation failed"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Supabase user payload is invalid"
        )
    return payload


def _safe_role(payload: Mapping[str, Any]) -> str:
    app_metadata = payload.get("app_metadata")
    role: str | None = None
    if isinstance(app_metadata, Mapping):
        raw = app_metadata.get("role")
        if isinstance(raw, str):
            role = raw.strip().lower()
    if role in _ROLE_PERMISSIONS:
        return role
    return "viewer"


@oauth_auth.authenticate
async def oauth_authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    token = _extract_bearer_token(headers)
    authorization = f"Bearer {token}"
    user_payload = await _fetch_supabase_user(authorization)
    identity = str(user_payload.get("id", "")).strip()
    if not identity:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Supabase user id is missing"
        )

    role = _safe_role(user_payload)
    permissions = deepcopy(_ROLE_PERMISSIONS[role])
    app_metadata = user_payload.get("app_metadata")
    org_id = app_metadata.get("org_id") if isinstance(app_metadata, Mapping) else None

    profile: Auth.types.MinimalUserDict = cast(
        Auth.types.MinimalUserDict,
        {
            "identity": identity,
            "email": user_payload.get("email"),
            "display_name": user_payload.get("email") or identity,
            "is_authenticated": True,
            "role": role,
            "org_id": org_id,
            "permissions": permissions,
        },
    )
    return profile


@oauth_auth.on
async def oauth_on_access(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> dict:
    user = _user_to_mapping(ctx.user)
    if ctx.resource == "threads":
        ensure_permission(user, "threads", ctx.action)
        owner_filter = thread_owner_filter(user)
        if ctx.action == "create":
            try:
                metadata = value.setdefault("metadata", {})
            except Exception:  # noqa: BLE001
                metadata = None
            if isinstance(metadata, dict):
                metadata.update(owner_filter)
        return owner_filter

    if ctx.resource == "assistants":
        if ctx.action in {"create", "update", "delete"}:
            ensure_assistant_write_allowed(user)
            return {}
        ensure_permission(user, "assistants", ctx.action)
        return {}

    if ctx.resource == "store":
        ensure_permission(user, "store", ctx.action)
        if isinstance(value, Mapping):
            raw_namespace = value.get("namespace")
            if isinstance(raw_namespace, (list, tuple)):
                namespace = tuple(str(item) for item in raw_namespace)
                ensure_store_namespace_allowed(user, namespace)
                return {}
        if _is_admin(user):
            return {}
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Forbidden: store namespace is required"
        )

    ensure_permission(user, ctx.resource, ctx.action)
    return {}


@custom_auth.authenticate
async def authenticate(headers: dict) -> Auth.types.MinimalUserDict:
    token = _extract_token(headers)
    return _resolve_user(token)


@custom_auth.on
async def on_access(ctx: Auth.types.AuthContext, value: dict[str, Any]) -> dict:
    user = _user_to_mapping(ctx.user)
    if ctx.resource == "threads":
        ensure_permission(user, "threads", ctx.action)
        owner_filter = thread_owner_filter(user)
        if ctx.action == "create":
            try:
                metadata = value.setdefault("metadata", {})
            except Exception:  # noqa: BLE001
                metadata = None
            if isinstance(metadata, dict):
                metadata.update(owner_filter)
        return owner_filter

    if ctx.resource == "assistants":
        if ctx.action in {"create", "update", "delete"}:
            ensure_assistant_write_allowed(user)
            return {}
        ensure_permission(user, "assistants", ctx.action)
        return {}

    if ctx.resource == "store":
        ensure_permission(user, "store", ctx.action)
        if isinstance(value, Mapping):
            raw_namespace = value.get("namespace")
            if isinstance(raw_namespace, (list, tuple)):
                namespace = tuple(str(item) for item in raw_namespace)
                ensure_store_namespace_allowed(user, namespace)
                return {}
        if _is_admin(user):
            return {}
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Forbidden: store namespace is required"
        )

    ensure_permission(user, ctx.resource, ctx.action)
    return {}
