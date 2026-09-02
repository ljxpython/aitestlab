"""Deterministic Thread Workspace graph for R6 acceptance."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.pregel import Pregel

from runtime_service.runtime import (
    RuntimeErrorBase,
    RuntimeResolutionError,
    resolve_resource_binding,
    verified_delegation_from_user,
)
from runtime_service.services.workspace_policy import (
    WorkspaceLimits,
    resolve_workspace_path,
    validate_workspace_write,
    workspace_write_lock,
)


class WorkspaceState(TypedDict, total=False):
    operation: str
    path: str
    content: str
    observed: str


def _configurable(config: RunnableConfig) -> Mapping[str, object]:
    value = config.get("configurable") or {}
    if not isinstance(value, Mapping):
        raise RuntimeResolutionError("runtime.workspace.recovery_failed", "configurable")
    return value


def _workspace(config: RunnableConfig):
    configurable = _configurable(config)
    user = configurable.get("langgraph_auth_user")
    try:
        facts = verified_delegation_from_user(user)
        binding = resolve_resource_binding(config, facts.principal, "workspace")
        thread_id = configurable.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            raise ValueError("thread_id is required")
        base_value = os.getenv("GRAPHHARBOR_WORKSPACE_ROOT", "").strip()
        if not base_value:
            raise ValueError("workspace root is not configured")
        base = Path(base_value)
        if not base.is_absolute():
            raise ValueError("workspace root must be absolute")
        from langgraph_runtime_pg.deepagent_workspace import build_deepagent_workspace

        return build_deepagent_workspace(
            base,
            tenant_id=facts.principal.tenant_id,
            project_id=facts.principal.project_id,
            thread_id=binding.resource_id,
        )
    except Exception as exc:
        if isinstance(exc, RuntimeErrorBase):
            raise
        raise RuntimeResolutionError("runtime.workspace.recovery_failed") from exc


async def workspace_io(state: WorkspaceState, config: RunnableConfig) -> WorkspaceState:
    """Rebuild the thread backend for every execution and fail closed on errors."""

    workspace = _workspace(config)
    path = state.get("path", "/state.txt")
    if not isinstance(path, str):
        raise RuntimeResolutionError("runtime.workspace.recovery_failed", "path")

    operation = state.get("operation", "write")
    try:
        if operation == "write":
            content = state.get("content", "")
            with workspace_write_lock(workspace.root):
                validate_workspace_write(
                    workspace.root,
                    path,
                    content,
                    limits=WorkspaceLimits.from_env(),
                )
                result = workspace.backend.write(path, content)
        elif operation == "read":
            resolve_workspace_path(workspace.root, path)
            result = await workspace.backend.aread(path)
        else:
            raise RuntimeResolutionError("runtime.workspace.recovery_failed", "operation")
    except (TypeError, ValueError) as exc:
        raise RuntimeResolutionError("runtime.workspace.recovery_failed", "path") from exc
    if operation == "write":
        if result.error:
            raise RuntimeResolutionError("runtime.workspace.recovery_failed")
        return {"observed": "written", "path": path}
    if operation == "read":
        if result.error or result.file_data is None:
            raise RuntimeResolutionError("runtime.workspace.recovery_failed")
        return {"observed": str(result.file_data["content"]), "path": path}


_builder = StateGraph(WorkspaceState)
_builder.add_node("workspace_io", workspace_io)
_builder.add_edge(START, "workspace_io")
_builder.add_edge("workspace_io", END)
_graph = _builder.compile()


async def get_agent(_config: RunnableConfig) -> Pregel:
    return _graph


__all__ = ["get_agent", "workspace_io"]
