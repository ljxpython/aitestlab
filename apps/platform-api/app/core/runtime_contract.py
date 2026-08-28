from __future__ import annotations

from typing import Any, Iterable

from app.core.normalization import ensure_dict

RUNTIME_CONTEXT_READONLY_KEYS = (
    "user_id",
    "tenant_id",
    "role",
    "permissions",
    "project_id",
)

TRUSTED_RUNTIME_CONTEXT_KEYS = (
    *RUNTIME_CONTEXT_READONLY_KEYS,
    "projectId",
    "x-project-id",
)

PROJECT_SCOPE_ALIAS_KEYS = (
    "project_id",
    "projectId",
    "x-project-id",
)

RUNTIME_CONTEXT_BUSINESS_KEYS = (
    "model_id",
    "system_prompt",
    "temperature",
    "max_tokens",
    "top_p",
    "enable_tools",
    "tools",
)

RUNTIME_OPTION_KEYS = (
    *RUNTIME_CONTEXT_BUSINESS_KEYS,
    "multimodal_parser_model_id",
)

PROTOCOL_V2_EVENT_CHANNELS = {
    "checkpoints",
    "values",
    "updates",
    "messages",
    "tools",
    "lifecycle",
    "input",
    "tasks",
    "custom",
}

PROTOCOL_V2_RUN_DURABILITY = {"sync", "async", "exit"}
PROTOCOL_V2_RUN_DISCONNECT = {"cancel", "continue"}


def _validate_runtime_option_values(options: dict[str, Any]) -> None:
    string_keys = ("model_id", "system_prompt", "multimodal_parser_model_id")
    for key in string_keys:
        value = options.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"platform_runtime.{key} must be a non-empty string")

    for key in ("temperature", "top_p"):
        value = options.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            raise ValueError(f"platform_runtime.{key} must be a number")

    max_tokens = options.get("max_tokens")
    if max_tokens is not None and (
        isinstance(max_tokens, bool)
        or not isinstance(max_tokens, int)
        or max_tokens <= 0
    ):
        raise ValueError("platform_runtime.max_tokens must be a positive integer")

    enable_tools = options.get("enable_tools")
    if enable_tools is not None and not isinstance(enable_tools, bool):
        raise ValueError("platform_runtime.enable_tools must be a boolean")

    tools = options.get("tools")
    if tools is not None and (
        not isinstance(tools, list)
        or any(not isinstance(tool, str) or not tool.strip() for tool in tools)
    ):
        raise ValueError("platform_runtime.tools must be an array of non-empty strings")

RUNTIME_CONTEXT_PROPERTY_TYPES: dict[str, str] = {
    "user_id": "string",
    "tenant_id": "string",
    "role": "string",
    "permissions": "array[string]",
    "project_id": "string",
}

RUNTIME_OPTION_PROPERTY_TYPES: dict[str, str] = {
    "model_id": "string",
    "system_prompt": "string",
    "temperature": "number",
    "max_tokens": "number",
    "top_p": "number",
    "enable_tools": "boolean",
    "tools": "array[string]",
    "multimodal_parser_model_id": "string",
}

EXECUTION_CONFIG_PROPERTIES: dict[str, dict[str, Any]] = {
    "recursion_limit": {"type": "number", "required": False},
    "run_name": {"type": "string", "required": False},
    "max_concurrency": {"type": "number", "required": False},
}


def normalize_runtime_object(value: dict[str, Any] | None) -> dict[str, Any]:
    return ensure_dict(value)


def strip_keys(payload: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    next_payload = dict(payload)
    for key in keys:
        next_payload.pop(key, None)
    return next_payload


def move_runtime_business_fields_into_context(
    *,
    source: dict[str, Any],
    context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    next_source = dict(source)
    next_context = dict(context)
    for key in RUNTIME_CONTEXT_BUSINESS_KEYS:
        if key not in next_source:
            continue
        value = next_source.pop(key)
        if value is None or key in next_context:
            continue
        next_context[key] = value
    return next_source, next_context


def normalize_runtime_contract(
    *,
    config: dict[str, Any],
    context: dict[str, Any],
    metadata: dict[str, Any],
    project_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    next_context = strip_keys(context, TRUSTED_RUNTIME_CONTEXT_KEYS)
    next_context["project_id"] = project_id

    next_config = strip_keys(config, PROJECT_SCOPE_ALIAS_KEYS)
    next_metadata = strip_keys(metadata, PROJECT_SCOPE_ALIAS_KEYS)

    next_config, next_context = move_runtime_business_fields_into_context(
        source=next_config,
        context=next_context,
    )

    configurable = next_config.get("configurable")
    configurable_dict = (
        strip_keys(dict(configurable), TRUSTED_RUNTIME_CONTEXT_KEYS)
        if isinstance(configurable, dict)
        else {}
    )
    configurable_dict, next_context = move_runtime_business_fields_into_context(
        source=configurable_dict,
        context=next_context,
    )
    if configurable_dict:
        next_config["configurable"] = configurable_dict
    else:
        next_config.pop("configurable", None)

    config_metadata = next_config.get("metadata")
    config_metadata_dict = (
        strip_keys(dict(config_metadata), PROJECT_SCOPE_ALIAS_KEYS)
        if isinstance(config_metadata, dict)
        else {}
    )
    if config_metadata_dict:
        next_config["metadata"] = config_metadata_dict
    else:
        next_config.pop("metadata", None)

    return next_config, next_context, next_metadata


def normalize_runtime_payload(
    *,
    payload: dict[str, Any] | None,
    project_id: str,
) -> dict[str, Any]:
    next_payload = strip_keys(normalize_runtime_object(payload), PROJECT_SCOPE_ALIAS_KEYS)
    next_config, next_context, next_metadata = normalize_runtime_contract(
        config=normalize_runtime_object(next_payload.get("config")),
        context=normalize_runtime_object(next_payload.get("context")),
        metadata=normalize_runtime_object(next_payload.get("metadata")),
        project_id=project_id,
    )

    if next_config:
        next_payload["config"] = next_config
    else:
        next_payload.pop("config", None)

    next_payload["context"] = next_context

    if next_metadata:
        next_payload["metadata"] = next_metadata
    else:
        next_payload.pop("metadata", None)

    return next_payload


def normalize_protocol_v2_command(
    *,
    payload: dict[str, Any],
    default_model_id: str | None = None,
) -> dict[str, Any]:
    command_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params")
    if isinstance(command_id, bool) or not isinstance(command_id, int):
        raise ValueError("Protocol command id must be an integer")
    if not isinstance(method, str) or not method.strip():
        raise ValueError("Protocol command method must be a non-empty string")
    if params is not None and not isinstance(params, dict):
        raise ValueError("Protocol command params must be an object")
    unknown_envelope_keys = sorted(set(payload) - {"id", "method", "params"})
    if unknown_envelope_keys:
        raise ValueError(
            "Unsupported Protocol v2 command fields: "
            + ", ".join(unknown_envelope_keys)
        )

    normalized = {"id": command_id, "method": method, "params": dict(params or {})}
    if method != "run.start":
        return normalized

    run_params = normalized["params"]
    unknown_run_fields = sorted(
        set(run_params)
        - {
            "assistant_id",
            "input",
            "config",
            "metadata",
            "durability",
            "stream_resumable",
            "on_disconnect",
        }
    )
    if unknown_run_fields:
        raise ValueError(
            "Unsupported run.start fields: " + ", ".join(unknown_run_fields)
        )

    run_params.setdefault("durability", "sync")
    run_params.setdefault("stream_resumable", True)
    run_params.setdefault("on_disconnect", "continue")
    durability = run_params["durability"]
    if not isinstance(durability, str) or durability not in PROTOCOL_V2_RUN_DURABILITY:
        raise ValueError("run.start durability must be one of: sync, async, exit")
    if not isinstance(run_params["stream_resumable"], bool):
        raise ValueError("run.start stream_resumable must be a boolean")
    if (
        not isinstance(run_params["on_disconnect"], str)
        or run_params["on_disconnect"] not in PROTOCOL_V2_RUN_DISCONNECT
    ):
        raise ValueError("run.start on_disconnect must be cancel or continue")

    config = ensure_dict(run_params.get("config"))
    configurable = ensure_dict(config.get("configurable"))
    raw_runtime_options = configurable.get("platform_runtime")
    if raw_runtime_options is not None and not isinstance(raw_runtime_options, dict):
        raise ValueError("config.configurable.platform_runtime must be an object")
    runtime_options = dict(raw_runtime_options or {})

    forbidden_locations = (
        ("metadata", ensure_dict(run_params.get("metadata"))),
        ("config", config),
        ("config.configurable", configurable),
        ("config.configurable.platform_runtime", runtime_options),
    )
    for location, value in forbidden_locations:
        forbidden = sorted(set(value).intersection(TRUSTED_RUNTIME_CONTEXT_KEYS))
        if forbidden:
            raise ValueError(
                f"{location} must not contain trusted identity fields: "
                + ", ".join(forbidden)
            )

    unknown_option_keys = sorted(set(runtime_options) - set(RUNTIME_OPTION_KEYS))
    if unknown_option_keys:
        raise ValueError(
            "Unsupported platform_runtime fields: " + ", ".join(unknown_option_keys)
        )

    next_config = dict(config)
    next_configurable = dict(configurable)
    next_configurable.pop("platform_runtime", None)
    for source in (next_config, next_configurable):
        for key in RUNTIME_OPTION_KEYS:
            if key in source and key not in runtime_options:
                runtime_options[key] = source[key]
            source.pop(key, None)
    if default_model_id and not runtime_options.get("model_id"):
        runtime_options["model_id"] = default_model_id
    _validate_runtime_option_values(runtime_options)

    if runtime_options:
        next_configurable["platform_runtime"] = runtime_options
    if next_configurable:
        next_config["configurable"] = next_configurable
    else:
        next_config.pop("configurable", None)
    if next_config:
        run_params["config"] = next_config
    else:
        run_params.pop("config", None)
    return normalized


def normalize_protocol_v2_event_request(payload: dict[str, Any]) -> dict[str, Any]:
    unknown_keys = sorted(set(payload) - {"channels", "namespaces", "depth", "since"})
    if unknown_keys:
        raise ValueError(
            "Unsupported Protocol v2 event fields: " + ", ".join(unknown_keys)
        )

    channels = payload.get("channels")
    if not isinstance(channels, list) or not channels:
        raise ValueError("Protocol v2 event channels must be a non-empty array")
    if any(not isinstance(channel, str) or not channel.strip() for channel in channels):
        raise ValueError("Protocol v2 event channels must contain non-empty strings")
    unsupported_channels = sorted(
        channel
        for channel in channels
        if channel not in PROTOCOL_V2_EVENT_CHANNELS and not channel.startswith("custom:")
    )
    if unsupported_channels:
        raise ValueError(
            "Unsupported Protocol v2 event channels: " + ", ".join(unsupported_channels)
        )

    namespaces = payload.get("namespaces")
    if namespaces is not None and (
        not isinstance(namespaces, list)
        or any(
            not isinstance(namespace, list)
            or any(not isinstance(segment, str) for segment in namespace)
            for namespace in namespaces
        )
    ):
        raise ValueError("Protocol v2 event namespaces must be an array of string arrays")

    for key in ("depth", "since"):
        value = payload.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise ValueError(f"Protocol v2 event {key} must be a non-negative integer")
    return dict(payload)


def build_execution_config_schema_properties() -> dict[str, dict[str, Any]]:
    return {
        key: dict(value)
        for key, value in EXECUTION_CONFIG_PROPERTIES.items()
    }


def build_runtime_context_schema_properties(
    *,
    keys: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    selected_keys = tuple(keys) if keys is not None else tuple(RUNTIME_CONTEXT_PROPERTY_TYPES)
    return {
        key: {
            "type": RUNTIME_CONTEXT_PROPERTY_TYPES[key],
            "required": False,
        }
        for key in selected_keys
        if key in RUNTIME_CONTEXT_PROPERTY_TYPES
    }


def build_runtime_options_schema_properties() -> dict[str, dict[str, Any]]:
    return {
        key: {"type": value_type, "required": False}
        for key, value_type in RUNTIME_OPTION_PROPERTY_TYPES.items()
    }
