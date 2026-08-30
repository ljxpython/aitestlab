from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeResolutionError,
    parse_runtime_context,
    resolve_runtime_config,
)
from runtime_service.runtime.runtime_config import parse_context


def _inputs() -> tuple[RuntimePrincipal, RuntimePolicy, AgentDefaults]:
    return (
        RuntimePrincipal("user-a", "tenant-a", "project-a", "developer", ("runtime.read",)),
        RuntimePolicy(
            "policy-1",
            ("deepseek:deepseek-chat",),
            ("read_project", "search"),
        ),
        AgentDefaults(
            model_id="deepseek:deepseek-chat",
            system_prompt="You are a reference agent.",
            prompt_version="reference-agent-1",
            temperature=0.7,
            optional_tool_names=("search", "read_project"),
        ),
    )


def test_contracts_are_frozen() -> None:
    context = RuntimeContext()
    with pytest.raises(FrozenInstanceError):
        context.model_id = "other"  # type: ignore[misc]


def test_context_parser_rejects_unknown_and_identity_fields() -> None:
    with pytest.raises(RuntimeResolutionError) as unknown:
        parse_runtime_context({"future": True})
    assert unknown.value.code == "runtime.context.unknown_field"

    with pytest.raises(RuntimeResolutionError) as identity:
        parse_runtime_context({"tenant_id": "tenant-b"})
    assert identity.value.code == "runtime.context.identity_field_forbidden"

    with pytest.raises(RuntimeResolutionError) as legacy:
        parse_context({"platform_runtime": {}})
    assert legacy.value.code == "runtime.context.unknown_field"


def test_resolver_merges_context_and_preserves_empty_tools() -> None:
    principal, policy, defaults = _inputs()
    resolved = resolve_runtime_config(
        principal=principal,
        context=RuntimeContext(temperature=0, tools=()),
        policy=policy,
        defaults=defaults,
    )

    assert resolved.temperature == 0.0
    assert resolved.optional_tool_names == ()
    assert resolved.required_tool_names == ()
    assert resolved.prompt_hash.startswith("sha256:")
    assert resolved.config_hash.startswith("sha256:")


def test_resolver_normalizes_names_and_hashes_equivalent_inputs() -> None:
    principal, policy, defaults = _inputs()
    first = resolve_runtime_config(
        principal=principal,
        context=RuntimeContext(),
        policy=policy,
        defaults=defaults,
    )
    equivalent_defaults = AgentDefaults(
        model_id=defaults.model_id,
        system_prompt=defaults.system_prompt,
        prompt_version=defaults.prompt_version,
        temperature=defaults.temperature,
        optional_tool_names=("read_project", "search"),
    )
    second = resolve_runtime_config(
        principal=principal,
        context=RuntimeContext(),
        policy=policy,
        defaults=equivalent_defaults,
    )

    assert first.optional_tool_names == ("read_project", "search")
    assert first.config_hash == second.config_hash


def test_resolver_rejects_model_and_tool_policy_violations() -> None:
    principal, policy, defaults = _inputs()
    with pytest.raises(RuntimeResolutionError) as model_error:
        resolve_runtime_config(
            principal=principal,
            context=RuntimeContext(model_id="openai:gpt-5.5"),
            policy=policy,
            defaults=defaults,
        )
    assert model_error.value.code == "runtime.model.not_allowed"

    with pytest.raises(RuntimeResolutionError) as tool_error:
        resolve_runtime_config(
            principal=principal,
            context=RuntimeContext(tools=("unknown",)),
            policy=policy,
            defaults=defaults,
        )
    assert tool_error.value.code == "runtime.optional_tool.not_declared"
