from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.adapters.langgraph import (
    LangGraphRuntimeGatewayUpstream,
)
from app.core.context.models import ActorContext
from app.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotAuthenticatedError,
    ServiceUnavailableError,
)
from app.core.security import create_runtime_delegation_token, empty_runtime_context_hash
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.runtime_gateway.application.service import RuntimeGatewayService
from app.modules.runtime_policies.application import RuntimePolicyOverlayService

router = APIRouter(prefix="/api/langgraph", tags=["runtime-gateway"])

_SENSITIVE_EVENT_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "cookie",
    "id_token",
    "password",
    "refresh_token",
    "secret",
    "token",
}


def _normalize_ack(value: Any) -> Any:
    if value is None:
        return {"ok": True}
    if isinstance(value, dict) and not value:
        return {"ok": True}
    return value


def _redact_event_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact_event_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: "[REDACTED]"
        if key.lower().replace("-", "_") in _SENSITIVE_EVENT_KEYS
        else _redact_event_value(item)
        for key, item in value.items()
    }


def _redact_sse_frame(frame: bytes) -> bytes:
    try:
        lines = frame.decode("utf-8").split("\n")
    except UnicodeDecodeError:
        return frame
    data_positions = [index for index, line in enumerate(lines) if line.startswith("data:")]
    if not data_positions:
        return frame
    data = "\n".join(lines[index][5:].lstrip() for index in data_positions)
    try:
        payload = json.loads(data)
    except ValueError:
        return frame
    encoded = json.dumps(_redact_event_value(payload), ensure_ascii=False, separators=(",", ":"))
    first_data_position = data_positions[0]
    redacted_lines = [
        f"data: {encoded}" if index == first_data_position else line
        for index, line in enumerate(lines)
        if index not in data_positions[1:]
    ]
    return "\n".join(redacted_lines).encode("utf-8")


async def _redact_protocol_event_stream(stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    buffer = b""
    async for chunk in stream:
        buffer += chunk.replace(b"\r\n", b"\n")
        frames = buffer.split(b"\n\n")
        buffer = frames.pop()
        for frame in frames:
            yield _redact_sse_frame(frame) + b"\n\n"
    if buffer:
        yield _redact_sse_frame(buffer)


def _require_project_id(request: Request) -> str:
    project_id = getattr(request.state.platform_context.project, "project_id", None)
    normalized = project_id.strip() if isinstance(project_id, str) else ""
    if not normalized:
        raise BadRequestError(
            code="project_id_required",
            message="x-project-id header is required",
        )
    request.state.audit_project_id = normalized
    return normalized


async def get_runtime_gateway_service(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> RuntimeGatewayService:
    settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    project_id = _require_project_id(request)
    context = request.state.platform_context
    subject = actor.user_id or actor.subject
    if not subject:
        raise NotAuthenticatedError()
    project_roles = actor.project_role_set(project_id)
    if not project_roles:
        raise ForbiddenError(
            code="project_role_missing",
            message="Project role missing",
        )
    try:
        policy = RuntimePolicyOverlayService(
            session_factory=session_factory,
            runtime_base_url=settings.langgraph_upstream_url,
        ).build_delegation_policy(project_id=project_id)
        delegation = create_runtime_delegation_token(
            subject=subject,
            tenant_id=context.tenant.tenant_id or "__default",
            project_id=project_id,
            role=project_roles[0],
            permissions=["project.runtime.read", "project.runtime.write"],
            policy_version=str(policy["version"]),
            allowed_model_ids=policy["allowed_model_ids"],
            allowed_tool_names=policy["allowed_tool_names"],
            scope={
                "tenant_id": context.tenant.tenant_id or "__default",
                "project_id": project_id,
            },
            context_hash=empty_runtime_context_hash(),
            settings=settings,
        )
    except ValueError as exc:
        raise ServiceUnavailableError(
            code="runtime_delegation_not_configured",
            message="Runtime delegation is not configured",
        ) from exc

    forwarded_headers = {"authorization": f"Bearer {delegation}"}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        forwarded_headers["x-request-id"] = request_id
    upstream = LangGraphRuntimeGatewayUpstream(
        base_url=settings.langgraph_upstream_url,
        api_key=settings.langgraph_upstream_api_key,
        timeout_seconds=settings.langgraph_upstream_timeout_seconds,
        forwarded_headers=forwarded_headers,
    )
    return RuntimeGatewayService(
        session_factory=session_factory,
        upstream=upstream,
        runtime_base_url=settings.langgraph_upstream_url,
    )


@router.get("/info")
async def get_runtime_info(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.get_info(actor=actor, project_id=project_id)


@router.post("/graphs/search")
async def search_graphs(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.search_graphs(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/graphs/count")
async def count_graphs(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.count_graphs(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/threads")
async def create_thread(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.create_thread(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/threads/search")
async def search_threads(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.search_threads(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/threads/count")
async def count_threads(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.count_threads(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/threads/prune")
async def prune_threads(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    result = await service.prune_threads(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )
    return _normalize_ack(result)


@router.get("/threads/{thread_id}")
async def get_thread(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.get_thread(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
    )


@router.patch("/threads/{thread_id}")
async def update_thread(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.update_thread(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )


@router.delete("/threads/{thread_id}")
async def delete_thread(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    result = await service.delete_thread(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
    )
    return _normalize_ack(result)


@router.post("/threads/{thread_id}/copy")
async def copy_thread(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    result = await service.copy_thread(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
    )
    return _normalize_ack(result)


@router.get("/threads/{thread_id}/state")
async def get_thread_state(
    request: Request,
    thread_id: str,
    subgraphs: bool | None = Query(default=None),
    checkpoint_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    params: dict[str, Any] = {}
    if subgraphs is not None:
        params["subgraphs"] = subgraphs
    if checkpoint_id is not None:
        params["checkpoint_id"] = checkpoint_id
    project_id = _require_project_id(request)
    return await service.get_thread_state(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        params=params,
    )


@router.post("/threads/{thread_id}/state")
async def update_thread_state(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.update_thread_state(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )


@router.get("/threads/{thread_id}/state/{checkpoint_id}")
async def get_thread_state_at_checkpoint(
    request: Request,
    thread_id: str,
    checkpoint_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.get_thread_state_at_checkpoint(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        checkpoint_id=checkpoint_id,
    )


@router.post("/threads/{thread_id}/history")
async def get_thread_history(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.get_thread_history(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )


@router.get("/threads/{thread_id}/history")
async def get_thread_history_alias(
    request: Request,
    thread_id: str,
    limit: int | None = Query(default=None),
    before: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    payload: dict[str, Any] = {}
    if limit is not None:
        payload["limit"] = limit
    if before is not None:
        payload["before"] = before
    project_id = _require_project_id(request)
    return await service.get_thread_history(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )


@router.post("/runs")
async def create_run(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.create_global_run(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/runs/stream")
async def stream_run(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    project_id = _require_project_id(request)
    stream = await service.stream_global_run(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )
    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/runs/wait")
async def wait_run(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.wait_global_run(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/runs/batch")
async def create_batch_runs(
    request: Request,
    payload: Any = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    if isinstance(payload, list):
        payloads = payload
    elif isinstance(payload, dict) and isinstance(payload.get("payloads"), list):
        payloads = payload["payloads"]
    else:
        raise BadRequestError(
            code="invalid_batch_payload",
            message="payload must be array or contain payloads array",
        )
    if any(not isinstance(item, dict) for item in payloads):
        raise BadRequestError(
            code="invalid_batch_payload_item",
            message="each batch payload must be an object",
        )

    project_id = _require_project_id(request)
    return await service.create_batch_runs(
        actor=actor,
        project_id=project_id,
        payloads=payloads,
    )


@router.post("/runs/cancel")
async def cancel_runs(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    result = await service.cancel_runs(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )
    return _normalize_ack(result)


@router.post("/runs/crons")
async def create_cron(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.create_cron(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/runs/crons/search")
async def search_crons(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.search_crons(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.post("/runs/crons/count")
async def count_crons(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.count_crons(
        actor=actor,
        project_id=project_id,
        payload=payload,
    )


@router.patch("/runs/crons/{cron_id}")
async def update_cron(
    request: Request,
    cron_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.update_cron(
        actor=actor,
        project_id=project_id,
        cron_id=cron_id,
        payload=payload,
    )


@router.delete("/runs/crons/{cron_id}")
async def delete_cron(
    request: Request,
    cron_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    result = await service.delete_cron(
        actor=actor,
        project_id=project_id,
        cron_id=cron_id,
    )
    return _normalize_ack(result)


@router.post("/threads/{thread_id}/runs")
async def create_thread_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.create_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )


@router.post("/threads/{thread_id}/runs/stream")
async def stream_thread_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    project_id = _require_project_id(request)
    stream = await service.stream_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )
    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/threads/{thread_id}/commands")
async def send_thread_command(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.send_thread_command(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )


@router.post("/threads/{thread_id}/stream/events")
async def stream_thread_events(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    project_id = _require_project_id(request)
    stream = await service.stream_thread_events(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )
    return StreamingResponse(_redact_protocol_event_stream(stream), media_type="text/event-stream")


@router.post("/threads/{thread_id}/runs/wait")
async def wait_thread_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.wait_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )


@router.get("/threads/{thread_id}/runs/{run_id}")
async def get_thread_run(
    request: Request,
    thread_id: str,
    run_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.get_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        run_id=run_id,
    )


@router.get("/threads/{thread_id}/runs")
async def list_thread_runs(
    request: Request,
    thread_id: str,
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
    status: str | None = Query(default=None),
    select: list[str] | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if status is not None:
        params["status"] = status
    if select is not None:
        params["select"] = select
    project_id = _require_project_id(request)
    return await service.list_thread_runs(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        params=params,
    )


@router.delete("/threads/{thread_id}/runs/{run_id}")
async def delete_thread_run(
    request: Request,
    thread_id: str,
    run_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    result = await service.delete_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        run_id=run_id,
    )
    return _normalize_ack(result)


@router.get("/threads/{thread_id}/runs/{run_id}/join")
async def join_thread_run(
    request: Request,
    thread_id: str,
    run_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.join_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        run_id=run_id,
    )


@router.get("/threads/{thread_id}/runs/{run_id}/stream")
async def join_thread_run_stream(
    request: Request,
    thread_id: str,
    run_id: str,
    cancel_on_disconnect: bool | None = Query(default=None),
    stream_mode: str | None = Query(default=None),
    last_event_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    params: dict[str, Any] = {}
    if cancel_on_disconnect is not None:
        params["cancel_on_disconnect"] = cancel_on_disconnect
    if stream_mode is not None:
        params["stream_mode"] = stream_mode
    if last_event_id is not None:
        params["last_event_id"] = last_event_id
    project_id = _require_project_id(request)
    stream = await service.join_thread_run_stream(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        run_id=run_id,
        params=params,
    )
    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/threads/{thread_id}/runs/crons")
async def create_thread_run_cron(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return await service.create_thread_run_cron(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_thread_run(
    request: Request,
    thread_id: str,
    run_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    result = await service.cancel_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        run_id=run_id,
        payload=payload,
    )
    return _normalize_ack(result)
