from __future__ import annotations

import time
import uuid
from contextvars import ContextVar, Token

from fastapi import Request

from app.core.context.models import (
    ActorContext,
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)

_REQUEST_CONTEXT: ContextVar[PlatformRequestContext | None] = ContextVar(
    "platform_api_request_context",
    default=None,
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _request_id(request: Request) -> str:
    incoming = _clean(request.headers.get("x-request-id"))
    return incoming or uuid.uuid4().hex


def _trace_id(request: Request, request_id: str) -> str:
    incoming = _clean(request.headers.get("x-trace-id"))
    return incoming or request_id


def build_request_context(request: Request) -> PlatformRequestContext:
    request_id = _request_id(request)
    trace_id = _trace_id(request, request_id)
    started_at = time.perf_counter()
    tenant_id = _clean(request.headers.get("x-tenant-id"))
    project_id = _clean(request.headers.get("x-project-id"))
    return PlatformRequestContext(
        request=RequestContext(
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            query=request.url.query or None,
            started_at=started_at,
            client_ip=request.client.host if request.client else None,
            user_agent=_clean(request.headers.get("user-agent")),
        ),
        tenant=TenantContext(tenant_id=tenant_id),
        project=ProjectContext(
            project_id=project_id,
            requested_by_header=project_id is not None,
        ),
        actor=ActorContext(),
    )


def set_current_request_context(
    context: PlatformRequestContext,
) -> Token[PlatformRequestContext | None]:
    return _REQUEST_CONTEXT.set(context)


def replace_current_request_context(context: PlatformRequestContext) -> None:
    _REQUEST_CONTEXT.set(context)


def reset_current_request_context(token: Token[PlatformRequestContext | None]) -> None:
    _REQUEST_CONTEXT.reset(token)


def get_current_request_context() -> PlatformRequestContext:
    context = _REQUEST_CONTEXT.get()
    if context is None:
        raise RuntimeError("request_context_not_bound")
    return context
