"""Composition root for the service-private fake MCP demo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.pregel import Pregel

from runtime_service.middlewares import RuntimeConfigMiddleware
from runtime_service.observability import with_langfuse_tracing
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeAuthError,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeScope,
    build_model,
    parse_runtime_context,
    reject_untrusted_configurable,
    resolve_runtime_config,
    verified_delegation_from_user,
)
from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.services.demo.mcp_demo.loader import load_mcp_tools


class _DemoChatModel(FakeListChatModel):
    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt="Use only the explicitly authorized MCP tools.",
    prompt_version="mcp-demo-v1",
    optional_tool_names=("mcp_read",),
)
_TOOL_PERMISSIONS = {"mcp_read": "runtime.tool.read"}


def _local_test_facts() -> VerifiedDelegation:
    return VerifiedDelegation(
        RuntimePrincipal(
            "local-user",
            "local-tenant",
            "mcp-project",
            "developer",
            ("runtime.tool.read",),
        ),
        RuntimePolicy(
            "mcp-demo-local-v1",
            (_DEFAULTS.model_id,),
            _DEFAULTS.optional_tool_names,
        ),
        RuntimeScope("local-tenant", "mcp-project"),
        "",
    )


def _configurable(config: RunnableConfig) -> Mapping[str, object]:
    value = config.get("configurable") or {}
    if not isinstance(value, Mapping):
        raise RuntimeAuthError("runtime.auth.missing_principal")
    reject_untrusted_configurable(value)
    return value


def _runtime_facts(config: RunnableConfig) -> tuple[VerifiedDelegation, bool]:
    configurable = _configurable(config)
    local = configurable.get("_runtime_test_local_auth") is True
    candidate = configurable.get("_runtime_test_model")
    if candidate is not None and not local:
        raise RuntimeAuthError("runtime.auth.test_adapter_forbidden")
    auth_user = configurable.get("langgraph_auth_user")
    if auth_user is not None:
        return verified_delegation_from_user(auth_user), False
    if local:
        return _local_test_facts(), True
    raise RuntimeAuthError("runtime.auth.missing_principal")


def _runtime_model(config: RunnableConfig, *, local: bool) -> BaseChatModel | None:
    candidate = _configurable(config).get("_runtime_test_model")
    if candidate is None:
        return None
    if not local:
        raise RuntimeAuthError("runtime.auth.test_adapter_forbidden")
    if not isinstance(candidate, BaseChatModel):
        raise RuntimeAuthError("runtime.model.invalid_test_adapter")
    return candidate


async def get_agent(config: RunnableConfig) -> Pregel:
    """Load fake MCP tools before creating the agent graph."""

    facts, local = _runtime_facts(config)
    configurable = _configurable(config)
    conflict = bool(configurable.get("_runtime_test_mcp_conflict")) if local else False
    context = parse_runtime_context(config.get("context"))
    resolved = resolve_runtime_config(
        principal=facts.principal,
        context=context,
        policy=facts.policy,
        defaults=_DEFAULTS,
        tool_permissions=_TOOL_PERMISSIONS,
    )
    model = _runtime_model(config, local=local) or build_model(resolved)
    tools = (
        await load_mcp_tools(
            allowed_names=resolved.required_tool_names + resolved.optional_tool_names,
            conflict=conflict,
            config=None if local else config,
            principal=None if local else facts.principal,
        )
        if resolved.optional_tool_names
        else []
    )
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=_DEFAULTS.system_prompt,
        middleware=[
            RuntimeConfigMiddleware(
                principal=facts.principal,
                policy=facts.policy,
                defaults=_DEFAULTS,
                base_model=model,
                tool_permissions=_TOOL_PERMISSIONS,
                local_fallback=local,
            )
        ],
        context_schema=RuntimeContext,
        name="mcp_demo",
    )
    bound_config = dict(config)
    bound_configurable = dict(bound_config.get("configurable") or {})
    bound_configurable.pop("_runtime_test_model", None)
    bound_configurable.pop("_runtime_test_local_auth", None)
    bound_configurable.pop("_runtime_test_mcp_conflict", None)
    bound_config["configurable"] = bound_configurable
    return with_langfuse_tracing(
        agent,
        bound_config,
        graph_id="mcp_demo",
        trusted_metadata={
            "user_id": facts.principal.user_id,
            "tenant_id": facts.principal.tenant_id,
            "project_id": facts.principal.project_id,
            "model_id": resolved.model_id,
            "config_hash": resolved.config_hash,
            "prompt_version": resolved.prompt_version,
            "prompt_hash": resolved.prompt_hash,
            "policy_version": resolved.policy_version,
            "request_id": facts.request_id,
            "platform_trace_id": facts.platform_trace_id,
        },
    )


__all__ = ["get_agent"]
