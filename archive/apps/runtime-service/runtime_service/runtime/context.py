from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any


@dataclass(frozen=True)
class RuntimeContext:
    """Trusted identity and project scope created by Agent Server Auth."""

    user_id: str | None = None
    tenant_id: str | None = None
    role: str | None = None
    permissions: list[str] | None = None
    project_id: str | None = None


@dataclass(frozen=True)
class RuntimeOptions:
    """Per-run business options from configurable.platform_runtime."""

    model_id: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    enable_tools: bool | None = None
    tools: list[str] | None = None
    multimodal_parser_model_id: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        # Drop None values so downstream resolver can use fallback logic clearly.
        data = dataclasses.asdict(self)
        return {key: value for key, value in data.items() if value is not None}


_RUNTIME_CONTEXT_FIELDS = {field.name for field in fields(RuntimeContext)}
_RUNTIME_OPTION_FIELDS = {field.name for field in fields(RuntimeOptions)}
_FORBIDDEN_RUNTIME_OPTION_FIELDS = _RUNTIME_CONTEXT_FIELDS | {
    "identity",
    "org_id",
}


def _to_mapping(raw: Any) -> Mapping[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return raw
    if dataclasses.is_dataclass(raw) and not isinstance(raw, type):
        data = dataclasses.asdict(raw)
        return data if isinstance(data, Mapping) else {}
    raw_dict = getattr(raw, "__dict__", None)
    return raw_dict if isinstance(raw_dict, Mapping) else {}


def coerce_runtime_context(raw: RuntimeContext | Mapping[str, Any] | None) -> RuntimeContext:
    if isinstance(raw, RuntimeContext):
        return raw

    source = _to_mapping(raw)
    normalized = {
        key: source[key]
        for key in _RUNTIME_CONTEXT_FIELDS
        if key in source and source[key] is not None
    }
    return RuntimeContext(**normalized)


def coerce_runtime_options(raw: RuntimeOptions | Mapping[str, Any] | None) -> RuntimeOptions:
    if isinstance(raw, RuntimeOptions):
        return raw

    source = _to_mapping(raw)
    forbidden = sorted(_FORBIDDEN_RUNTIME_OPTION_FIELDS.intersection(source))
    if forbidden:
        raise ValueError(
            "platform_runtime must not contain trusted identity fields: "
            + ", ".join(forbidden)
        )
    normalized = {
        key: source[key]
        for key in _RUNTIME_OPTION_FIELDS
        if key in source and source[key] is not None
    }
    return RuntimeOptions(**normalized)
