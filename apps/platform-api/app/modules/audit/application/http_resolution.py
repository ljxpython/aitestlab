from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.core.normalization import clean_str
from app.modules.audit.domain import AuditPlane, AuditResult


def _route_segments(path: str) -> list[str]:
    return [segment for segment in path.strip("/").split("/") if segment]


def _response_size(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _nested_value(payload: dict[str, Any] | None, *keys: str) -> str | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return clean_str(current)


@dataclass(frozen=True, slots=True)
class AuditHttpRequest:
    method: str
    path: str
    query_params: Mapping[str, str]
    query_string: str | None
    state_project_id: str | None
    client_ip: str | None
    user_agent: str | None
    response_content_length: str | None
    metadata: Mapping[str, Any] | None = None
    action_override: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedHttpAudit:
    plane: AuditPlane
    action: str
    target_type: str | None
    target_id: str | None
    project_id: str | None
    metadata: dict[str, Any]


def _resolve_plane(path: str) -> AuditPlane:
    if path.startswith("/_system/"):
        return AuditPlane.SYSTEM_INTERNAL
    if path.startswith("/_runtime/"):
        return AuditPlane.RUNTIME_GATEWAY
    if path == "/api/langgraph" or path.startswith("/api/langgraph/"):
        return AuditPlane.RUNTIME_GATEWAY
    return AuditPlane.CONTROL_PLANE


def _resolve_project_id(request: AuditHttpRequest) -> str | None:
    state_project_id = clean_str(request.state_project_id)
    if state_project_id:
        return state_project_id
    query_project_id = clean_str(request.query_params.get("project_id"))
    path_segments = _route_segments(request.path)
    if len(path_segments) >= 3 and path_segments[:2] == ["api", "projects"]:
        return clean_str(path_segments[2])
    return query_project_id


def _resolve_action(
    *,
    request: AuditHttpRequest,
) -> tuple[str, str | None, str | None]:
    path = request.path
    method = request.method
    segments = _route_segments(path)
    action_override = clean_str(request.action_override)
    if action_override in {
        "user.profile.updated",
        "user.status.updated",
        "user.roles.updated",
        "user.credentials.reset",
        "user.governance.updated",
    } and len(segments) == 3 and segments[:2] == ["api", "users"] and method == "PATCH":
        return action_override, "user", clean_str(segments[2])
    if segments == ["_system", "health"] and method == "GET":
        return "system.health.read", "system", "health"
    if segments == ["_system", "probes", "live"] and method == "GET":
        return "system.probe.live", "system", "live"
    if segments == ["_system", "probes", "ready"] and method == "GET":
        return "system.probe.ready", "system", "ready"
    if segments == ["_system", "metrics"] and method == "GET":
        return "system.metrics.read", "system", "metrics"

    if len(segments) >= 2 and segments[:2] == ["api", "identity"]:
        if segments[2:] == ["session"] and method == "POST":
            return "identity.session.created", "session", None
        if segments[2:] == ["session", "refresh"] and method == "POST":
            return "identity.session.refreshed", "session", None
        if segments[2:] == ["session"] and method == "DELETE":
            return "identity.session.deleted", "session", None
        if segments[2:] == ["me"] and method == "GET":
            return "identity.profile.read", "user", None
        if segments[2:] == ["password", "change"] and method == "POST":
            return "identity.password.changed", "user", None

    if len(segments) >= 2 and segments[:2] == ["api", "users"]:
        if len(segments) == 2 and method == "GET":
            return "user.collection.listed", "user", None
        if len(segments) == 2 and method == "POST":
            return "user.item.created", "user", None
        if len(segments) == 3 and method == "GET":
            return "user.item.read", "user", clean_str(segments[2])
        if len(segments) == 3 and method == "PATCH":
            return "user.item.updated", "user", clean_str(segments[2])
        if len(segments) == 5 and segments[3:] == ["credentials", "reset"] and method == "POST":
            return "user.credentials.reset", "user", clean_str(segments[2])

    if len(segments) >= 2 and segments[:2] == ["api", "projects"]:
        if len(segments) == 2 and method == "GET":
            return "project.collection.listed", "project", None
        if len(segments) == 2 and method == "POST":
            return "project.project.created", "project", None
        if len(segments) == 3 and method == "DELETE":
            return "project.project.deleted", "project", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "access" and method == "GET":
            return "project.access.read", "project", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "takeover" and method == "POST":
            return "project.takeover.completed", "project", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "admin-recovery" and method == "POST":
            return "project.admin.recovered", "project", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "archive" and method == "POST":
            return "project.project.archived", "project", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "restore" and method == "POST":
            return "project.project.restored", "project", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "member-candidates" and method == "GET":
            return "project.member.candidates.listed", "project", clean_str(segments[2])
        if len(segments) >= 4 and segments[3] == "members":
            project_id = clean_str(segments[2])
            if len(segments) == 4 and method == "GET":
                return "project.member.listed", "project_member", project_id
            if len(segments) == 5 and method == "PUT":
                return "project.member.upserted", "project_member", clean_str(segments[4])
            if len(segments) == 5 and method == "DELETE":
                return "project.member.removed", "project_member", clean_str(segments[4])

    if len(segments) >= 2 and segments[:2] == ["api", "announcements"]:
        if len(segments) == 2 and method == "GET":
            return "announcement.collection.listed", "announcement", None
        if len(segments) == 2 and method == "POST":
            return "announcement.item.created", "announcement", None
        if len(segments) == 3 and segments[2] == "feed" and method == "GET":
            return "announcement.feed.read", "announcement_feed", _resolve_project_id(request)
        if len(segments) == 3 and segments[2] == "read-all" and method == "POST":
            return "announcement.feed.read_all_marked", "announcement_feed", _resolve_project_id(
                request
            )
        if len(segments) == 3 and method == "PATCH":
            return "announcement.item.updated", "announcement", clean_str(segments[2])
        if len(segments) == 3 and method == "DELETE":
            return "announcement.item.deleted", "announcement", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "read" and method == "POST":
            return "announcement.item.read_marked", "announcement", clean_str(segments[2])

    if segments == ["api", "audit"] and method == "GET":
        return "audit.collection.listed", "audit_event", None

    if segments == ["_system", "platform-config"] and method == "GET":
        return "system.config.read", "platform_config", "platform-config"
    if segments == ["_system", "platform-config", "feature-flags"] and method == "PATCH":
        return "system.config.feature_flags.updated", "platform_config", "platform-config"

    if len(segments) >= 2 and segments[:2] == ["api", "operations"]:
        if len(segments) == 2 and method == "POST":
            return "operation.item.submitted", "operation", None
        if len(segments) == 2 and method == "GET":
            return "operation.collection.listed", "operation", _resolve_project_id(request)
        if len(segments) == 3 and segments[2] == "stream" and method == "GET":
            return "operation.collection.stream_opened", "operation", _resolve_project_id(request)
        if len(segments) == 4 and segments[2] == "artifacts" and segments[3] == "cleanup" and method == "POST":
            return "operation.artifact.collection.cleaned", "operation_artifact", None
        if len(segments) == 4 and segments[2] == "bulk" and segments[3] == "cancel" and method == "POST":
            return "operation.collection.cancelled", "operation", _resolve_project_id(request)
        if len(segments) == 4 and segments[2] == "bulk" and segments[3] == "archive" and method == "POST":
            return "operation.collection.archived", "operation", _resolve_project_id(request)
        if len(segments) == 4 and segments[2] == "bulk" and segments[3] == "restore" and method == "POST":
            return "operation.collection.restored", "operation", _resolve_project_id(request)
        if len(segments) == 3 and method == "GET":
            return "operation.item.read", "operation", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "artifact" and method == "GET":
            return "operation.item.artifact_read", "operation_artifact", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "cancel" and method == "POST":
            return "operation.item.cancelled", "operation", clean_str(segments[2])

    if len(segments) >= 2 and segments[:2] == ["api", "service-accounts"]:
        if len(segments) == 2 and method == "GET":
            return "service_account.collection.listed", "service_account", None
        if len(segments) == 2 and method == "POST":
            return "service_account.item.created", "service_account", None
        if len(segments) == 3 and method == "PATCH":
            return "service_account.item.updated", "service_account", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "tokens" and method == "POST":
            return "service_account.token.created", "service_account_token", clean_str(segments[2])
        if len(segments) == 5 and segments[3] == "tokens" and method == "DELETE":
            return "service_account.token.revoked", "service_account_token", clean_str(segments[4])
        if len(segments) == 4 and segments[3] == "project-grants" and method == "GET":
            return "service_account.project_grant.listed", "service_account", clean_str(segments[2])
        if len(segments) == 5 and segments[3] == "project-grants" and method == "PUT":
            return "service_account.project_grant.upserted", "project", clean_str(segments[4])
        if len(segments) == 5 and segments[3] == "project-grants" and method == "DELETE":
            return "service_account.project_grant.removed", "project", clean_str(segments[4])

    if len(segments) >= 2 and segments[:2] == ["api", "assistants"]:
        if len(segments) == 3 and method == "GET":
            return "assistant.item.read", "assistant", clean_str(segments[2])
        if len(segments) == 3 and method == "PATCH":
            return "assistant.item.updated", "assistant", clean_str(segments[2])
        if len(segments) == 3 and method == "DELETE":
            return "assistant.item.deleted", "assistant", clean_str(segments[2])
        if len(segments) == 4 and segments[3] == "resync" and method == "POST":
            return "assistant.item.resynced", "assistant", clean_str(segments[2])

    if len(segments) >= 4 and segments[:2] == ["api", "projects"]:
        if len(segments) == 4 and segments[3] == "assistants" and method == "GET":
            return "assistant.collection.listed", "assistant", None
        if len(segments) == 4 and segments[3] == "assistants" and method == "POST":
            return "assistant.item.created", "assistant", None

    if len(segments) >= 4 and segments[:2] == ["api", "graphs"] and segments[3] == "assistant-parameter-schema":
        if method == "GET":
            return "assistant.schema.read", "graph", clean_str(segments[2])

    if len(segments) >= 2 and segments[:2] == ["api", "runtime"]:
        if segments[2:] == ["models"] and method == "GET":
            return "runtime.model.collection.listed", "runtime_model", _resolve_project_id(request)
        if segments[2:] == ["models", "refresh"] and method == "POST":
            return "runtime.model.collection.refreshed", "runtime_model", _resolve_project_id(request)
        if segments[2:] == ["tools"] and method == "GET":
            return "runtime.tool.collection.listed", "runtime_tool", _resolve_project_id(request)
        if segments[2:] == ["tools", "refresh"] and method == "POST":
            return "runtime.tool.collection.refreshed", "runtime_tool", _resolve_project_id(request)
        if segments[2:] == ["graphs"] and method == "GET":
            return "runtime.graph.collection.listed", "runtime_graph", _resolve_project_id(request)
        if segments[2:] == ["graphs", "refresh"] and method == "POST":
            return "runtime.graph.collection.refreshed", "runtime_graph", _resolve_project_id(request)

    if len(segments) >= 5 and segments[:2] == ["api", "projects"] and segments[3] == "runtime-policies":
        project_id = clean_str(segments[2])
        if len(segments) == 5 and segments[4] == "models" and method == "GET":
            return "runtime.policy.model.listed", "runtime_policy_model", project_id
        if len(segments) == 5 and segments[4] == "tools" and method == "GET":
            return "runtime.policy.tool.listed", "runtime_policy_tool", project_id
        if len(segments) == 5 and segments[4] == "graphs" and method == "GET":
            return "runtime.policy.graph.listed", "runtime_policy_graph", project_id
        if len(segments) == 6 and segments[4] == "models" and method == "PUT":
            return "runtime.policy.model.updated", "runtime_policy_model", clean_str(segments[5])
        if len(segments) == 6 and segments[4] == "tools" and method == "PUT":
            return "runtime.policy.tool.updated", "runtime_policy_tool", clean_str(segments[5])
        if len(segments) == 6 and segments[4] == "graphs" and method == "PUT":
            return "runtime.policy.graph.updated", "runtime_policy_graph", clean_str(segments[5])

    if len(segments) >= 2 and segments[:2] == ["api", "langgraph"]:
        if segments[2:] == ["info"] and method == "GET":
            return "runtime.info.read", "runtime", "info"
        if segments[2:] == ["graphs", "search"] and method == "POST":
            return "runtime.graph.collection.searched", "graph", None
        if segments[2:] == ["graphs", "count"] and method == "POST":
            return "runtime.graph.collection.counted", "graph", None
        if segments[2:] == ["threads"] and method == "POST":
            return "runtime.thread.item.created", "thread", None
        if segments[2:] == ["threads", "search"] and method == "POST":
            return "runtime.thread.collection.searched", "thread", None
        if segments[2:] == ["threads", "count"] and method == "POST":
            return "runtime.thread.collection.counted", "thread", None
        if segments[2:] == ["threads", "prune"] and method == "POST":
            return "runtime.thread.collection.pruned", "thread", None
        if len(segments) == 4 and segments[2] == "threads" and method == "GET":
            return "runtime.thread.item.read", "thread", clean_str(segments[3])
        if len(segments) == 4 and segments[2] == "threads" and method == "PATCH":
            return "runtime.thread.item.updated", "thread", clean_str(segments[3])
        if len(segments) == 4 and segments[2] == "threads" and method == "DELETE":
            return "runtime.thread.item.deleted", "thread", clean_str(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "copy" and method == "POST":
            return "runtime.thread.item.copied", "thread", clean_str(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "state" and method == "GET":
            return "runtime.thread.state.read", "thread", clean_str(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "state" and method == "POST":
            return "runtime.thread.state.updated", "thread", clean_str(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "state" and method == "GET":
            return "runtime.thread.state.read", "thread", clean_str(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "history" and method in {"GET", "POST"}:
            return "runtime.thread.history.read", "thread", clean_str(segments[3])
        if segments[2:] == ["runs"] and method == "POST":
            return "runtime.run.item.created", "run", None
        if segments[2:] == ["runs", "stream"] and method == "POST":
            return "runtime.run.stream.opened", "run", None
        if segments[2:] == ["runs", "wait"] and method == "POST":
            return "runtime.run.wait.requested", "run", None
        if segments[2:] == ["runs", "batch"] and method == "POST":
            return "runtime.run.collection.created", "run", None
        if segments[2:] == ["runs", "cancel"] and method == "POST":
            return "runtime.run.collection.cancelled", "run", None
        if segments[2:] == ["runs", "crons"] and method == "POST":
            return "runtime.cron.item.created", "cron", None
        if segments[2:] == ["runs", "crons", "search"] and method == "POST":
            return "runtime.cron.collection.searched", "cron", None
        if segments[2:] == ["runs", "crons", "count"] and method == "POST":
            return "runtime.cron.collection.counted", "cron", None
        if len(segments) == 5 and segments[2] == "runs" and segments[3] == "crons" and method == "PATCH":
            return "runtime.cron.item.updated", "cron", clean_str(segments[4])
        if len(segments) == 5 and segments[2] == "runs" and segments[3] == "crons" and method == "DELETE":
            return "runtime.cron.item.deleted", "cron", clean_str(segments[4])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "runs" and method == "POST":
            return "runtime.run.item.created", "thread", clean_str(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "commands" and method == "POST":
            return "runtime.command.submitted", "thread", clean_str(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4:6] == ["stream", "events"] and method == "POST":
            return "runtime.event_stream.opened", "thread", clean_str(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and segments[5] == "stream" and method == "POST":
            return "runtime.run.stream.opened", "thread", clean_str(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and segments[5] == "wait" and method == "POST":
            return "runtime.run.wait.requested", "thread", clean_str(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "runs" and method == "GET":
            return "runtime.run.collection.listed", "thread", clean_str(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and method == "GET":
            return "runtime.run.item.read", "run", clean_str(segments[5])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and method == "DELETE":
            return "runtime.run.item.deleted", "run", clean_str(segments[5])
        if len(segments) == 7 and segments[2] == "threads" and segments[4] == "runs" and segments[6] == "join" and method == "GET":
            return "runtime.run.item.joined", "run", clean_str(segments[5])
        if len(segments) == 7 and segments[2] == "threads" and segments[4] == "runs" and segments[6] == "stream" and method == "GET":
            return "runtime.run.stream.joined", "run", clean_str(segments[5])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and segments[5] == "crons" and method == "POST":
            return "runtime.cron.item.created", "thread", clean_str(segments[3])
        if len(segments) == 8 and segments[2] == "threads" and segments[4] == "runs" and segments[6] == "cancel" and method == "POST":
            return "runtime.run.item.cancelled", "run", clean_str(segments[5])

    return "system.route.requested", "route", path


def _resolve_project_id_from_payload(
    *,
    path: str,
    payload: dict[str, Any] | None,
) -> str | None:
    segments = _route_segments(path)
    if segments == ["api", "projects"]:
        return _nested_value(payload, "id")
    if len(segments) >= 2 and segments[:2] == ["api", "announcements"]:
        return _nested_value(payload, "scope_project_id")
    return None


def _resolve_target_id_from_payload(
    *,
    path: str,
    method: str,
    payload: dict[str, Any] | None,
    actor_user_id: str | None,
) -> str | None:
    segments = _route_segments(path)
    if len(segments) >= 2 and segments[:2] == ["api", "identity"]:
        if segments[2:] == ["session"] and method == "POST":
            return _nested_value(payload, "user", "id")
        if segments[2:] == ["me"] and method == "GET":
            return actor_user_id or _nested_value(payload, "id")
        if segments[2:] == ["password", "change"] and method == "POST":
            return actor_user_id
    if segments == ["api", "projects"] and method == "POST":
        return _nested_value(payload, "id")
    if segments == ["api", "users"] and method == "POST":
        return _nested_value(payload, "id")
    if len(segments) >= 2 and segments[:2] == ["api", "announcements"]:
        return _nested_value(payload, "id")
    if len(segments) >= 4 and segments[:2] == ["api", "projects"]:
        if segments[3] == "assistants" and method == "POST":
            return _nested_value(payload, "id")
    if len(segments) >= 2 and segments[:2] == ["api", "assistants"]:
        if method in {"GET", "PATCH", "POST"}:
            return _nested_value(payload, "id")
    if len(segments) >= 2 and segments[:2] == ["api", "langgraph"]:
        if segments[2:] == ["threads"] and method == "POST":
            return _nested_value(payload, "thread_id")
        if segments[2:] in (["runs"], ["runs", "wait"]) and method == "POST":
            return _nested_value(payload, "run_id")
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "runs" and method == "POST":
            return _nested_value(payload, "run_id")
    return None


def _resolve_metadata(
    *,
    request: AuditHttpRequest,
    plane: AuditPlane,
    target_type: str | None,
    target_id: str | None,
    status_code: int,
    result: AuditResult,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "route_kind": plane.value,
        "query": request.query_string or None,
        "client_ip": request.client_ip,
        "user_agent": request.user_agent,
        "target_type": target_type,
        "target_id": target_id,
        "result": result.value,
        "response_size": _response_size(request.response_content_length),
    }
    if status_code >= 400:
        metadata["is_error"] = True
    if request.metadata:
        metadata.update(
            {
                str(key): value
                for key, value in request.metadata.items()
                if key in {"reason"} and isinstance(value, (str, int, float, bool))
            }
        )
    return {key: value for key, value in metadata.items() if value is not None}


def resolve_http_audit(
    *,
    request: AuditHttpRequest,
    response_payload: dict[str, Any] | None,
    actor_user_id: str | None,
    status_code: int,
    result: AuditResult,
) -> ResolvedHttpAudit:
    plane = _resolve_plane(request.path)
    action, target_type, target_id = _resolve_action(request=request)
    target_id = target_id or _resolve_target_id_from_payload(
        path=request.path,
        method=request.method,
        payload=response_payload,
        actor_user_id=actor_user_id,
    )
    project_id = _resolve_project_id(request) or _resolve_project_id_from_payload(
        path=request.path,
        payload=response_payload,
    )
    metadata = _resolve_metadata(
        request=request,
        plane=plane,
        target_type=target_type,
        target_id=target_id,
        status_code=status_code,
        result=result,
    )
    return ResolvedHttpAudit(
        plane=plane,
        action=action,
        target_type=target_type,
        target_id=target_id,
        project_id=project_id,
        metadata=metadata,
    )
