from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.adapters.langgraph import (
    LangGraphRuntimeGatewayUpstream,
    build_forward_headers,
)
from app.core.context.models import ActorContext
from app.core.errors import BadRequestError
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.runtime_gateway.application.service import RuntimeGatewayService

router = APIRouter(prefix="/api/langgraph", tags=["runtime-gateway"])


def _normalize_ack(value: Any) -> Any:
    if value is None:
        return {"ok": True}
    if isinstance(value, dict) and not value:
        return {"ok": True}
    return value


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


def get_runtime_gateway_service(request: Request) -> RuntimeGatewayService:
    settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    upstream = LangGraphRuntimeGatewayUpstream(
        base_url=settings.langgraph_upstream_url,
        api_key=settings.langgraph_upstream_api_key,
        timeout_seconds=settings.langgraph_upstream_timeout_seconds,
        forwarded_headers=build_forward_headers(
            request.headers,
            request_id=getattr(request.state, "request_id", None),
        ),
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
