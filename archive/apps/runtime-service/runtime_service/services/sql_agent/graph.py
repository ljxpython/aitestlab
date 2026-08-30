from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from runtime_service.conf.settings import get_default_model_id
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.runtime_request_resolver import (
    AgentDefaults,
    ResolvedRuntimeSettings,
    dedupe_tools_by_name,
)
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.services.sql_agent.chart_mcp import (
    aget_mcp_server_chart_tools,
    get_mcp_server_chart_tools,
)
from runtime_service.services.sql_agent.prompts import build_sql_agent_system_prompt
from runtime_service.services.sql_agent.schemas import DEFAULT_DATABASE_NAME
from runtime_service.services.sql_agent.tools import (
    build_sql_agent_service_config,
    build_sql_agent_tools,
)
from runtime_service.tools.registry import abuild_runtime_tools, build_runtime_tools

SQL_AGENT_DEFAULTS = AgentDefaults(
    model_id=get_default_model_id(),
    system_prompt="",
    enable_tools=False,
)

SQL_AGENT_SERVICE_CONFIG = build_sql_agent_service_config(None)
BASELINE_MODEL = resolve_model_by_id(SQL_AGENT_DEFAULTS.model_id)

_CHART_TOOLS_CACHE: list[Any] | None = None
_CHART_TOOLS_LOAD_FAILED = False


def _build_sql_system_prompt(settings: ResolvedRuntimeSettings) -> str:
    custom_instructions = settings.system_prompt or None
    return build_sql_agent_system_prompt(
        dialect="sqlite",
        top_k=SQL_AGENT_SERVICE_CONFIG.top_k,
        database_name=DEFAULT_DATABASE_NAME,
        custom_instructions=custom_instructions,
    )


def _get_chart_tools() -> list[Any]:
    global _CHART_TOOLS_CACHE, _CHART_TOOLS_LOAD_FAILED

    if _CHART_TOOLS_CACHE is not None:
        return list(_CHART_TOOLS_CACHE)
    if _CHART_TOOLS_LOAD_FAILED:
        return []

    try:
        _CHART_TOOLS_CACHE = list(get_mcp_server_chart_tools())
    except Exception:
        _CHART_TOOLS_LOAD_FAILED = True
        return []
    return list(_CHART_TOOLS_CACHE)


async def _aget_chart_tools() -> list[Any]:
    global _CHART_TOOLS_CACHE, _CHART_TOOLS_LOAD_FAILED

    if _CHART_TOOLS_CACHE is not None:
        return list(_CHART_TOOLS_CACHE)
    if _CHART_TOOLS_LOAD_FAILED:
        return []

    try:
        _CHART_TOOLS_CACHE = list(await aget_mcp_server_chart_tools())
    except Exception:
        _CHART_TOOLS_LOAD_FAILED = True
        return []
    return list(_CHART_TOOLS_CACHE)


def _resolve_required_tools(settings: ResolvedRuntimeSettings) -> list[Any]:
    return [
        *build_sql_agent_tools(settings.model),
        *_get_chart_tools(),
    ]


async def _aresolve_required_tools(settings: ResolvedRuntimeSettings) -> list[Any]:
    return [
        *build_sql_agent_tools(settings.model),
        *(await _aget_chart_tools()),
    ]


BASELINE_PRIVATE_TOOLS = dedupe_tools_by_name(
    [
        *build_sql_agent_tools(BASELINE_MODEL),
        *_get_chart_tools(),
    ]
)


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
    tools=BASELINE_PRIVATE_TOOLS,
    middleware=[
        RuntimeRequestMiddleware(
            defaults=SQL_AGENT_DEFAULTS,
            required_tools=[],
            public_tools=[],
            required_tool_resolver=_resolve_required_tools,
            arequired_tool_resolver=_aresolve_required_tools,
            public_tool_resolver=_resolve_public_tools,
            apublic_tool_resolver=_aresolve_public_tools,
            system_prompt_resolver=_build_sql_system_prompt,
        )
    ],
    system_prompt=_build_sql_system_prompt(
        ResolvedRuntimeSettings(
            context=RuntimeContext(),
            model=BASELINE_MODEL,
            system_prompt="",
            enable_tools=False,
            requested_public_tool_names=[],
        )
    ),
    context_schema=RuntimeContext,
    name="sql_agent",
)
