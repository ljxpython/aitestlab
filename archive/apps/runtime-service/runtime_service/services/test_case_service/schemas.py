from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from runtime_service.middlewares.multimodal.types import get_default_multimodal_model_id
from runtime_service.runtime.config_utils import read_configurable

DEFAULT_MULTIMODAL_DETAIL_MODE = False
DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS = 2000
DEFAULT_TEST_CASE_MODEL_ID = "deepseek_chat"
DEFAULT_TEST_CASE_PERSISTENCE_ENABLED = True
DEFAULT_TEST_CASE_KNOWLEDGE_MCP_ENABLED = True
DEFAULT_TEST_CASE_KNOWLEDGE_MCP_URL = "http://0.0.0.0:8000/sse"
DEFAULT_TEST_CASE_KNOWLEDGE_TIMEOUT_SECONDS = 30
DEFAULT_TEST_CASE_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class TestCaseServiceConfig:
    multimodal_parser_model_id: str = field(
        default_factory=get_default_multimodal_model_id
    )
    multimodal_detail_mode: bool = DEFAULT_MULTIMODAL_DETAIL_MODE
    multimodal_detail_text_max_chars: int = DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS
    default_model_id: str = DEFAULT_TEST_CASE_MODEL_ID
    persistence_enabled: bool = DEFAULT_TEST_CASE_PERSISTENCE_ENABLED
    knowledge_mcp_enabled: bool = DEFAULT_TEST_CASE_KNOWLEDGE_MCP_ENABLED
    knowledge_mcp_url: str = DEFAULT_TEST_CASE_KNOWLEDGE_MCP_URL
    knowledge_timeout_seconds: int = DEFAULT_TEST_CASE_KNOWLEDGE_TIMEOUT_SECONDS
    knowledge_sse_read_timeout_seconds: int = (
        DEFAULT_TEST_CASE_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS
    )


class PersistTestCaseItem(BaseModel):
    case_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    status: str = Field(default="active", min_length=1, max_length=64)
    module_name: str | None = Field(default=None, max_length=255)
    priority: str | None = Field(default=None, max_length=32)
    test_type: str | None = Field(default=None, max_length=64)
    design_technique: str | None = Field(default=None, max_length=64)
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    test_data: dict[str, Any] = Field(default_factory=dict)
    expected_results: list[str] = Field(default_factory=list)
    remarks: str | None = None
    content_json: dict[str, Any] = Field(default_factory=dict)


class PersistTestCaseResultsArgs(BaseModel):
    bundle_title: str = Field(min_length=1, max_length=255)
    bundle_summary: str = ""
    test_cases: list[PersistTestCaseItem] = Field(default_factory=list)
    quality_review: dict[str, Any] = Field(default_factory=dict)
    export_format: str | None = Field(default=None, max_length=32)


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_test_case_service_config(config: RunnableConfig) -> TestCaseServiceConfig:
    """从 RunnableConfig 中解析服务配置，未提供则使用默认值。"""
    private_config = dict(read_configurable(config))
    default_multimodal_parser_model_id = get_default_multimodal_model_id()
    return TestCaseServiceConfig(
        multimodal_parser_model_id=str(
            private_config.get("test_case_multimodal_parser_model_id")
            or default_multimodal_parser_model_id
        ),
        multimodal_detail_mode=_parse_bool(
            private_config.get("test_case_multimodal_detail_mode"),
            DEFAULT_MULTIMODAL_DETAIL_MODE,
        ),
        multimodal_detail_text_max_chars=_parse_int(
            private_config.get("test_case_multimodal_detail_text_max_chars"),
            DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS,
        ),
        default_model_id=str(
            private_config.get("test_case_default_model_id") or DEFAULT_TEST_CASE_MODEL_ID
        ),
        persistence_enabled=_parse_bool(
            private_config.get("test_case_persistence_enabled"),
            DEFAULT_TEST_CASE_PERSISTENCE_ENABLED,
        ),
        knowledge_mcp_enabled=_parse_bool(
            private_config.get("test_case_knowledge_mcp_enabled"),
            DEFAULT_TEST_CASE_KNOWLEDGE_MCP_ENABLED,
        ),
        knowledge_mcp_url=str(
            private_config.get("test_case_knowledge_mcp_url")
            or DEFAULT_TEST_CASE_KNOWLEDGE_MCP_URL
        ),
        knowledge_timeout_seconds=_parse_int(
            private_config.get("test_case_knowledge_timeout_seconds"),
            DEFAULT_TEST_CASE_KNOWLEDGE_TIMEOUT_SECONDS,
        ),
        knowledge_sse_read_timeout_seconds=_parse_int(
            private_config.get("test_case_knowledge_sse_read_timeout_seconds"),
            DEFAULT_TEST_CASE_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS,
        ),
    )


def get_service_root() -> Path:
    return Path(__file__).resolve().parent


def get_skills_root() -> Path:
    return get_service_root() / "skills"
