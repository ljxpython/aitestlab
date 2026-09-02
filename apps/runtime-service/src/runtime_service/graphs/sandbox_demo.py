"""R6-only Sandbox reconnect probe; not part of the production graph set."""

from __future__ import annotations

from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.pregel import Pregel

from runtime_service.runtime import (
    RuntimeErrorBase,
    RuntimeResolutionError,
    verified_delegation_from_user,
)
from runtime_service.services.sandbox import reconnect_langsmith_sandbox


class SandboxState(TypedDict, total=False):
    observed: str


async def sandbox_probe(state: SandboxState, config: RunnableConfig) -> SandboxState:
    user = (config.get("configurable") or {}).get("langgraph_auth_user")
    try:
        facts = verified_delegation_from_user(user)
        sandbox = await reconnect_langsmith_sandbox(config, facts.principal)
        try:
            result = await sandbox.aexecute("printf r6-sandbox-ok")
        finally:
            await sandbox.aclose()
    except Exception as exc:
        if isinstance(exc, RuntimeErrorBase):
            raise
        raise RuntimeResolutionError("runtime.sandbox.recovery_failed") from exc
    if result.exit_code not in (None, 0) or result.output != "r6-sandbox-ok":
        raise RuntimeResolutionError("runtime.sandbox.recovery_failed")
    return {"observed": result.output}


_builder = StateGraph(SandboxState)
_builder.add_node("sandbox_probe", sandbox_probe)
_builder.add_edge(START, "sandbox_probe")
_builder.add_edge("sandbox_probe", END)
_graph = _builder.compile()


async def get_agent(_config: RunnableConfig) -> Pregel:
    return _graph


__all__ = ["get_agent", "sandbox_probe"]
