from __future__ import annotations

import sys
import importlib
from pathlib import Path
from typing import Any

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import HumanMessage
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.middlewares.multimodal.middleware import MultimodalMiddleware  # noqa: E402
from runtime_service.middlewares.multimodal.types import (  # noqa: E402
    DEFAULT_MULTIMODAL_MODEL_ID,
    MULTIMODAL_PARSER_MODEL_ID_ENV,
    get_default_multimodal_model_id,
)
from runtime_service.services.test_case_service.schemas import (  # noqa: E402
    build_test_case_service_config,
)


def test_get_default_multimodal_model_id_reads_env(monkeypatch) -> None:
    monkeypatch.setenv(MULTIMODAL_PARSER_MODEL_ID_ENV, "glm4v_multimodal")

    assert get_default_multimodal_model_id() == "glm4v_multimodal"


def test_get_default_multimodal_model_id_falls_back_to_code_default(monkeypatch) -> None:
    monkeypatch.delenv(MULTIMODAL_PARSER_MODEL_ID_ENV, raising=False)

    assert get_default_multimodal_model_id() == DEFAULT_MULTIMODAL_MODEL_ID


def test_multimodal_middleware_uses_env_default_when_parser_model_id_omitted(monkeypatch) -> None:
    monkeypatch.setenv(MULTIMODAL_PARSER_MODEL_ID_ENV, "qwen_vl_env_default")

    middleware = MultimodalMiddleware()

    assert middleware._parser_model_id == "qwen_vl_env_default"


def test_multimodal_middleware_explicit_parser_model_id_beats_env(monkeypatch) -> None:
    monkeypatch.setenv(MULTIMODAL_PARSER_MODEL_ID_ENV, "qwen_vl_env_default")

    middleware = MultimodalMiddleware(parser_model_id="manual_override")

    assert middleware._parser_model_id == "manual_override"


def test_build_test_case_service_config_uses_env_default_when_private_override_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv(MULTIMODAL_PARSER_MODEL_ID_ENV, "shared_env_parser")

    config = build_test_case_service_config({"configurable": {}})

    assert config.multimodal_parser_model_id == "shared_env_parser"


def test_build_test_case_service_config_private_override_beats_env(monkeypatch) -> None:
    monkeypatch.setenv(MULTIMODAL_PARSER_MODEL_ID_ENV, "shared_env_parser")

    config = build_test_case_service_config(
        {
            "configurable": {
                "test_case_multimodal_parser_model_id": "service_private_override"
            }
        }
    )

    assert config.multimodal_parser_model_id == "service_private_override"


def test_multimodal_middleware_platform_runtime_override_beats_env(monkeypatch) -> None:
    monkeypatch.setenv(MULTIMODAL_PARSER_MODEL_ID_ENV, "shared_env_parser")
    monkeypatch.setattr(
        "runtime_service.middlewares.multimodal.middleware.get_config",
        lambda: {
            "configurable": {
                "platform_runtime": {
                    "multimodal_parser_model_id": "runtime_override",
                }
            }
        },
    )

    middleware = MultimodalMiddleware()
    assert middleware._resolve_parser_model_id() == "runtime_override"


def test_test_case_graph_multimodal_middleware_preserves_platform_runtime_override(
    monkeypatch,
) -> None:
    monkeypatch.setenv(MULTIMODAL_PARSER_MODEL_ID_ENV, "shared_env_parser")
    monkeypatch.setattr(
        "runtime_service.middlewares.multimodal.middleware.get_config",
        lambda: {
            "configurable": {
                "platform_runtime": {
                    "multimodal_parser_model_id": "graph_runtime_override",
                }
            }
        },
    )

    graph_module = importlib.import_module("runtime_service.services.test_case_service.graph")
    graph_module = importlib.reload(graph_module)
    middleware = graph_module.TEST_CASE_MIDDLEWARE[0]

    assert middleware._resolve_parser_model_id() == "graph_runtime_override"
