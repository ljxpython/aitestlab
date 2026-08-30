"""Composition root for the deterministic workflow demo."""

from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.services.workflow_demo.workflow import builder

_AGENT = builder.compile()


async def get_agent(config: RunnableConfig) -> Pregel:
    """Return the compiled workflow graph without external side effects."""

    return _AGENT


__all__ = ["get_agent"]
