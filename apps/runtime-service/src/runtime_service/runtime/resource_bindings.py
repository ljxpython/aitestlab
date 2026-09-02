"""Validated, serializable Thread resource bindings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from runtime_service.runtime.contracts import RuntimePrincipal
from runtime_service.runtime.errors import RuntimeResolutionError

_SCHEMA = "runtime-resource-bindings/v1"
_REQUIRED_FIELDS = frozenset(
    {"provider", "resource_id", "tenant_id", "project_id", "thread_id"}
)


@dataclass(frozen=True, slots=True)
class RuntimeResourceBinding:
    kind: str
    provider: str
    resource_id: str
    tenant_id: str
    project_id: str
    thread_id: str


def _failed(kind: str) -> RuntimeResolutionError:
    return RuntimeResolutionError(f"runtime.{kind}.recovery_failed")


def resolve_resource_binding(
    config: Mapping[str, Any],
    principal: RuntimePrincipal,
    kind: str,
) -> RuntimeResourceBinding:
    """Resolve one resource from trusted server metadata and fail closed."""

    metadata = config.get("metadata")
    thread_metadata = (
        metadata.get("__graphharbor_thread_metadata")
        if isinstance(metadata, Mapping)
        else None
    )
    raw_bindings = (
        thread_metadata.get("runtime_resource_bindings")
        if isinstance(thread_metadata, Mapping)
        else None
    )
    if not isinstance(raw_bindings, Mapping) or raw_bindings.get("schema") != _SCHEMA:
        raise _failed(kind)
    raw = raw_bindings.get(kind)
    if not isinstance(raw, Mapping) or set(raw) != _REQUIRED_FIELDS:
        raise _failed(kind)
    values = {field: raw.get(field) for field in _REQUIRED_FIELDS}
    if any(not isinstance(value, str) or not value or value != value.strip() for value in values.values()):
        raise _failed(kind)
    configurable = config.get("configurable")
    thread_id = configurable.get("thread_id") if isinstance(configurable, Mapping) else None
    if (
        values["tenant_id"] != principal.tenant_id
        or values["project_id"] != principal.project_id
        or values["thread_id"] != thread_id
    ):
        raise _failed(kind)
    return RuntimeResourceBinding(kind=kind, **values)


def thread_resource_metadata(
    *,
    kind: str,
    provider: str,
    resource_id: str,
    principal: RuntimePrincipal,
    thread_id: str,
) -> dict[str, object]:
    """Build the JSON-safe metadata written when a Thread owns a resource."""

    if not all(isinstance(value, str) and value.strip() for value in (kind, provider, resource_id, thread_id)):
        raise ValueError("resource binding values must be non-empty strings")
    return {
        "runtime_resource_bindings": {
            "schema": _SCHEMA,
            kind: {
                "provider": provider,
                "resource_id": resource_id,
                "tenant_id": principal.tenant_id,
                "project_id": principal.project_id,
                "thread_id": thread_id,
            },
        }
    }


__all__ = ["RuntimeResourceBinding", "resolve_resource_binding", "thread_resource_metadata"]
