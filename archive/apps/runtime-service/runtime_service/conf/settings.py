from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TypedDict

import yaml

_CONF_DIR = Path(__file__).parent.absolute()
_SETTINGS_FILE = _CONF_DIR / "settings.yaml"
_LOCAL_SETTINGS_FILE = _CONF_DIR / "settings.local.yaml"
_CURRENT_ENV = (
    (os.getenv("APP_ENV") or os.getenv("DYNACONF_ENV") or "test").strip().lower()
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _read_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _as_dict(data)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _select_env_block(raw: dict[str, Any], env_name: str) -> dict[str, Any]:
    default_block = _as_dict(raw.get("default"))
    env_block = _as_dict(raw.get(env_name))
    return _deep_merge(default_block, env_block)


def _load_settings() -> dict[str, Any]:
    primary = _read_yaml_file(_SETTINGS_FILE)
    selected = _select_env_block(primary, _CURRENT_ENV)

    local = _read_yaml_file(_LOCAL_SETTINGS_FILE)
    if local:
        local_selected = _select_env_block(local, _CURRENT_ENV)
        selected = _deep_merge(selected, local_selected)
    return selected


_SETTINGS = _load_settings()


class ModelCatalogItem(TypedDict):
    model_id: str
    display_name: str
    is_default: bool


def get_default_model_id() -> str:
    default_id = _SETTINGS.get("default_model_id")
    default_id = str(default_id).strip() if default_id is not None else ""
    return default_id or "glm4_mass"


def list_model_catalog() -> list[ModelCatalogItem]:
    default_id = get_default_model_id()
    all_models = _as_dict(_SETTINGS.get("models"))

    catalog: list[ModelCatalogItem] = []
    for raw_model_id, raw_value in all_models.items():
        model_id = str(raw_model_id).strip()
        if not model_id:
            continue

        value = _as_dict(raw_value)
        alias = str(value.get("alias") or "").strip()
        display_name = alias or model_id

        catalog.append(
            {
                "model_id": model_id,
                "display_name": display_name,
                "is_default": model_id == default_id,
            }
        )

    return sorted(
        catalog,
        key=lambda item: (
            0 if item["is_default"] else 1,
            item["display_name"].lower(),
            item["model_id"].lower(),
        ),
    )


def get_model_spec(model_id: str) -> dict[str, str | None]:
    model_id = str(model_id or "").strip()
    all_models = _as_dict(_SETTINGS.get("models"))
    raw = all_models.get(model_id) if model_id else None
    data = _as_dict(raw)
    model_provider = data.get("model_provider")
    model = data.get("model")
    base_url = data.get("base_url")
    api_key = data.get("api_key")

    def _norm(v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    return {
        "model_provider": _norm(model_provider),
        "model": _norm(model),
        "base_url": _norm(base_url),
        "api_key": _norm(api_key),
    }


def require_model_spec(model_id: str | None = None) -> tuple[str, dict[str, str]]:
    """解析并校验模型组配置。

    规则：
    - 用户只需要提供 model_id（为空时使用 default_model_id）
    - 模型组必须具备 provider/model/base_url/api_key 四元组
    """

    resolved_id = str(model_id or "").strip() or get_default_model_id()
    raw_spec = get_model_spec(resolved_id)

    provider = raw_spec.get("model_provider")
    model = raw_spec.get("model")
    base_url = raw_spec.get("base_url")
    api_key = raw_spec.get("api_key")

    missing: list[str] = []
    if not provider:
        missing.append("model_provider")
    if not model:
        missing.append("model")
    if not base_url:
        missing.append("base_url")
    if not api_key:
        missing.append("api_key")

    if missing:
        missing_fields = ", ".join(missing)
        raise ValueError(
            f"Model '{resolved_id}' config is incomplete in settings.yaml: missing {missing_fields}."
        )

    assert provider is not None
    assert model is not None
    assert base_url is not None
    assert api_key is not None

    return resolved_id, {
        "model_provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
    }
