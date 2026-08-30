from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from runtime_service.agents.customer_support_agent.tools import (
    StepMiddleware,
    SupportState,
)
from runtime_service.conf.settings import get_default_model_id
from runtime_service.middlewares.multimodal import MultimodalMiddleware
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.runtime.runtime_request_resolver import (
    AgentDefaults,
    ResolvedRuntimeSettings,
)
from runtime_service.tools.registry import abuild_runtime_tools, build_runtime_tools


CUSTOMER_SUPPORT_DEFAULTS = AgentDefaults(
    model_id=get_default_model_id(),
    system_prompt="",
    enable_tools=False,
)

BASELINE_MODEL = resolve_model_by_id(CUSTOMER_SUPPORT_DEFAULTS.model_id)


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


graph = create_agent(
    model=BASELINE_MODEL,
    tools=[],
    system_prompt=CUSTOMER_SUPPORT_DEFAULTS.system_prompt,
    state_schema=SupportState,
    context_schema=RuntimeContext,
    name="customer_support_handoff_demo",
    middleware=[
        RuntimeRequestMiddleware(
            defaults=CUSTOMER_SUPPORT_DEFAULTS,
            required_tools=[],
            public_tools=[],
            public_tool_resolver=_resolve_public_tools,
            apublic_tool_resolver=_aresolve_public_tools,
        ),
        StepMiddleware(),
        MultimodalMiddleware(),
    ],
)
