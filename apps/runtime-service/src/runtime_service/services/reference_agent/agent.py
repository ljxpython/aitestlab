"""Composition root for the Runtime-aware reference agent."""

from __future__ import annotations

from collections.abc import Mapping

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.services.reference_agent.prompts import SYSTEM_PROMPT
from runtime_service.services.reference_agent.tools import read_reference
from runtime_service.middlewares import ModelCallTimeoutMiddleware, RuntimeConfigMiddleware
from runtime_service.observability import with_langfuse_tracing
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    build_model,
    parse_runtime_context,
    resolve_runtime_config,
)

_PRINCIPAL = RuntimePrincipal(
    user_id="local-user",
    tenant_id="local-tenant",
    project_id="reference-project",
    role="developer",
    permissions=(),
)
_POLICY = RuntimePolicy(
    version="reference-agent-local-v1",
    allowed_model_ids=("deepseek:DeepSeek-V4-Flash",),
    allowed_tool_names=("read_reference",),
)
_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="reference-agent-v3",
    optional_tool_names=("read_reference",),
)
_STATIC_AGENT: Pregel | None = None


def _runtime_model(config: RunnableConfig) -> BaseChatModel | None:
    configurable = config.get("configurable") or {}
    candidate = configurable.get("_runtime_model") if isinstance(configurable, Mapping) else None
    return candidate if isinstance(candidate, BaseChatModel) else None


async def get_agent(config: RunnableConfig) -> Pregel:
    """Resolve Runtime values and return the compiled reference graph."""

    global _STATIC_AGENT
    context = parse_runtime_context(config.get("context"))
    resolved = resolve_runtime_config(
        principal=_PRINCIPAL,
        context=context,
        policy=_POLICY,
        defaults=_DEFAULTS,
    )
    runtime_model = _runtime_model(config)
    has_context_override = config.get("context") is not None
    if runtime_model is None and not has_context_override and _STATIC_AGENT is not None:
        agent = _STATIC_AGENT
    else:
        model = runtime_model or build_model(resolved)
        middleware = [
            RuntimeConfigMiddleware(
                principal=_PRINCIPAL,
                policy=_POLICY,
                defaults=_DEFAULTS,
                base_model=model,
                model_builder=build_model,
            ),
            ModelCallLimitMiddleware(run_limit=10, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=10, exit_behavior="error"),
            ModelCallTimeoutMiddleware(timeout_seconds=30),
        ]
        agent = create_agent(
            model=model,
            tools=[read_reference],
            system_prompt=_DEFAULTS.system_prompt,
            middleware=middleware,
            context_schema=RuntimeContext,
            name="reference_agent",
        )
        if runtime_model is None and not has_context_override:
            _STATIC_AGENT = agent

    bound_config = dict(config)
    configurable = dict(bound_config.get("configurable") or {})
    configurable.pop("_runtime_model", None)
    bound_config["configurable"] = configurable
    return with_langfuse_tracing(
        agent,
        bound_config,
        graph_id="reference_agent",
        trusted_metadata={
            "user_id": _PRINCIPAL.user_id,
            "tenant_id": _PRINCIPAL.tenant_id,
            "project_id": _PRINCIPAL.project_id,
            "model_id": resolved.model_id,
            "config_hash": resolved.config_hash,
            "prompt_version": resolved.prompt_version,
            "prompt_hash": resolved.prompt_hash,
            "policy_version": resolved.policy_version,
        },
    )


__all__ = ["get_agent"]
