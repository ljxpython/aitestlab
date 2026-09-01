from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import builtins
from math import inf, nan

import pytest

from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeResolutionError,
    ResolvedRuntimeConfig,
    parse_runtime_context,
    resolved_runtime_config_from_snapshot,
    resolve_runtime_config,
    runtime_config_snapshot,
    runtime_context_hash,
)
from runtime_service.runtime.runtime_config import parse_context


def _inputs() -> tuple[RuntimePrincipal, RuntimePolicy, AgentDefaults]:
    return (
        RuntimePrincipal("user-a", "tenant-a", "project-a", "developer", ("search", "read_project")),
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
    principal, policy, defaults = _inputs()
    resolved = resolve_runtime_config(
        principal=principal,
        context=RuntimeContext(tools=()),
        policy=policy,
        defaults=defaults,
    )
    values = [
        RuntimePrincipal("user-a", "tenant-a", "project-a", "developer", ()),
        RuntimeContext(),
        RuntimePolicy("p1", ("test:model",), ()),
        AgentDefaults("test:model", "prompt", "v1"),
        resolved,
    ]
    for value in values:
        with pytest.raises(FrozenInstanceError):
            field = next(iter(value.__dataclass_fields__))
            setattr(value, field, "other")


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


@pytest.mark.parametrize(
    "field, value",
    [
        ("temperature", True),
        ("temperature", nan),
        ("temperature", inf),
        ("temperature", -0.1),
        ("top_p", 0),
        ("top_p", 1.1),
        ("max_tokens", True),
        ("max_tokens", 0),
    ],
)
def test_context_parser_rejects_invalid_generation_values(field: str, value: object) -> None:
    with pytest.raises(RuntimeResolutionError):
        parse_runtime_context({field: value})


def test_resolver_enforces_actor_tool_permissions() -> None:
    principal, policy, defaults = _inputs()
    with pytest.raises(RuntimeResolutionError) as error:
        resolve_runtime_config(
            principal=principal,
            context=RuntimeContext(),
            policy=policy,
            defaults=defaults,
            tool_permissions={"search": "tool.search", "read_project": "tool.read"},
        )
    assert error.value.code == "runtime.optional_tool.not_allowed"

    with pytest.raises(RuntimeResolutionError) as required_error:
        resolve_runtime_config(
            principal=principal,
            context=RuntimeContext(),
            policy=policy,
            defaults=AgentDefaults(
                model_id=defaults.model_id,
                system_prompt=defaults.system_prompt,
                prompt_version=defaults.prompt_version,
                required_tool_names=("search",),
            ),
            tool_permissions={"search": "tool.search"},
        )
    assert required_error.value.code == "runtime.required_tool.not_allowed"


def test_runtime_context_hash_and_snapshot_are_safe_and_stable() -> None:
    context = {"temperature": 0, "tools": ["search"]}
    assert runtime_context_hash(context) == runtime_context_hash(
        RuntimeContext(temperature=0.0, tools=("search",))
    )

    principal, policy, defaults = _inputs()
    resolved = resolve_runtime_config(
        principal=principal,
        context=RuntimeContext(tools=()),
        policy=policy,
        defaults=defaults,
    )
    snapshot = runtime_config_snapshot(resolved)
    json.dumps(snapshot, allow_nan=False)
    restored = resolved_runtime_config_from_snapshot(snapshot)
    assert restored == resolved
    serialized = str(snapshot)
    assert defaults.system_prompt not in serialized
    assert "secret" not in serialized
    assert "jwt" not in serialized.lower()

    tampered = {**snapshot, "config_hash": "sha256:" + "0" * 64}
    with pytest.raises(RuntimeResolutionError) as error:
        resolved_runtime_config_from_snapshot(tampered)
    assert error.value.code == "runtime.snapshot.hash_mismatch"


def test_runtime_context_hash_changes_with_semantics() -> None:
    assert runtime_context_hash(RuntimeContext(temperature=0)) != runtime_context_hash(
        RuntimeContext(temperature=1)
    )


def test_resolver_does_not_mutate_inputs_or_perform_io(monkeypatch: pytest.MonkeyPatch) -> None:
    principal, policy, defaults = _inputs()
    context = {"temperature": 0, "tools": ["read_project"]}
    original_context = json.loads(json.dumps(context))

    def fail_io(*_: object, **__: object) -> object:
        raise AssertionError("Resolver must not perform I/O")

    monkeypatch.setattr(builtins, "open", fail_io)
    resolved = resolve_runtime_config(
        principal=principal,
        context=parse_runtime_context(context),
        policy=policy,
        defaults=defaults,
    )

    assert context == original_context
    assert resolved.optional_tool_names == ("read_project",)
