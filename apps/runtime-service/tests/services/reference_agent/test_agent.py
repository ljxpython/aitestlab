from __future__ import annotations

import asyncio

import pytest
from runtime_service.runtime import RuntimeAuthError, RuntimeContext, RuntimeResolutionError
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.services.reference_agent import agent
from runtime_service.services.reference_agent.tools import read_reference
from support import BindableFakeChatModel


def _config(model: BindableFakeChatModel, context: object | None = None) -> dict[str, object]:
    return {
        "configurable": {
            "_runtime_model": model,
            "langgraph_auth_user": _auth_user(context),
        }
    }


def _auth_user(context: object | None = None) -> dict[str, object]:
    return {
        "runtime_principal": {
            "user_id": "local-user",
            "tenant_id": "local-tenant",
            "project_id": "reference-project",
            "role": "developer",
            "permissions": ["runtime.tool.read"],
        },
        "runtime_policy": {
            "version": "reference-agent-local-v1",
            "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
            "allowed_tool_names": ["read_reference"],
        },
        "runtime_scope": {"tenant_id": "local-tenant", "project_id": "reference-project"},
        "runtime_context_hash": runtime_context_hash(context),
    }


def test_get_agent_accepts_explicit_fake_model_and_runtime_context() -> None:
    graph = asyncio.run(
        agent.get_agent(_config(BindableFakeChatModel(responses=["runtime-ok"])))
    )

    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]},
            context=RuntimeContext(),
        )
    )

    assert result["messages"][-1].content == "runtime-ok"


def test_authenticated_identity_and_policy_are_used_per_run() -> None:
    principal, policy = agent._runtime_identity_and_policy(
        {
            "configurable": {
                "langgraph_auth_user": {
                    "runtime_principal": {
                        "user_id": "user-b",
                        "tenant_id": "tenant-b",
                        "project_id": "project-b",
                        "role": "operator",
                        "permissions": ["runtime.tool.read"],
                    },
                    "runtime_policy": {
                        "version": "policy-b",
                        "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
                        "allowed_tool_names": ["read_reference"],
                    },
                    "runtime_scope": {"tenant_id": "tenant-b", "project_id": "project-b"},
                    "runtime_context_hash": runtime_context_hash(None),
                },
            }
        }
    )

    assert principal.tenant_id == "tenant-b"
    assert principal.project_id == "project-b"
    assert policy.version == "policy-b"


def test_authenticated_identity_and_policy_must_be_complete() -> None:
    with pytest.raises(RuntimeAuthError):
        agent._runtime_identity_and_policy(
            {
                "configurable": {
                "langgraph_auth_user": {
                    "runtime_principal": {
                        "user_id": "user-b",
                        "tenant_id": "tenant-b",
                        "project_id": "project-b",
                        "role": "operator",
                        "permissions": [],
                    },
                }
                }
            }
        )


def test_context_override_is_resolved_before_model_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_build_model(config: object) -> BindableFakeChatModel:
        captured["config"] = config
        return BindableFakeChatModel(responses=["override-ok"])

    monkeypatch.setattr(agent, "build_model", fake_build_model)
    graph = asyncio.run(
        agent.get_agent(
            {
                "context": {"temperature": 0},
                "configurable": {
                    "langgraph_auth_user": {
                        **_auth_user(),
                        "runtime_context_hash": runtime_context_hash({"temperature": 0}),
                    },
                    "_runtime_test_local_auth": True,
                },
            }
        )
    )
    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]},
            context=RuntimeContext(temperature=0),
        )
    )

    assert captured["config"].temperature == 0.0  # type: ignore[union-attr]
    assert result["messages"][-1].content == "override-ok"


def test_reference_agent_topology_is_stable_across_runtime_bindings() -> None:
    first = asyncio.run(
        agent.get_agent(_config(BindableFakeChatModel(responses=["first"])))
    )
    second = asyncio.run(
        agent.get_agent(_config(BindableFakeChatModel(responses=["second"])))
    )

    first_graph = first.get_graph()
    second_graph = second.get_graph()
    assert first is not second
    assert set(first_graph.nodes) == set(second_graph.nodes)
    assert {(edge.source, edge.target) for edge in first_graph.edges} == {
        (edge.source, edge.target) for edge in second_graph.edges
    }
    assert first.input_schema.model_json_schema() == second.input_schema.model_json_schema()
    assert first.output_schema.model_json_schema() == second.output_schema.model_json_schema()


def test_context_policy_violation_fails_before_fake_model_use() -> None:
    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(
            agent.get_agent(
                _config(
                    BindableFakeChatModel(responses=["must-not-run"]),
                    {"model_id": "openai:gpt-5.5"},
                )
                | {"context": {"model_id": "openai:gpt-5.5"}}
            )
        )

    assert error.value.code == "runtime.model.not_allowed"


def test_default_path_does_not_fallback_to_fake_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_provider(_: object) -> FakeListChatModel:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")

    monkeypatch.setattr(agent, "build_model", missing_provider)
    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(agent.get_agent({"configurable": {"langgraph_auth_user": _auth_user()}}))

    assert error.value.code == "runtime.model.initialization_failed"


def test_agent_requires_authenticated_server_facts() -> None:
    with pytest.raises(RuntimeAuthError) as error:
        asyncio.run(agent.get_agent({}))
    assert error.value.code == "runtime.auth.missing_principal"


def test_agent_rejects_untrusted_resource_injection() -> None:
    with pytest.raises(RuntimeResolutionError, match="runtime.configurable.forbidden"):
        asyncio.run(
            agent.get_agent(
                {
                    "configurable": {
                        "langgraph_auth_user": _auth_user(),
                        "backend": object(),
                    }
                }
            )
        )


def test_reference_tool_is_explicit_and_read_only() -> None:
    assert read_reference.invoke({"topic": "runtime"}) == "reference note: runtime"
