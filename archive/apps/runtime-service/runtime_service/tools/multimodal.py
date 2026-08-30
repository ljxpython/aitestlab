from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool


def _read_runtime_state(runtime: ToolRuntime[Any, Any]) -> dict[str, Any]:
    state = runtime.state if hasattr(runtime, "state") else {}
    return state if isinstance(state, dict) else {}


def _trim_text(value: Any, *, max_chars: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "...[truncated]"


def _extract_key_points(structured_data: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(structured_data, Mapping):
        return []
    raw_points = structured_data.get("key_points")
    if not isinstance(raw_points, list):
        return []
    key_points: list[str] = []
    for item in raw_points[:8]:
        text = str(item).strip()
        if text:
            key_points.append(text)
    return key_points


def _extract_source_refs(structured_data: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(structured_data, Mapping):
        return []
    raw_refs = structured_data.get("source_refs")
    if not isinstance(raw_refs, list):
        return []
    refs: list[dict[str, Any]] = []
    for item in raw_refs[:8]:
        if isinstance(item, Mapping):
            refs.append(dict(item))
    return refs


@tool(
    "read_multimodal_attachments",
    description=(
        "Read parsed multimodal attachment artifacts from runtime state and return a "
        "compact JSON payload for attachment-aware workflows."
    ),
)
def read_multimodal_attachments(runtime: ToolRuntime[None, Any]) -> str:
    state = _read_runtime_state(runtime)
    multimodal_summary = state.get("multimodal_summary")
    attachments_raw = state.get("multimodal_attachments")

    attachments: list[dict[str, Any]] = []
    if isinstance(attachments_raw, list):
        for item in attachments_raw:
            if not isinstance(item, Mapping):
                continue
            structured_data = (
                item.get("structured_data")
                if isinstance(item.get("structured_data"), Mapping)
                else None
            )
            attachments.append(
                {
                    "attachment_id": str(item.get("attachment_id") or ""),
                    "kind": str(item.get("kind") or ""),
                    "name": item.get("name"),
                    "status": str(item.get("status") or ""),
                    "summary_for_model": str(item.get("summary_for_model") or ""),
                    "parsed_text_preview": _trim_text(
                        item.get("parsed_text"), max_chars=1200
                    ),
                    "key_points": _extract_key_points(structured_data),
                    "source_refs": _extract_source_refs(structured_data),
                }
            )

    payload = {
        "multimodal_summary": (
            multimodal_summary.strip()
            if isinstance(multimodal_summary, str) and multimodal_summary.strip()
            else None
        ),
        "attachments": attachments,
    }
    return json.dumps(payload, ensure_ascii=False)


__all__ = ["read_multimodal_attachments"]
