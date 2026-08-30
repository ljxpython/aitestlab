"""Pure parsing and resolution of Runtime values."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from runtime_service.runtime.contracts import (
    AgentDefaults,
    ResolvedRuntimeConfig,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
)
from runtime_service.runtime.errors import RuntimeResolutionError

_CONTEXT_FIELDS = frozenset({"model_id", "temperature", "max_tokens", "top_p", "tools"})
_IDENTITY_FIELDS = frozenset(
    {"user_id", "tenant_id", "project_id", "role", "permissions", "secret", "token", "api_key"}
)


def _fail(code: str, field: str | None = None) -> RuntimeResolutionError:
    return RuntimeResolutionError(code, field)


def _identifier(value: object, field: str, code: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 128:
        raise _fail(code, field)
    if not value.isascii() or not all(char.isprintable() and not char.isspace() for char in value):
        raise _fail(code, field)
    return value


def _text(value: object, field: str, code: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 100_000:
        raise _fail(code, field)
    return value


def _names(value: object, field: str, code: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise _fail("runtime.context.invalid_field_type", field)
    names = tuple(_identifier(item, field, code) for item in value)
    if len(set(names)) != len(names):
        raise _fail(code, field)
    return tuple(sorted(names))


def _number(value: object, field: str, *, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail("runtime.context.invalid_field_type", field)
    number = float(value)
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise _fail("runtime.context.invalid_value", field)
    return number


def _max_tokens(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail("runtime.context.invalid_field_type", "max_tokens")
    if value <= 0:
        raise _fail("runtime.context.invalid_value", "max_tokens")
    return value


def parse_runtime_context(raw: Mapping[str, Any] | RuntimeContext | None) -> RuntimeContext:
    """Parse the untrusted Context boundary with no compatibility fallback."""

    if raw is None:
        return RuntimeContext()
    if isinstance(raw, RuntimeContext):
        return _validate_context(raw)
    if not isinstance(raw, Mapping):
        raise _fail("runtime.context.invalid_shape")
    keys = set(raw)
    if any(not isinstance(key, str) for key in keys):
        raise _fail("runtime.context.unknown_field")
    identity = keys & _IDENTITY_FIELDS
    if identity:
        raise _fail("runtime.context.identity_field_forbidden", sorted(identity)[0])
    unknown = keys - _CONTEXT_FIELDS
    if unknown:
        raise _fail("runtime.context.unknown_field", sorted(unknown)[0])
    tools = raw.get("tools")
    if tools is not None and not isinstance(tools, (list, tuple)):
        raise _fail("runtime.context.invalid_field_type", "tools")
    return _validate_context(
        RuntimeContext(
            model_id=raw.get("model_id"),
            temperature=raw.get("temperature"),
            max_tokens=raw.get("max_tokens"),
            top_p=raw.get("top_p"),
            tools=None if tools is None else tuple(tools),
        )
    )


def parse_runtime_principal(raw: Mapping[str, Any] | RuntimePrincipal) -> RuntimePrincipal:
    if isinstance(raw, RuntimePrincipal):
        return _validate_principal(raw)
    if not isinstance(raw, Mapping):
        raise _fail("runtime.auth.invalid_principal")
    expected = {"user_id", "tenant_id", "project_id", "role", "permissions"}
    if set(raw) != expected:
        raise _fail("runtime.auth.invalid_principal")
    return _validate_principal(
        RuntimePrincipal(
            user_id=raw["user_id"],
            tenant_id=raw["tenant_id"],
            project_id=raw["project_id"],
            role=raw["role"],
            permissions=tuple(raw["permissions"]) if isinstance(raw["permissions"], list) else raw["permissions"],
        )
    )


def parse_runtime_policy(raw: Mapping[str, Any] | RuntimePolicy) -> RuntimePolicy:
    if isinstance(raw, RuntimePolicy):
        return _validate_policy(raw)
    if not isinstance(raw, Mapping):
        raise _fail("runtime.auth.invalid_claim")
    expected = {"version", "allowed_model_ids", "allowed_tool_names"}
    if set(raw) != expected:
        raise _fail("runtime.auth.invalid_claim")
    return _validate_policy(
        RuntimePolicy(
            version=raw["version"],
            allowed_model_ids=tuple(raw["allowed_model_ids"])
            if isinstance(raw["allowed_model_ids"], list)
            else raw["allowed_model_ids"],
            allowed_tool_names=tuple(raw["allowed_tool_names"])
            if isinstance(raw["allowed_tool_names"], list)
            else raw["allowed_tool_names"],
        )
    )


def _validate_context(value: RuntimeContext) -> RuntimeContext:
    if not isinstance(value, RuntimeContext):
        raise _fail("runtime.context.invalid_shape")
    model_id = None if value.model_id is None else _identifier(value.model_id, "model_id", "runtime.context.invalid_value")
    temperature = _number(value.temperature, "temperature", minimum=0, maximum=2)
    top_p = _number(value.top_p, "top_p", minimum=0, maximum=1)
    if top_p == 0:
        raise _fail("runtime.context.invalid_value", "top_p")
    max_tokens = _max_tokens(value.max_tokens)
    tools = None if value.tools is None else _names(value.tools, "tools", "runtime.context.invalid_value")
    return replace(value, model_id=model_id, temperature=temperature, max_tokens=max_tokens, top_p=top_p, tools=tools)


def _validate_principal(value: RuntimePrincipal) -> RuntimePrincipal:
    if not isinstance(value, RuntimePrincipal):
        raise _fail("runtime.auth.invalid_principal")
    return replace(
        value,
        user_id=_identifier(value.user_id, "user_id", "runtime.auth.invalid_principal"),
        tenant_id=_identifier(value.tenant_id, "tenant_id", "runtime.auth.invalid_principal"),
        project_id=_identifier(value.project_id, "project_id", "runtime.auth.invalid_principal"),
        role=_identifier(value.role, "role", "runtime.auth.invalid_principal"),
        permissions=_names(value.permissions, "permissions", "runtime.auth.invalid_principal"),
    )


def _validate_policy(value: RuntimePolicy) -> RuntimePolicy:
    if not isinstance(value, RuntimePolicy):
        raise _fail("runtime.auth.invalid_claim")
    version = _text(value.version, "policy_version", "runtime.auth.invalid_claim")
    models = _names(value.allowed_model_ids, "allowed_model_ids", "runtime.auth.invalid_claim")
    if not models:
        raise _fail("runtime.auth.invalid_claim", "allowed_model_ids")
    tools = _names(value.allowed_tool_names, "allowed_tool_names", "runtime.auth.invalid_claim")
    return replace(value, version=version, allowed_model_ids=models, allowed_tool_names=tools)


def _validate_defaults(value: AgentDefaults) -> AgentDefaults:
    if not isinstance(value, AgentDefaults):
        raise _fail("runtime.defaults.invalid")
    required = _names(value.required_tool_names, "required_tool_names", "runtime.defaults.invalid")
    optional = _names(value.optional_tool_names, "optional_tool_names", "runtime.defaults.invalid")
    if set(required) & set(optional):
        raise _fail("runtime.defaults.invalid", "tool_names")
    return replace(
        value,
        model_id=_identifier(value.model_id, "model_id", "runtime.defaults.invalid"),
        system_prompt=_text(value.system_prompt, "system_prompt", "runtime.defaults.invalid"),
        prompt_version=_text(value.prompt_version, "prompt_version", "runtime.defaults.invalid"),
        temperature=_number(value.temperature, "temperature", minimum=0, maximum=2),
        max_tokens=_max_tokens(value.max_tokens),
        top_p=_number(value.top_p, "top_p", minimum=0, maximum=1),
        required_tool_names=required,
        optional_tool_names=optional,
    )


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _config_hash(config: ResolvedRuntimeConfig) -> str:
    payload = {
        "schema": "runtime-config/v1",
        "principal": {
            "tenant_id": config.principal.tenant_id,
            "project_id": config.principal.project_id,
            "user_id": config.principal.user_id,
            "role": config.principal.role,
            "permissions": list(config.principal.permissions),
        },
        "model_id": config.model_id,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "top_p": config.top_p,
        "required_tool_names": list(config.required_tool_names),
        "optional_tool_names": list(config.optional_tool_names),
        "prompt_version": config.prompt_version,
        "prompt_hash": config.prompt_hash,
        "policy_version": config.policy_version,
    }
    canonical = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return _sha256(canonical)


def resolve_runtime_config(
    *,
    principal: RuntimePrincipal,
    context: RuntimeContext,
    policy: RuntimePolicy,
    defaults: AgentDefaults,
) -> ResolvedRuntimeConfig:
    """Validate, merge and hash a single Run without side effects."""

    principal = _validate_principal(principal)
    context = _validate_context(context)
    policy = _validate_policy(policy)
    defaults = _validate_defaults(defaults)

    model_id = context.model_id if context.model_id is not None else defaults.model_id
    if model_id not in policy.allowed_model_ids:
        raise _fail("runtime.model.not_allowed", "model_id")
    temperature = context.temperature if context.temperature is not None else defaults.temperature
    max_tokens = context.max_tokens if context.max_tokens is not None else defaults.max_tokens
    top_p = context.top_p if context.top_p is not None else defaults.top_p

    required = defaults.required_tool_names
    optional_source = context.tools if context.tools is not None else defaults.optional_tool_names
    optional = _names(optional_source, "optional_tool_names", "runtime.optional_tool.not_declared")
    if set(required) & set(optional):
        raise _fail("runtime.tool.duplicate", "tool_names")
    if any(name not in policy.allowed_tool_names for name in required):
        raise _fail("runtime.required_tool.not_allowed", "required_tool_names")
    if any(name not in defaults.optional_tool_names for name in optional):
        raise _fail("runtime.optional_tool.not_declared", "optional_tool_names")
    if any(name not in policy.allowed_tool_names for name in optional):
        raise _fail("runtime.optional_tool.not_allowed", "optional_tool_names")

    prompt_hash = _sha256(defaults.system_prompt)
    resolved = ResolvedRuntimeConfig(
        principal=principal,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        required_tool_names=required,
        optional_tool_names=optional,
        prompt_version=defaults.prompt_version,
        prompt_hash=prompt_hash,
        policy_version=policy.version,
        config_hash="",
    )
    return replace(resolved, config_hash=_config_hash(resolved))


__all__ = [
    "parse_runtime_context",
    "parse_runtime_policy",
    "parse_runtime_principal",
    "resolve_runtime_config",
]
