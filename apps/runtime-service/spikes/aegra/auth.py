"""Minimal auth fixture for the local compatibility spike."""

from __future__ import annotations

import os
from typing import Any

from langgraph_sdk import Auth


auth = Auth()


@auth.authenticate
async def authenticate(headers: dict[str, str]) -> dict[str, Any]:
    expected = os.getenv("AEGRA_SPIKE_AUTH_TOKEN", "aegra-spike-token")
    authorization = headers.get("authorization") or headers.get("Authorization")
    if authorization != f"Bearer {expected}":
        raise Auth.exceptions.HTTPException(status_code=401, detail="Invalid Spike token")
    return {"identity": "spike-user", "permissions": ["threads:*", "assistants:read"]}


@auth.on.threads
async def authorize_threads(*, ctx: Any, value: dict[str, Any]) -> None:
    context = value.get("context") or {}
    if not isinstance(context, dict):
        return
    identity = str(ctx.user.identity)
    for field in ("user_id", "tenant_id"):
        requested = context.get(field)
        if requested is not None and str(requested) != identity:
            raise Auth.exceptions.HTTPException(status_code=403, detail=f"Protected context override: {field}")
