from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from langchain_core.tools import StructuredTool

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.services.test_case_service_v2 import knowledge_mcp  # noqa: E402
from runtime_service.services.test_case_service_v2.schemas import (  # noqa: E402
    DEFAULT_TEST_CASE_KNOWLEDGE_MCP_URL,
    TestCaseServiceConfig as ServiceConfig,
    build_test_case_service_config,
)


def test_build_test_case_knowledge_mcp_specs_defaults() -> None:
    specs = knowledge_mcp.build_test_case_knowledge_mcp_specs(ServiceConfig())
    assert specs == {
        knowledge_mcp.TEST_CASE_KNOWLEDGE_SERVER_NAME: {
            "transport": "sse",
            "url": DEFAULT_TEST_CASE_KNOWLEDGE_MCP_URL,
            "timeout": 30,
            "sse_read_timeout": 300,
        }
    }


def test_aget_test_case_knowledge_tools_disabled_returns_empty() -> None:
    config = ServiceConfig(knowledge_mcp_enabled=False)
    assert asyncio.run(knowledge_mcp.aget_test_case_knowledge_tools(config)) == []


def test_aget_test_case_knowledge_tools_uses_multi_server_client(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyClient:
        def __init__(self, specs: dict[str, dict[str, object]], *, tool_name_prefix: bool) -> None:
            captured["specs"] = specs
            captured["tool_name_prefix"] = tool_name_prefix

        async def get_tools(self) -> list[StructuredTool]:
            async def fake_query_tool(project_id: str) -> list[dict[str, str]]:
                return [{"type": "text", "text": f"project={project_id}"}]

            async def fake_list_tool(project_id: str) -> dict[str, object]:
                return {"project_id": project_id, "documents": []}

            async def fake_status_tool(project_id: str, document_id: str) -> dict[str, str]:
                return {
                    "project_id": project_id,
                    "document_id": document_id,
                    "overall_status": "not_found",
                }

            return [
                StructuredTool.from_function(
                    coroutine=fake_query_tool,
                    name="query_project_knowledge",
                    description="query",
                ),
                StructuredTool.from_function(
                    coroutine=fake_list_tool,
                    name="list_project_knowledge_documents",
                    description="list",
                ),
                StructuredTool.from_function(
                    coroutine=fake_status_tool,
                    name="get_project_knowledge_document_status",
                    description="status",
                ),
            ]

    monkeypatch.setattr(knowledge_mcp, "MultiServerMCPClient", DummyClient)

    tools = asyncio.run(
        knowledge_mcp.aget_test_case_knowledge_tools(
            ServiceConfig(
                knowledge_mcp_url="http://127.0.0.1:8765/sse",
                knowledge_timeout_seconds=12,
                knowledge_sse_read_timeout_seconds=34,
            )
        )
    )

    tool_names = {getattr(tool, "name", "") for tool in tools}
    assert tool_names == knowledge_mcp.REQUIRED_KNOWLEDGE_TOOL_NAMES

    query_tool = next(tool for tool in tools if getattr(tool, "name", "") == "query_project_knowledge")
    content = asyncio.run(query_tool.ainvoke({"project_id": "project-a"}))
    assert content == "project=project-a"
    assert captured["tool_name_prefix"] is False
    assert captured["specs"] == {
        knowledge_mcp.TEST_CASE_KNOWLEDGE_SERVER_NAME: {
            "transport": "sse",
            "url": "http://127.0.0.1:8765/sse",
            "timeout": 12,
            "sse_read_timeout": 34,
        }
    }


def test_aget_test_case_knowledge_tools_returns_empty_when_client_init_fails(monkeypatch) -> None:
    class BrokenClient:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("mcp unavailable")

    monkeypatch.setattr(knowledge_mcp, "MultiServerMCPClient", BrokenClient)

    tools = asyncio.run(
        knowledge_mcp.aget_test_case_knowledge_tools(
            ServiceConfig(
                knowledge_mcp_url="http://127.0.0.1:8765/sse",
            )
        )
    )

    assert tools == []


def test_aget_test_case_knowledge_tools_returns_empty_when_required_tools_missing(
    monkeypatch,
) -> None:
    class DummyClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def get_tools(self) -> list[StructuredTool]:
            async def fake_tool(project_id: str) -> list[dict[str, str]]:
                return [{"type": "text", "text": f"project={project_id}"}]

            return [
                StructuredTool.from_function(
                    coroutine=fake_tool,
                    name="query_project_knowledge",
                    description="query",
                )
            ]

    monkeypatch.setattr(knowledge_mcp, "MultiServerMCPClient", DummyClient)

    tools = asyncio.run(
        knowledge_mcp.aget_test_case_knowledge_tools(
            ServiceConfig(
                knowledge_mcp_url="http://127.0.0.1:8765/sse",
            )
        )
    )

    assert tools == []


def test_wrapped_mcp_tool_supports_repeated_invocations() -> None:
    calls: list[str] = []

    async def fake_tool(project_id: str) -> list[dict[str, str]]:
        calls.append(project_id)
        return [{"type": "text", "text": f"project={project_id};count={len(calls)}"}]

    wrapped = knowledge_mcp._wrap_mcp_tool_with_string_output(
        StructuredTool.from_function(
            coroutine=fake_tool,
            name="query_project_knowledge",
            description="query",
        )
    )

    first = asyncio.run(wrapped.ainvoke({"project_id": "project-a"}))
    second = asyncio.run(wrapped.ainvoke({"project_id": "project-b"}))

    assert first == "project=project-a;count=1"
    assert second == "project=project-b;count=2"
    assert calls == ["project-a", "project-b"]


def test_normalize_mcp_tool_result_handles_tuple_content_blocks() -> None:
    result = (
        [
            {"type": "text", "text": '{"project_id":"p1","count":0,"documents":[]}'},
        ],
        {"structured_content": {"project_id": "p1", "count": 0, "documents": []}},
    )
    assert (
        knowledge_mcp._normalize_mcp_tool_result(result)
        == '{"project_id":"p1","count":0,"documents":[]}'
    )


def test_build_test_case_service_config_reads_v2_prefixed_keys() -> None:
    config = build_test_case_service_config(
        {
            "configurable": {
                "test_case_v2_default_model_id": "gpt-4o-mini",
                "test_case_v2_multimodal_detail_mode": True,
                "test_case_v2_knowledge_mcp_enabled": False,
                "test_case_v2_knowledge_mcp_url": "http://127.0.0.1:9999/sse",
                "test_case_v2_knowledge_timeout_seconds": 12,
                "test_case_v2_knowledge_sse_read_timeout_seconds": 34,
            }
        }
    )

    assert config.default_model_id == "gpt-4o-mini"
    assert config.multimodal_detail_mode is True
    assert config.knowledge_mcp_enabled is False
    assert config.knowledge_mcp_url == "http://127.0.0.1:9999/sse"
    assert config.knowledge_timeout_seconds == 12
    assert config.knowledge_sse_read_timeout_seconds == 34
