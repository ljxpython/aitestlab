from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext, PlatformRequestContext
from app.core.normalization import clean_str
from app.modules.audit.application import AuditHttpRequest, WriteHttpAuditCommand, write_http_audit_event
from app.modules.audit.domain import AuditResult

logger = logging.getLogger(__name__)

_SKIP_PATHS = {"/docs", "/openapi.json", "/redoc", "/favicon.ico"}
_MAX_CAPTURE_BYTES = 64 * 1024

def _parse_json_bytes(value: bytes | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_context(request: Request) -> PlatformRequestContext | None:
    context = getattr(request.state, "platform_context", None)
    if isinstance(context, PlatformRequestContext):
        return context
    return None


def _resolve_response_payload(request: Request) -> dict[str, Any] | None:
    payload = getattr(request.state, "audit_response_payload", None)
    if isinstance(payload, dict):
        return payload
    return None


def _should_capture_response(response: Response) -> bool:
    content_type = clean_str(response.headers.get("content-type")) or clean_str(response.media_type)
    if content_type is None or not content_type.lower().startswith("application/json"):
        return False
    if response.headers.get("content-disposition"):
        return False
    try:
        content_length = int(response.headers["content-length"])
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= content_length <= _MAX_CAPTURE_BYTES


def _write_audit_event(
    *,
    request: Request,
    session_factory: sessionmaker[Session],
    status_code: int,
    result: AuditResult,
    duration_ms: int,
) -> None:
    context = _resolve_context(request)
    response_payload = _resolve_response_payload(request)
    audit_actor = getattr(request.state, "audit_actor", None)
    actor = audit_actor if isinstance(audit_actor, ActorContext) else (context.actor if context is not None else None)
    tenant_id = context.tenant.tenant_id if context is not None else None
    write_http_audit_event(
        session_factory=session_factory,
        command=WriteHttpAuditCommand(
            request_id=getattr(request.state, "request_id", "") or "unknown",
            request=AuditHttpRequest(
                method=request.method.upper(),
                path=request.url.path,
                query_params=dict(request.query_params),
                query_string=request.url.query or None,
                state_project_id=getattr(request.state, "audit_project_id", None),
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent") or None,
                response_content_length=getattr(request.state, "response_content_length", None),
                metadata=getattr(request.state, "audit_metadata", None),
                action_override=getattr(request.state, "audit_action", None),
            ),
            actor_user_id=actor.user_id if actor is not None else None,
            actor_subject=actor.subject if actor is not None else None,
            tenant_id=tenant_id,
            fallback_project_id=(context.project.project_id if context is not None else None),
            response_payload=response_payload,
            status_code=status_code,
            result=result,
            duration_ms=duration_ms,
        ),
    )


def register_audit_log_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def audit_log_middleware(request: Request, call_next):
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        started_at = time.perf_counter()
        session_factory = getattr(request.app.state, "db_session_factory", None)
        if session_factory is None or not isinstance(session_factory, sessionmaker):
            return await call_next(request)

        try:
            response = await call_next(request)
        except asyncio.CancelledError:
            duration_ms = max(0, int(round((time.perf_counter() - started_at) * 1000)))
            try:
                _write_audit_event(
                    request=request,
                    session_factory=session_factory,
                    status_code=499,
                    result=AuditResult.CANCELLED,
                    duration_ms=duration_ms,
                )
            except Exception:
                logger.exception(
                    "audit_write_failed request_id=%s",
                    getattr(request.state, "request_id", "unknown"),
                )
            raise
        except Exception:
            duration_ms = max(0, int(round((time.perf_counter() - started_at) * 1000)))
            try:
                _write_audit_event(
                    request=request,
                    session_factory=session_factory,
                    status_code=500,
                    result=AuditResult.FAILED,
                    duration_ms=duration_ms,
                )
            except Exception:
                logger.exception(
                    "audit_write_failed request_id=%s",
                    getattr(request.state, "request_id", "unknown"),
                )
            raise

        capture_payload = _should_capture_response(response)
        request.state.response_content_length = response.headers.get("content-length")
        request.state.audit_response_payload = None
        body_iterator = response.body_iterator

        async def audited_body_iterator() -> AsyncIterator[bytes]:
            chunks: list[bytes] = []
            captured_bytes = 0
            result = AuditResult.SUCCESS if response.status_code < 400 else AuditResult.FAILED
            status_code = response.status_code
            try:
                async for chunk in body_iterator:
                    if capture_payload and captured_bytes <= _MAX_CAPTURE_BYTES:
                        encoded = chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk)
                        captured_bytes += len(encoded)
                        if captured_bytes <= _MAX_CAPTURE_BYTES:
                            chunks.append(encoded)
                        else:
                            chunks.clear()
                    yield chunk
            except asyncio.CancelledError:
                result = AuditResult.CANCELLED
                status_code = 499
                raise
            except Exception:
                result = AuditResult.FAILED
                status_code = 500
                raise
            finally:
                if chunks:
                    request.state.audit_response_payload = _parse_json_bytes(b"".join(chunks))
                duration_ms = max(0, int(round((time.perf_counter() - started_at) * 1000)))
                try:
                    _write_audit_event(
                        request=request,
                        session_factory=session_factory,
                        status_code=status_code,
                        result=result,
                        duration_ms=duration_ms,
                    )
                except Exception:
                    logger.exception(
                        "audit_write_failed request_id=%s",
                        getattr(request.state, "request_id", "unknown"),
                    )

        response.body_iterator = audited_body_iterator()
        return response
