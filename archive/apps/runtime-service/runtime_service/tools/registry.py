from __future__ import annotations

import asyncio
from typing import Any

from runtime_service.mcp.loader import get_mcp_tools
from runtime_service.mcp.servers import get_mcp_server_specs
from runtime_service.tools.local import get_builtin_tools

MCP_TOOL_PREFIX = "mcp:"


def _builtin_tool_catalog() -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}
    for tool in get_builtin_tools(None):
        name = str(getattr(tool, "name", "")).strip().lower()
        if not name:
            continue
        description = str(getattr(tool, "description", "") or "")
        catalog[name] = {
            "name": name,
            "source": "builtin_tool",
            "description": description,
        }
    return catalog


def get_tool_catalog() -> dict[str, dict[str, str]]:
    catalog = _builtin_tool_catalog()
    for server_name in sorted(get_mcp_server_specs().keys()):
        display_name = f"{MCP_TOOL_PREFIX}{server_name}"
        catalog[display_name] = {
            "name": display_name,
            "source": "mcp_server",
            "description": f"MCP server '{server_name}' (loads all tools from this server).",
        }
    return catalog


def resolve_requested_tools(
    requested_tool_names: list[str] | None,
) -> tuple[list[str], list[str]]:
    builtin_catalog = _builtin_tool_catalog()
    mcp_specs = get_mcp_server_specs()

    if not requested_tool_names:
        return [], []

    selected_builtin: list[str] = []
    selected_mcp: list[str] = []
    seen_builtin: set[str] = set()
    seen_mcp: set[str] = set()
    unknown: list[str] = []

    for raw_name in requested_tool_names:
        key = str(raw_name).strip().lower()
        if not key:
            continue

        if key in builtin_catalog:
            if key not in seen_builtin:
                seen_builtin.add(key)
                selected_builtin.append(key)
            continue

        server_name = (
            key[len(MCP_TOOL_PREFIX) :] if key.startswith(MCP_TOOL_PREFIX) else key
        )
        if server_name in mcp_specs:
            if server_name not in seen_mcp:
                seen_mcp.add(server_name)
                selected_mcp.append(server_name)
            continue

        unknown.append(key)

    if unknown:
        allowed = ", ".join(sorted(get_tool_catalog().keys()))
        raise ValueError(f"Unsupported tools: {unknown}. allowed: {allowed}")

    return selected_builtin, selected_mcp


def build_runtime_tools(
    *,
    enable_tools: bool,
    requested_tool_names: list[str] | None,
) -> list[Any]:
    if not enable_tools:
        return []

    builtin_names, mcp_server_names = resolve_requested_tools(requested_tool_names)
    tools: list[Any] = []
    if builtin_names:
        tools.extend(get_builtin_tools(builtin_names))
    if mcp_server_names:
        tools.extend(asyncio.run(get_mcp_tools(mcp_server_names)))
    return tools


async def abuild_runtime_tools(
    *,
    enable_tools: bool,
    requested_tool_names: list[str] | None,
) -> list[Any]:
    if not enable_tools:
        return []

    builtin_names, mcp_server_names = resolve_requested_tools(requested_tool_names)
    tools: list[Any] = []
    if builtin_names:
        tools.extend(get_builtin_tools(builtin_names))
    if mcp_server_names:
        tools.extend(await get_mcp_tools(mcp_server_names))
    return tools

__all__ = [
    "MCP_TOOL_PREFIX",
    "abuild_runtime_tools",
    "build_runtime_tools",
    "get_tool_catalog",
    "resolve_requested_tools",
]
