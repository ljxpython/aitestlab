"""Composition root for the deterministic unrecoverable Tool failure demo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypedDict

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.pregel import Pregel

from runtime_service.middlewares import RuntimeConfigMiddleware
from runtime_service.observability import with_langfuse_tracing
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    parse_runtime_context,
    resolve_runtime_config,
    verified_delegation_from_user,
)
from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.runtime.errors import RuntimeAuthError
from runtime_service.services.demo.failure_demo.tools import slow_tool, unrecoverable_tool


class _ToolCallingChatModel(FakeMessagesListChatModel):
    """Request one Tool deterministically without an external model provider."""

    def __init__(self, name: str, args: dict[str, object]) -> None:
        super().__init__(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": name,
                            "args": args,
                            "id": f"{name}-call",
                        }
                    ],
                )
            ]
        )

    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


class _TimeoutState(TypedDict, total=False):
    messages: list[object]


async def _run_slow_tool(_: _TimeoutState) -> dict[str, object]:
    await slow_tool.ainvoke({"delay_seconds": 30})
    return {}


_DEFAULTS = AgentDefaults(
    model_id="runtime:failure-demo",
    system_prompt="Call unrecoverable_tool exactly once.",
    prompt_version="failure-demo-v1",
    optional_tool_names=("unrecoverable_tool",),
)
_TIMEOUT_DEFAULTS = AgentDefaults(
    model_id="runtime:timeout-demo",
    system_prompt="Call slow_tool exactly once.",
    prompt_version="timeout-demo-v1",
    optional_tool_names=("slow_tool",),
)


def _runtime_facts(config: RunnableConfig) -> VerifiedDelegation:
    configurable = config.get("configurable") or {}
    if not isinstance(configurable, Mapping):
        raise RuntimeAuthError("runtime.auth.missing_principal")
    user = configurable.get("langgraph_auth_user")
    if user is None:
        raise RuntimeAuthError("runtime.auth.missing_principal")
    return verified_delegation_from_user(user)


def _build_agent(
    config: RunnableConfig,
    *,
    defaults: AgentDefaults,
    model: BaseChatModel,
    tool: BaseTool,
    permission: str,
    graph_id: str,
) -> Pregel:
    facts = _runtime_facts(config)
    resolved = resolve_runtime_config(
        principal=facts.principal,
        context=parse_runtime_context(config.get("context")),
        policy=facts.policy,
        defaults=defaults,
        tool_permissions={tool.name: permission},
    )
    agent = create_agent(
        model=model,
        tools=[tool],
        system_prompt=defaults.system_prompt,
        middleware=[
            RuntimeConfigMiddleware(
                principal=facts.principal,
                policy=facts.policy,
                defaults=defaults,
                base_model=model,
                tool_permissions={tool.name: permission},
                local_fallback=True,
            )
        ],
        context_schema=RuntimeContext,
        name=graph_id,
    )
    return with_langfuse_tracing(
        agent,
        config,
        graph_id=graph_id,
        trusted_metadata={
            "user_id": facts.principal.user_id,
            "tenant_id": facts.principal.tenant_id,
            "project_id": facts.principal.project_id,
            "model_id": resolved.model_id,
            "config_hash": resolved.config_hash,
            "prompt_version": resolved.prompt_version,
            "prompt_hash": resolved.prompt_hash,
            "policy_version": resolved.policy_version,
        },
    )


async def get_agent(config: RunnableConfig) -> Pregel:
    """Return a graph whose Tool failure must become a failed Run."""

    return _build_agent(
        config,
        defaults=_DEFAULTS,
        model=_ToolCallingChatModel(
            "unrecoverable_tool", {"reason": "r6 acceptance"}
        ),
        tool=unrecoverable_tool,
        permission="runtime.tool.write",
        graph_id="failure_demo",
    )


async def get_timeout_agent(config: RunnableConfig) -> Pregel:
    """Return a graph that blocks in a cancellable Tool call."""

    facts = _runtime_facts(config)
    resolved = resolve_runtime_config(
        principal=facts.principal,
        context=parse_runtime_context(config.get("context")),
        policy=facts.policy,
        defaults=_TIMEOUT_DEFAULTS,
        tool_permissions={"slow_tool": "runtime.tool.write"},
    )
    builder = StateGraph(_TimeoutState)
    builder.add_node("slow_tool", _run_slow_tool)
    builder.add_edge(START, "slow_tool")
    builder.add_edge("slow_tool", END)
    return with_langfuse_tracing(
        builder.compile(),
        config,
        graph_id="timeout_demo",
        trusted_metadata={
            "user_id": facts.principal.user_id,
            "tenant_id": facts.principal.tenant_id,
            "project_id": facts.principal.project_id,
            "model_id": resolved.model_id,
            "config_hash": resolved.config_hash,
            "prompt_version": resolved.prompt_version,
            "prompt_hash": resolved.prompt_hash,
            "policy_version": resolved.policy_version,
        },
    )


__all__ = ["get_agent", "get_timeout_agent"]
