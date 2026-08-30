from __future__ import annotations

from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent
from runtime_service.agents.deepagent_agent.prompts import SYSTEM_PROMPT
from runtime_service.agents.deepagent_agent.tools import (
    list_deepagent_skills,
    list_subagents,
)
from runtime_service.conf.settings import get_default_model_id
from runtime_service.middlewares.multimodal import MultimodalMiddleware
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.filesystem_backend import build_filesystem_backend
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.runtime.runtime_request_resolver import AgentDefaults
from runtime_service.tools.registry import abuild_runtime_tools, build_runtime_tools


def _runtime_service_root() -> Path:
    return Path(__file__).resolve().parents[2]


DEEPAGENT_DEFAULTS = AgentDefaults(
    model_id=get_default_model_id(),
    system_prompt=SYSTEM_PROMPT,
    enable_tools=False,
)

BASELINE_MODEL = resolve_model_by_id(DEEPAGENT_DEFAULTS.model_id)
SUBAGENTS: list[SubAgent | CompiledSubAgent] = list(list_subagents())
BACKEND = build_filesystem_backend(
    root_dir=_runtime_service_root(),
    virtual_mode=False,
)


def _resolve_public_tools(settings: Any) -> list[Any]:
    return build_runtime_tools(
        enable_tools=settings.enable_tools,
        requested_tool_names=settings.requested_public_tool_names or None,
    )


async def _aresolve_public_tools(settings: Any) -> list[Any]:
    return await abuild_runtime_tools(
        enable_tools=settings.enable_tools,
        requested_tool_names=settings.requested_public_tool_names or None,
    )


graph = create_deep_agent(
    name="deepagent-demo",
    model=BASELINE_MODEL,
    tools=[],
    middleware=[
        RuntimeRequestMiddleware(
            defaults=DEEPAGENT_DEFAULTS,
            required_tools=[],
            public_tools=[],
            public_tool_resolver=_resolve_public_tools,
            apublic_tool_resolver=_aresolve_public_tools,
        ),
        MultimodalMiddleware(),
    ],
    system_prompt=DEEPAGENT_DEFAULTS.system_prompt,
    backend=BACKEND,
    skills=list_deepagent_skills(),
    subagents=SUBAGENTS,
    context_schema=RuntimeContext,
)
