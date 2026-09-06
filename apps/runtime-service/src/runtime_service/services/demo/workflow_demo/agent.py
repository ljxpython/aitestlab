"""Composition root for the model-backed workflow agent."""

from __future__ import annotations

from collections.abc import Mapping
import os

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.middlewares import ModelCallTimeoutMiddleware
from runtime_service.observability import with_langfuse_tracing
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeScope,
    build_model,
    parse_runtime_context,
    reject_untrusted_configurable,
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.runtime.errors import RuntimeAuthError, RuntimeResolutionError
from runtime_service.services.demo.workflow_demo.workflow import build_graph


@tool
def read_reference(topic: str) -> str:
    """Return a short reference note for a named topic."""

    return f"reference note: {topic.strip()}"

_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=(
        "You are Workflow Demo, a real model-backed Runtime Agent. "
        "Answer the user's current question clearly and naturally."
    ),
    prompt_version="workflow-demo-v2",
    optional_tool_names=("read_reference",),
)
_TOOL_PERMISSIONS = {"read_reference": "runtime.tool.read"}


def _local_test_facts() -> VerifiedDelegation:
    return VerifiedDelegation(
        RuntimePrincipal(
            "local-user",
            "local-tenant",
            "workflow-project",
            "developer",
            ("runtime.tool.read",),
        ),
        RuntimePolicy(
            "workflow-demo-local-v2",
            (_DEFAULTS.model_id,),
            _DEFAULTS.optional_tool_names,
        ),
        RuntimeScope("local-tenant", "workflow-project"),
        "",
    )


def _configurable(config: RunnableConfig) -> Mapping[str, object]:
    value = config.get("configurable") or {}
    if not isinstance(value, Mapping):
        raise RuntimeAuthError("runtime.auth.missing_principal")
    reject_untrusted_configurable(value)
    return value


def _facts(config: RunnableConfig) -> tuple[VerifiedDelegation, bool]:
    configurable = _configurable(config)
    local = configurable.get("_runtime_test_local_auth") is True
    candidate = configurable.get("_runtime_model")
    auth_user = configurable.get("langgraph_auth_user")
    if auth_user is not None:
        return verified_delegation_from_user(auth_user), False
    if local or candidate is not None:
        return _local_test_facts(), True
    raise RuntimeAuthError("runtime.auth.missing_principal")


def _runtime_model(config: RunnableConfig, *, local: bool) -> BaseChatModel | None:
    candidate = _configurable(config).get("_runtime_model")
    if candidate is None:
        return None
    if not local:
        raise RuntimeAuthError("runtime.auth.test_adapter_forbidden")
    if not isinstance(candidate, BaseChatModel):
        raise RuntimeResolutionError("runtime.model.invalid_test_adapter", "_runtime_model")
    return candidate


async def _catalog_connection(
    config: RunnableConfig,
    *,
    model_id: str,
    project_id: str,
) -> dict[str, str] | None:
    configurable = _configurable(config)
    reference = configurable.get("_runtime_model_ref")
    endpoint = os.getenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", "").strip()
    if not reference or not endpoint or not project_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                endpoint,
                headers={
                    "x-runtime-model-ref": str(reference),
                    "x-project-id": project_id,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id") from exc
    required = ("provider", "base_url", "protocol", "model", "api_key")
    if not isinstance(payload, dict) or payload.get("model_id") != model_id:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")
    if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")
    return {key: payload[key] for key in required} | {"model_id": model_id}


async def get_agent(config: RunnableConfig) -> Pregel:
    """Build the real model-backed workflow Agent with optional HITL routing."""

    facts, local = _facts(config)
    context = parse_runtime_context(config.get("context"))
    raw_context = config.get("context")
    if raw_context is not None and facts.context_hash != runtime_context_hash(context):
        raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
    resolved = resolve_runtime_config(
        principal=facts.principal,
        context=context,
        policy=facts.policy,
        defaults=_DEFAULTS,
        tool_permissions=_TOOL_PERMISSIONS,
    )
    injected = _runtime_model(config, local=local)
    connection = None if injected is not None else await _catalog_connection(
        config,
        model_id=resolved.model_id,
        project_id=facts.principal.project_id,
    )
    model = injected or build_model(resolved, connection=connection)

    model_agent = create_agent(
        model=model,
        tools=[read_reference],
        system_prompt=_DEFAULTS.system_prompt,
        middleware=[
            ModelCallLimitMiddleware(run_limit=10, exit_behavior="end"),
            ModelCallTimeoutMiddleware(timeout_seconds=30),
        ],
        context_schema=RuntimeContext,
        name="workflow_demo_model",
    )
    bound_config = dict(config)
    bound_configurable = dict(bound_config.get("configurable") or {})
    bound_configurable.pop("_runtime_model", None)
    bound_configurable.pop("_runtime_test_local_auth", None)
    bound_config["configurable"] = bound_configurable
    graph = build_graph(
        model_agent,
        model_config=bound_config,
        runtime_context=context,
    )
    return with_langfuse_tracing(
        graph,
        bound_config,
        graph_id="workflow_demo",
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
