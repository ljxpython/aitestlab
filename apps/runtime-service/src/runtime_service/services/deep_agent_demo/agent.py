"""Composition root for the Deep Agents capability demo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from deepagents import SubAgent, create_deep_agent
from deepagents.backends import StateBackend
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.pregel import Pregel

from runtime_service.observability import with_langfuse_tracing

class _DemoChatModel(FakeListChatModel):
    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


_SKILL_DIR = Path(__file__).with_name("skills") / "runtime-notes"
_DEFAULT_MODEL = _DemoChatModel(responses=["deep agent demo response"])


async def get_agent(config: RunnableConfig) -> Pregel:
    """Create a Deep Agent with explicitly scoped backend, skill, and subagent."""

    configurable = config.get("configurable") or {}
    candidate = configurable.get("_runtime_model") if isinstance(configurable, Mapping) else None
    model = candidate if isinstance(candidate, BaseChatModel) else _DEFAULT_MODEL
    subagent: SubAgent = {
        "name": "summarizer",
        "description": "Summarize the current task without filesystem or network access.",
        "system_prompt": "Return a concise summary. Do not perform side effects.",
        "model": model,
        "tools": [],
    }
    agent = create_deep_agent(
        model=model,
        backend=StateBackend(),
        skills=[str(_SKILL_DIR)],
        subagents=[subagent],
        name="deep_agent_demo",
    )
    bound_config = dict(config)
    bound_configurable = dict(bound_config.get("configurable") or {})
    bound_configurable.pop("_runtime_model", None)
    bound_config["configurable"] = bound_configurable
    return with_langfuse_tracing(agent, bound_config, graph_id="deep_agent_demo")


__all__ = ["get_agent"]
