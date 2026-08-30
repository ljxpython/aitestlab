from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any


def read_configurable(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(config, Mapping):
        return {}
    configurable = config.get("configurable")
    return configurable if isinstance(configurable, Mapping) else {}


def context_to_mapping(raw: Any) -> Mapping[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return raw
    if dataclasses.is_dataclass(raw) and not isinstance(raw, type):
        return dataclasses.asdict(raw)
    raw_dict = getattr(raw, "__dict__", None)
    return raw_dict if isinstance(raw_dict, Mapping) else {}


__all__ = ["context_to_mapping", "read_configurable"]
