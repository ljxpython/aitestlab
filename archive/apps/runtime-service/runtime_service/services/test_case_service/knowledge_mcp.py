from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import StructuredTool

from runtime_service.services.test_case_service.schemas import TestCaseServiceConfig

TEST_CASE_KNOWLEDGE_SERVER_NAME = "test_case_knowledge"
logger = logging.getLogger(__name__)


def build_test_case_knowledge_mcp_specs(
    service_config: TestCaseServiceConfig,
) -> dict[str, dict[str, object]]:
    url = service_config.knowledge_mcp_url.strip()
    if not url:
        return {}

    return {
        TEST_CASE_KNOWLEDGE_SERVER_NAME: {
            "transport": "sse",
            "url": url,
            "timeout": service_config.knowledge_timeout_seconds,
            "sse_read_timeout": service_config.knowledge_sse_read_timeout_seconds,
        }
    }


async def aget_test_case_knowledge_tools(
    service_config: TestCaseServiceConfig,
) -> list[Any]:
    if not service_config.knowledge_mcp_enabled:
        return []

    specs = build_test_case_knowledge_mcp_specs(service_config)
    if not specs:
        return []

    try:
        client = MultiServerMCPClient(specs, tool_name_prefix=False)
        tools = await client.get_tools()
    except Exception:
        logger.warning(
            "test_case_service knowledge MCP unavailable, fallback to local-only tools",
            extra={
                "knowledge_mcp_url": service_config.knowledge_mcp_url,
                "knowledge_timeout_seconds": service_config.knowledge_timeout_seconds,
                "knowledge_sse_read_timeout_seconds": service_config.knowledge_sse_read_timeout_seconds,
            },
            exc_info=True,
        )
        return []

    return [_wrap_mcp_tool_with_string_output(tool) for tool in tools]


def get_test_case_knowledge_tools(
    service_config: TestCaseServiceConfig,
) -> list[Any]:
    return asyncio.run(aget_test_case_knowledge_tools(service_config))


def _wrap_mcp_tool_with_string_output(tool: Any) -> StructuredTool:
    async def call_tool(**kwargs: Any) -> str:
        if getattr(tool, "coroutine", None) is not None:
            result = await tool.coroutine(**kwargs)
        else:
            result = await tool.ainvoke(kwargs)
        return _normalize_mcp_tool_result(result)

    return StructuredTool.from_function(
        coroutine=call_tool,
        name=str(getattr(tool, "name", "")).strip(),
        description=str(getattr(tool, "description", "") or ""),
        args_schema=getattr(tool, "args_schema", None),
        infer_schema=False,
        return_direct=bool(getattr(tool, "return_direct", False)),
        response_format="content",
        metadata=getattr(tool, "metadata", None),
        tags=getattr(tool, "tags", None),
    )


def _normalize_mcp_tool_result(result: Any) -> str:
    content = result[0] if isinstance(result, tuple) and result else result
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
                continue
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        if text_parts:
            return "\n".join(part for part in text_parts if part)
        return json.dumps(content, ensure_ascii=False)
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    if content is None:
        return ""
    return str(content)
