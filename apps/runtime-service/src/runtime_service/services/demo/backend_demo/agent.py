"""Composition root for the StateBackend isolation demo."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemMiddleware, FilesystemPermission
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.pregel import Pregel

from runtime_service.middlewares import RuntimeConfigMiddleware
from runtime_service.observability import with_langfuse_tracing
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeAuthError,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeResolutionError,
    RuntimeScope,
    build_model,
    parse_runtime_context,
    reject_untrusted_configurable,
    resolve_resource_binding,
    resolve_runtime_config,
    verified_delegation_from_user,
)
from runtime_service.runtime.auth import VerifiedDelegation


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
    system_prompt="Use only the Thread-scoped virtual Workspace tools.",
    prompt_version="backend-demo-v1",
    optional_tool_names=(
        "delete",
        "edit_file",
        "glob",
        "grep",
        "ls",
        "read_file",
        "write_file",
    ),
)
_TOOL_PERMISSIONS = {
    name: "runtime.tool.write"
    if name in {"delete", "edit_file", "write_file"}
    else "runtime.tool.read"
    for name in _DEFAULTS.optional_tool_names
}
_FILESYSTEM_TOOLS = [
    "ls",
    "read_file",
    "write_file",
    "edit_file",
    "delete",
    "glob",
    "grep",
]
_SKILL_READ_ONLY = [
    FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny")
]

_NO_DEFAULT_SUBAGENT = HarnessProfile(
    general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)
)
register_harness_profile("deepseek:DeepSeek-V4-Flash", _NO_DEFAULT_SUBAGENT)
register_harness_profile("bindablefakechatmodel", _NO_DEFAULT_SUBAGENT)
register_harness_profile("bindablefakemessageschatmodel", _NO_DEFAULT_SUBAGENT)


def _local_test_facts() -> VerifiedDelegation:
    return VerifiedDelegation(
        RuntimePrincipal(
            "local-user",
            "local-tenant",
            "backend-project",
            "developer",
            tuple(sorted(set(_TOOL_PERMISSIONS.values()))),
        ),
        RuntimePolicy(
            "backend-demo-local-v1",
            (_DEFAULTS.model_id,),
            _DEFAULTS.optional_tool_names,
        ),
        RuntimeScope("local-tenant", "backend-project"),
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
        raise RuntimeResolutionError(
            "runtime.model.invalid_test_adapter", "_runtime_test_model"
        )
    return candidate


def _runtime_checkpointer(
    config: RunnableConfig, *, local: bool
) -> BaseCheckpointSaver | None:
    candidate = _configurable(config).get("_runtime_test_checkpointer")
    if candidate is None:
        return None
    if not local:
        raise RuntimeAuthError("runtime.auth.test_adapter_forbidden")
    if not isinstance(candidate, BaseCheckpointSaver):
        raise RuntimeResolutionError(
            "runtime.checkpointer.invalid", "_runtime_test_checkpointer"
        )
    return candidate


async def get_agent(config: RunnableConfig) -> Pregel:
    """Create a fresh StateBackend bound to this graph instance."""

    facts, local = _runtime_facts(config)
    configurable = _configurable(config)
    binding = None
    if not local:
        binding = resolve_resource_binding(config, facts.principal, "backend")
        if binding.provider != "graphharbor_workspace":
            raise RuntimeResolutionError("runtime.backend.recovery_failed")
        thread_id = str(configurable.get("thread_id", ""))
        if not thread_id:
            raise RuntimeResolutionError("runtime.backend.recovery_failed")
        root_value = os.environ.get("GRAPHHARBOR_WORKSPACE_ROOT", "").strip()
        if not root_value or not Path(root_value).is_absolute():
            raise RuntimeResolutionError("runtime.backend.recovery_failed")
    resolved = resolve_runtime_config(
        principal=facts.principal,
        context=parse_runtime_context(config.get("context")),
        policy=facts.policy,
        defaults=_DEFAULTS,
        tool_permissions=_TOOL_PERMISSIONS,
    )
    model = _runtime_model(config, local=local) or build_model(resolved)
    if local:
        backend = StateBackend()
    else:
        root_value = os.environ.get("GRAPHHARBOR_WORKSPACE_ROOT", "").strip()
        from langgraph_runtime_pg.deepagent_workspace import build_deepagent_workspace

        backend = build_deepagent_workspace(
            Path(root_value),
            tenant_id=facts.principal.tenant_id,
            project_id=facts.principal.project_id,
            thread_id=binding.resource_id,
        ).backend
    agent = create_deep_agent(
        model=model,
        backend=backend,
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                tools=_FILESYSTEM_TOOLS,
                _permissions=_SKILL_READ_ONLY,
            ),
            RuntimeConfigMiddleware(
                principal=facts.principal,
                policy=facts.policy,
                defaults=_DEFAULTS,
                base_model=model,
                tool_permissions=_TOOL_PERMISSIONS,
                local_fallback=local,
            ),
        ],
        context_schema=RuntimeContext,
        checkpointer=_runtime_checkpointer(config, local=local),
        system_prompt=_DEFAULTS.system_prompt,
        name="backend_demo",
    )
    bound_config = dict(config)
    bound_configurable = dict(bound_config.get("configurable") or {})
    bound_configurable.pop("_runtime_test_model", None)
    bound_configurable.pop("_runtime_test_checkpointer", None)
    bound_configurable.pop("_runtime_test_local_auth", None)
    bound_config["configurable"] = bound_configurable
    return with_langfuse_tracing(
        agent,
        bound_config,
        graph_id="backend_demo",
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
