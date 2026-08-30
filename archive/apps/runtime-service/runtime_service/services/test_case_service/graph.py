from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from runtime_service.middlewares.multimodal import MultimodalMiddleware
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.filesystem_backend import build_filesystem_backend
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.runtime.runtime_request_resolver import (
    AgentDefaults,
    ResolvedRuntimeSettings,
)
from runtime_service.services.test_case_service.knowledge_mcp import (
    aget_test_case_knowledge_tools,
    get_test_case_knowledge_tools,
)
from runtime_service.services.test_case_service.knowledge_query_guard_middleware import (
    TestCaseKnowledgeQueryGuardMiddleware,
)
from runtime_service.services.test_case_service.middleware import (
    TestCaseDocumentPersistenceMiddleware,
)
from runtime_service.services.test_case_service.prompts import (
    build_test_case_system_prompt,
)
from runtime_service.services.test_case_service.schemas import (
    TestCaseServiceConfig,
    build_test_case_service_config,
    get_service_root,
)
from runtime_service.services.test_case_service.tool_runtime_context_middleware import (
    ToolRuntimeContextSanitizerMiddleware,
)
from runtime_service.services.test_case_service.tools import (
    build_test_case_service_tools,
)


TEST_CASE_SERVICE_CONFIG: TestCaseServiceConfig = build_test_case_service_config(
    {"configurable": {}}
)
TEST_CASE_DEFAULTS = AgentDefaults(
    model_id=TEST_CASE_SERVICE_CONFIG.default_model_id,
    system_prompt="",
    enable_tools=False,
)

BASELINE_MODEL = resolve_model_by_id(TEST_CASE_DEFAULTS.model_id)
BACKEND = build_filesystem_backend(
    root_dir=get_service_root(),
    virtual_mode=True,
)
SERVICE_TOOLS = build_test_case_service_tools(TEST_CASE_SERVICE_CONFIG)
TEST_CASE_MIDDLEWARE = [
    MultimodalMiddleware(
        parser_model_id=TEST_CASE_SERVICE_CONFIG.multimodal_parser_model_id,
        detail_mode=TEST_CASE_SERVICE_CONFIG.multimodal_detail_mode,
        detail_text_max_chars=TEST_CASE_SERVICE_CONFIG.multimodal_detail_text_max_chars,
    ),
    TestCaseDocumentPersistenceMiddleware(TEST_CASE_SERVICE_CONFIG),
    TestCaseKnowledgeQueryGuardMiddleware(),
    ToolRuntimeContextSanitizerMiddleware(),
]


def _resolve_current_project_id(settings: ResolvedRuntimeSettings) -> str | None:
    project_id = settings.context.project_id
    if project_id:
        return str(project_id).strip() or None
    return None


def _build_system_prompt(settings: ResolvedRuntimeSettings) -> str:
    return build_test_case_system_prompt(
        runtime_system_prompt=settings.system_prompt or None,
        current_project_id=_resolve_current_project_id(settings),
    )


def _resolve_required_tools(_settings: ResolvedRuntimeSettings) -> list[Any]:
    return [
        *get_test_case_knowledge_tools(TEST_CASE_SERVICE_CONFIG),
        *SERVICE_TOOLS,
    ]


async def _aresolve_required_tools(_settings: ResolvedRuntimeSettings) -> list[Any]:
    return [
        *(await aget_test_case_knowledge_tools(TEST_CASE_SERVICE_CONFIG)),
        *SERVICE_TOOLS,
    ]


graph = create_deep_agent(
    name="test_case_agent",
    model=BASELINE_MODEL,
    tools=SERVICE_TOOLS,
    middleware=[
        RuntimeRequestMiddleware(
            defaults=TEST_CASE_DEFAULTS,
            required_tools=[],
            public_tools=[],
            required_tool_resolver=_resolve_required_tools,
            arequired_tool_resolver=_aresolve_required_tools,
            system_prompt_resolver=_build_system_prompt,
        ),
        *TEST_CASE_MIDDLEWARE,
    ],
    system_prompt=_build_system_prompt(
        ResolvedRuntimeSettings(
            context=RuntimeContext(),
            model=BASELINE_MODEL,
            system_prompt="",
            enable_tools=False,
            requested_public_tool_names=[],
        )
    ),
    backend=BACKEND,
    skills=["/skills/"],
    context_schema=RuntimeContext,
)
