from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent
from runtime_service.agents.research_agent.prompts import SYSTEM_PROMPT
from runtime_service.agents.research_agent.tools import (
    aget_research_private_tools,
    build_research_runtime_tools,
    get_research_private_tools,
    list_research_agent_skills,
    list_research_subagents,
)
from runtime_service.conf.settings import get_default_model_id
from runtime_service.middlewares.multimodal import MultimodalMiddleware
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.filesystem_backend import build_filesystem_backend
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.runtime.runtime_request_resolver import (
    AgentDefaults,
    ResolvedRuntimeSettings,
)
from runtime_service.tools.registry import abuild_runtime_tools, build_runtime_tools


def _default_backend_root() -> Path:
    return Path(tempfile.gettempdir()) / "ai-agent-platform" / "deepagents" / "research-demo"


RESEARCH_DEFAULTS = AgentDefaults(
    model_id=get_default_model_id(),
    system_prompt=SYSTEM_PROMPT,
    enable_tools=False,
)

BASELINE_MODEL = resolve_model_by_id(RESEARCH_DEFAULTS.model_id)
SUBAGENTS: list[SubAgent | CompiledSubAgent] = list(list_research_subagents())
RESEARCH_MIDDLEWARE = MultimodalMiddleware()
BACKEND = build_filesystem_backend(
    root_dir=_default_backend_root(),
    virtual_mode=False,
)


def _resolve_required_tools(_settings: ResolvedRuntimeSettings) -> list[Any]:
    return [
        *build_research_runtime_tools(),
        *get_research_private_tools({}),
    ]


async def _aresolve_required_tools(_settings: ResolvedRuntimeSettings) -> list[Any]:
    return [
        *build_research_runtime_tools(),
        *(await aget_research_private_tools({})),
    ]


def _resolve_public_tools(settings: ResolvedRuntimeSettings) -> list[Any]:
    return build_runtime_tools(
        enable_tools=settings.enable_tools,
        requested_tool_names=settings.requested_public_tool_names or None,
    )


async def _aresolve_public_tools(settings: ResolvedRuntimeSettings) -> list[Any]:
    return await abuild_runtime_tools(
        enable_tools=settings.enable_tools,
        requested_tool_names=settings.requested_public_tool_names or None,
    )


graph = create_deep_agent(
    name="research-demo",
    model=BASELINE_MODEL,
    tools=[],
    middleware=[
        RuntimeRequestMiddleware(
            defaults=RESEARCH_DEFAULTS,
            required_tools=[],
            public_tools=[],
            required_tool_resolver=_resolve_required_tools,
            arequired_tool_resolver=_aresolve_required_tools,
            public_tool_resolver=_resolve_public_tools,
            apublic_tool_resolver=_aresolve_public_tools,
        ),
        RESEARCH_MIDDLEWARE,
    ],
    system_prompt=RESEARCH_DEFAULTS.system_prompt,
    backend=BACKEND,
    skills=list_research_agent_skills(),
    subagents=SUBAGENTS,
    context_schema=RuntimeContext,
)
