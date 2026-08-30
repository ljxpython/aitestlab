from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import tool


@tool(description="Count words in text.")
def word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


@tool(description="Get current UTC timestamp.")
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@tool(description="Convert text to uppercase.")
def to_upper(text: str) -> str:
    return text.upper()


_BUILTIN_TOOL_REGISTRY: dict[str, Any] = {
    "word_count": word_count,
    "utc_now": utc_now,
    "to_upper": to_upper,
}


def get_builtin_tools(tool_names: list[str] | None = None) -> list[Any]:
    if tool_names is None:
        return list(_BUILTIN_TOOL_REGISTRY.values())

    selected: list[Any] = []
    seen: set[str] = set()
    for raw_name in tool_names:
        key = str(raw_name).strip().lower()
        if not key or key in seen:
            continue
        tool_obj = _BUILTIN_TOOL_REGISTRY.get(key)
        if tool_obj is None:
            allowed = ", ".join(sorted(_BUILTIN_TOOL_REGISTRY.keys()))
            raise ValueError(
                f"Unsupported builtin tool '{raw_name}', allowed: {allowed}"
            )
        seen.add(key)
        selected.append(tool_obj)
    return selected
