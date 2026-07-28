from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from runtime_service.runtime.config_utils import read_configurable
from runtime_service.runtime.context import (
    RuntimeContext,
    RuntimeOptions,
    coerce_runtime_context,
    coerce_runtime_options,
)
from runtime_service.runtime.modeling import resolve_model_by_id


@dataclass(frozen=True)
class AgentDefaults:
    model_id: str
    system_prompt: str
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    enable_tools: bool = True
    public_tool_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedRuntimeRequest:
    context: RuntimeContext
    model: Any
    system_prompt: str
    tools: list[Any]
    options: RuntimeOptions = RuntimeOptions()


@dataclass(frozen=True)
class ResolvedRuntimeSettings:
    context: RuntimeContext
    model: Any
    system_prompt: str
    enable_tools: bool
    requested_public_tool_names: list[str]
    options: RuntimeOptions = RuntimeOptions()


def normalize_tool_name(raw_name: Any) -> str:
    return str(raw_name or "").strip().lower()


def _user_value(user: Any, key: str) -> Any:
    if isinstance(user, Mapping):
        return user.get(key)
    try:
        return user[key]
    except (KeyError, TypeError):
        return getattr(user, key, None)


def _require_trusted_context_fields(context: RuntimeContext) -> RuntimeContext:
    missing = [
        name
        for name, value in (
            ("identity", context.user_id),
            ("tenant_id", context.tenant_id),
            ("role", context.role),
            ("project_id", context.project_id),
        )
        if not str(value or "").strip()
    ]
    if missing:
        raise ValueError(
            "Authenticated runtime user is missing required fields: "
            + ", ".join(missing)
        )
    return context


def resolve_trusted_runtime_context(
    runtime: Any,
    *,
    allow_internal_context: bool = False,
) -> RuntimeContext:
    server_info = getattr(runtime, "server_info", None)
    user = getattr(server_info, "user", None)
    if user is None or not bool(getattr(user, "is_authenticated", True)):
        if allow_internal_context:
            return _require_trusted_context_fields(
                coerce_runtime_context(getattr(runtime, "context", None))
            )
        raise ValueError("Authenticated Agent Server runtime user is required.")

    user_id = str(_user_value(user, "identity") or "").strip()
    tenant_id = str(_user_value(user, "tenant_id") or "").strip()
    role = str(_user_value(user, "role") or "").strip()
    project_id = str(_user_value(user, "project_id") or "").strip()
    raw_permissions = _user_value(user, "permissions")
    permissions = (
        [str(item).strip() for item in raw_permissions if str(item).strip()]
        if isinstance(raw_permissions, Sequence)
        and not isinstance(raw_permissions, (str, bytes))
        else []
    )

    return _require_trusted_context_fields(
        RuntimeContext(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions,
            project_id=project_id,
        )
    )


def resolve_runtime_options(config: Mapping[str, Any] | None) -> RuntimeOptions:
    configurable = read_configurable(config)
    raw_options = configurable.get("platform_runtime")
    if raw_options is not None and not isinstance(raw_options, Mapping):
        raise ValueError("configurable.platform_runtime must be an object.")
    return coerce_runtime_options(raw_options)


def build_tool_catalog(tools: Sequence[Any]) -> dict[str, Any]:
    catalog: dict[str, Any] = {}
    for tool in tools:
        name = normalize_tool_name(getattr(tool, "name", ""))
        if not name:
            continue
        catalog[name] = tool
    return catalog


def _normalize_requested_tool_names(raw_names: Sequence[str] | None) -> list[str]:
    if raw_names is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        name = normalize_tool_name(raw_name)
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    return normalized


def _bind_model_request_params(
    model: Any,
    *,
    temperature: float | None,
    max_tokens: int | None,
    top_p: float | None,
) -> Any:
    kwargs: dict[str, Any] = {}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if top_p is not None:
        kwargs["top_p"] = top_p
    if not kwargs:
        return model
    return model.bind(**kwargs)


def _resolve_optional_tools(
    public_tool_catalog: Mapping[str, Any],
    requested_tool_names: Sequence[str],
) -> list[Any]:
    if not requested_tool_names:
        return []

    selected: list[Any] = []
    unknown: list[str] = []
    for name in requested_tool_names:
        tool = public_tool_catalog.get(name)
        if tool is None:
            unknown.append(name)
            continue
        selected.append(tool)

    if unknown:
        allowed = ", ".join(sorted(public_tool_catalog.keys()))
        raise ValueError(f"Unsupported tools: {unknown}. allowed: {allowed}")

    return selected


def _dedupe_tools_by_name(tools: Sequence[Any]) -> list[Any]:
    unique_tools: list[Any] = []
    seen: set[str] = set()
    for tool in tools:
        name = normalize_tool_name(getattr(tool, "name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        unique_tools.append(tool)
    return unique_tools


def dedupe_tools_by_name(tools: Sequence[Any]) -> list[Any]:
    return _dedupe_tools_by_name(tools)


def resolve_optional_tools(
    public_tool_catalog: Mapping[str, Any],
    requested_tool_names: Sequence[str],
) -> list[Any]:
    return _resolve_optional_tools(public_tool_catalog, requested_tool_names)


def resolve_runtime_settings(
    *,
    runtime: Any,
    config: Mapping[str, Any] | None,
    defaults: AgentDefaults,
    allow_internal_context: bool = False,
) -> ResolvedRuntimeSettings:
    configurable = read_configurable(config)
    runtime_context = resolve_trusted_runtime_context(
        runtime,
        allow_internal_context=(
            allow_internal_context
            or configurable.get("platform_local_debug") is True
        ),
    )
    options = resolve_runtime_options(config)

    model_id = options.model_id or defaults.model_id
    system_prompt = options.system_prompt or defaults.system_prompt
    temperature = (
        options.temperature
        if options.temperature is not None
        else defaults.temperature
    )
    max_tokens = (
        options.max_tokens
        if options.max_tokens is not None
        else defaults.max_tokens
    )
    top_p = options.top_p if options.top_p is not None else defaults.top_p
    enable_tools = (
        options.enable_tools
        if options.enable_tools is not None
        else defaults.enable_tools
    )

    requested_public_tool_names = _normalize_requested_tool_names(
        options.tools
        if options.tools is not None
        else defaults.public_tool_names
    )

    model = _bind_model_request_params(
        resolve_model_by_id(model_id),
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )

    return ResolvedRuntimeSettings(
        context=runtime_context,
        options=options,
        model=model,
        system_prompt=system_prompt,
        enable_tools=enable_tools,
        requested_public_tool_names=requested_public_tool_names,
    )


def resolve_runtime_request(
    *,
    runtime: Any,
    config: Mapping[str, Any] | None,
    defaults: AgentDefaults,
    required_tools: Sequence[Any],
    public_tools: Sequence[Any],
) -> ResolvedRuntimeRequest:
    settings = resolve_runtime_settings(
        runtime=runtime,
        config=config,
        defaults=defaults,
    )
    public_tool_catalog = build_tool_catalog(public_tools)
    optional_tools = (
        resolve_optional_tools(
            public_tool_catalog,
            settings.requested_public_tool_names,
        )
        if settings.enable_tools
        else []
    )
    tools = dedupe_tools_by_name([*required_tools, *optional_tools])

    return ResolvedRuntimeRequest(
        context=settings.context,
        options=settings.options,
        model=settings.model,
        system_prompt=settings.system_prompt,
        tools=tools,
    )
