"""Composition root for the Runtime-aware reference agent."""

from __future__ import annotations

from collections.abc import Mapping

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
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
    RuntimeScope,
    build_model,
    parse_runtime_context,
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.runtime.errors import RuntimeAuthError

_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="reference-agent-v3",
    optional_tool_names=("read_reference",),
)
_TOOL_PERMISSIONS = {"read_reference": "runtime.tool.read"}


def _local_test_facts() -> VerifiedDelegation:
    return VerifiedDelegation(
        RuntimePrincipal(
            "local-user",
            "local-tenant",
            "reference-project",
            "developer",
            ("runtime.tool.read",),
        ),
        RuntimePolicy(
            "reference-agent-local-v1",
            ("deepseek:DeepSeek-V4-Flash",),
            ("read_reference",),
        ),
        RuntimeScope("local-tenant", "reference-project"),
        "",
    )


def _runtime_model(config: RunnableConfig) -> BaseChatModel | None:
    configurable = config.get("configurable") or {}
    candidate = (
        configurable.get("_runtime_model")
        if isinstance(configurable, Mapping)
        else None
    )
    return candidate if isinstance(candidate, BaseChatModel) else None


def _runtime_fallback_model(config: RunnableConfig) -> BaseChatModel | None:
    configurable = config.get("configurable") or {}
    candidate = (
        configurable.get("_runtime_fallback_model")
        if isinstance(configurable, Mapping)
        else None
    )
    return candidate if isinstance(candidate, BaseChatModel) else None


def _runtime_facts(config: RunnableConfig) -> VerifiedDelegation:
    configurable = config.get("configurable") or {}
    if not isinstance(configurable, Mapping):
        raise RuntimeAuthError("runtime.auth.missing_principal")
    auth_user = configurable.get("langgraph_auth_user")
    if auth_user is not None:
        return verified_delegation_from_user(auth_user)
    if configurable.get("_runtime_model") is not None:
        return _local_test_facts()
    raise RuntimeAuthError("runtime.auth.missing_principal")


def _runtime_identity_and_policy(
    config: RunnableConfig,
) -> tuple[RuntimePrincipal, RuntimePolicy]:
    facts = _runtime_facts(config)
    return facts.principal, facts.policy


async def get_agent(config: RunnableConfig) -> Pregel:
    """Resolve Runtime values and return the compiled reference graph."""

    runtime_model = _runtime_model(config)
    configurable = config.get("configurable") or {}
    local_test_auth = (
        isinstance(configurable, Mapping)
        and configurable.get("_runtime_test_local_auth") is True
    )
    facts = _runtime_facts(config)
    principal, policy = facts.principal, facts.policy
    raw_context = config.get("context")
    context = parse_runtime_context(raw_context)
    if raw_context is not None and facts.context_hash != runtime_context_hash(context):
        raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
    resolved = resolve_runtime_config(
        principal=principal,
        context=context,
        policy=policy,
        defaults=_DEFAULTS,
        tool_permissions=_TOOL_PERMISSIONS,
    )
    model = runtime_model or build_model(resolved)
    fallback_model = _runtime_fallback_model(config) if runtime_model is not None else None
    model_retry_enabled = (
        runtime_model is not None
        and isinstance(configurable, Mapping)
        and configurable.get("_runtime_model_retry") is True
    )

    def _tool_error(exc: Exception, request) -> str | None:
        if isinstance(exc, (ConnectionError, ValueError)):
            return (
                f"Tool `{request.tool_call['name']}` failed with {type(exc).__name__}; "
                "fix the input and retry."
            )
        return None

    middleware = [
        RuntimeConfigMiddleware(
            principal=principal,
            policy=policy,
            defaults=_DEFAULTS,
            base_model=model,
            model_builder=build_model,
            tool_permissions=_TOOL_PERMISSIONS,
            local_fallback=runtime_model is not None or local_test_auth,
        ),
        ModelCallLimitMiddleware(run_limit=10, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=10, exit_behavior="error"),
        ToolErrorMiddleware(on_error=_tool_error, tools=["read_reference"]),
        ToolRetryMiddleware(
            max_retries=1,
            tools=["read_reference"],
            retry_on=(ConnectionError,),
            on_failure="error",
            initial_delay=0,
            jitter=False,
        ),
        *(
            [ModelFallbackMiddleware(fallback_model)]
            if fallback_model is not None
            else []
        ),
        *(
            [
                ModelRetryMiddleware(
                    max_retries=1,
                    retry_on=(ConnectionError,),
                    on_failure="error",
                    initial_delay=0,
                    jitter=False,
                )
            ]
            if model_retry_enabled
            else []
        ),
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

    bound_config = dict(config)
    configurable = dict(bound_config.get("configurable") or {})
    configurable.pop("_runtime_model", None)
    configurable.pop("_runtime_fallback_model", None)
    configurable.pop("_runtime_model_retry", None)
    bound_config["configurable"] = configurable
    return with_langfuse_tracing(
        agent,
        bound_config,
        graph_id="reference_agent",
        trusted_metadata={
            "user_id": principal.user_id,
            "tenant_id": principal.tenant_id,
            "project_id": principal.project_id,
            "model_id": resolved.model_id,
            "config_hash": resolved.config_hash,
            "prompt_version": resolved.prompt_version,
            "prompt_hash": resolved.prompt_hash,
            "policy_version": resolved.policy_version,
        },
    )


__all__ = ["get_agent"]
