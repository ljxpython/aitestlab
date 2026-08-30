from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.conf import settings as settings_module  # noqa: E402


def test_list_model_catalog_uses_alias_when_present(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_module,
        "_SETTINGS",
        {
            "default_model_id": "m1",
            "models": {
                "m1": {"alias": "模型一"},
                "m2": {},
            },
        },
    )

    models = settings_module.list_model_catalog()
    by_id = {item["model_id"]: item for item in models}
    assert by_id["m1"]["display_name"] == "模型一"


def test_list_model_catalog_falls_back_to_model_id_when_alias_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings_module,
        "_SETTINGS",
        {
            "default_model_id": "m1",
            "models": {
                "m1": {},
            },
        },
    )

    models = settings_module.list_model_catalog()
    assert models[0]["model_id"] == "m1"
    assert models[0]["display_name"] == "m1"


def test_list_model_catalog_marks_default_model(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_module,
        "_SETTINGS",
        {
            "default_model_id": "m2",
            "models": {
                "m1": {"alias": "A"},
                "m2": {"alias": "B"},
            },
        },
    )

    models = settings_module.list_model_catalog()
    assert models[0]["model_id"] == "m2"
    assert models[0]["is_default"] is True


def test_list_model_catalog_does_not_expose_sensitive_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_module,
        "_SETTINGS",
        {
            "default_model_id": "m1",
            "models": {
                "m1": {
                    "alias": "展示名",
                    "model_provider": "openai",
                    "model": "gpt",
                    "base_url": "https://x",
                    "api_key": "secret",
                }
            },
        },
    )

    models = settings_module.list_model_catalog()
    assert set(models[0].keys()) == {"model_id", "display_name", "is_default"}
