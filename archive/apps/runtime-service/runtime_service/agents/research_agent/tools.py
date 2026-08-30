from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from deepagents.middleware.subagents import SubAgent
from langchain_mcp_adapters.client import MultiServerMCPClient
from runtime_service.tools.multimodal import read_multimodal_attachments


def list_research_agent_skills() -> list[str]:
    skills_root = Path(__file__).resolve().parent / "skills"
    return [str(skills_root)]


def list_research_subagents() -> list[SubAgent]:
    skill_sources = list_research_agent_skills()
    return [
        SubAgent(
            name="research-subagent",
            description=(
                "Focused web researcher for one subtopic. Collect concise evidence and "
                "save findings into local files with source links."
            ),
            system_prompt=(
                "You are a focused research subagent. Keep scope narrow, cite URLs, and "
                "return concise findings that can be merged by the parent agent."
            ),
            skills=skill_sources,
        )
    ]


def build_research_runtime_tools() -> list[Any]:
    return [read_multimodal_attachments]


async def aget_research_private_tools(config: dict[str, Any]) -> list[Any]:
    """Build research-only private tools (currently optional Tavily MCP)."""

    tavily_api_key = str(
        config.get("research_tavily_api_key") or os.getenv("RESEARCH_TAVILY_API_KEY") or ""
    ).strip()
    if not tavily_api_key:
        return []

    client = MultiServerMCPClient(
        {
            "tavily_web": {
                "transport": "http",
                "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}",
            }
        }
    )
    return await client.get_tools()


def get_research_private_tools(config: dict[str, Any] | None = None) -> list[Any]:
    return asyncio.run(aget_research_private_tools(config or {}))
