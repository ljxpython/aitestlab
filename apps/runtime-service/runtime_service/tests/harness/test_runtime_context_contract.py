from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.runtime.context import RuntimeContext  # noqa: E402


def test_runtime_context_fields_match_v1_contract() -> None:
    field_names = [field.name for field in fields(RuntimeContext)]
    assert field_names == [
        "user_id",
        "tenant_id",
        "role",
        "permissions",
        "project_id",
        "model_id",
        "system_prompt",
        "temperature",
        "max_tokens",
        "top_p",
        "enable_tools",
        "tools",
        "multimodal_parser_model_id",
    ]


def test_runtime_context_excludes_legacy_public_fields() -> None:
    field_names = {field.name for field in fields(RuntimeContext)}
    assert "environment" not in field_names
    assert "skills" not in field_names
    assert "subagents" not in field_names
