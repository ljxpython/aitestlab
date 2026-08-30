from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from .types import (
    _DOC_MIME_TYPES,
    AttachmentArtifact,
    AttachmentKind,
    AttachmentStatus,
)


def _get_message_content(message: Any) -> Any:
    if hasattr(message, "content"):
        return getattr(message, "content")
    if isinstance(message, Mapping):
        return message.get("content")
    return None


def _get_message_type(message: Any) -> str | None:
    if hasattr(message, "type"):
        value = getattr(message, "type")
        return value if isinstance(value, str) else None
    if isinstance(message, Mapping):
        value = message.get("type")
        return value if isinstance(value, str) else None
    return None


def _is_attachment_block(item: Any) -> bool:
    return isinstance(item, Mapping) and item.get("type") in {"image", "file"}


def _copy_message_with_content(message: Any, content: Any) -> Any:
    if hasattr(message, "model_copy"):
        return message.model_copy(update={"content": content})
    if isinstance(message, Mapping):
        next_message = dict(message)
        next_message["content"] = content
        return next_message
    return message


def _resolve_mime_type(block: Mapping[str, Any]) -> str | None:
    raw = block.get("mime_type") or block.get("mimeType")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _resolve_attachment_name(block: Mapping[str, Any]) -> str | None:
    metadata = block.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("filename", "name", "title"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("filename", "name"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_attachment_kind(block_type: str, mime_type: str | None) -> AttachmentKind:
    if block_type == "image":
        return "image"
    if mime_type == "application/pdf":
        return "pdf"
    if mime_type in _DOC_MIME_TYPES:
        return _DOC_MIME_TYPES[mime_type]
    if block_type == "file":
        return "file"
    return "other"


def _resolve_attachment_status(kind: AttachmentKind) -> AttachmentStatus:
    if kind == "other":
        return "unsupported"
    return "unprocessed"


def _resolve_attachment_fingerprint(block: Mapping[str, Any]) -> str | None:
    payload = block.get("base64") or block.get("data")
    if not isinstance(payload, str) or not payload.strip():
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_content_block(item: Any) -> Any:
    if not isinstance(item, Mapping):
        return item

    block = dict(item)
    block_type = block.get("type")
    if block_type not in {"image", "file"}:
        return block

    normalized = dict(block)
    if "base64" not in normalized and isinstance(normalized.get("data"), str):
        normalized["base64"] = normalized["data"]
    mime_type = _resolve_mime_type(block)
    if mime_type and "mime_type" not in normalized:
        normalized["mime_type"] = mime_type
    return normalized


def normalize_message_content(content: Any) -> Any:
    if not isinstance(content, list):
        return content
    return [_normalize_content_block(item) for item in content]


def normalize_messages(messages: Sequence[Any]) -> list[Any]:
    normalized_messages: list[Any] = []
    for message in messages:
        content = _get_message_content(message)
        normalized_content = normalize_message_content(content)
        if normalized_content is content or normalized_content == content:
            normalized_messages.append(message)
            continue
        normalized_messages.append(
            _copy_message_with_content(message, normalized_content)
        )
    return normalized_messages


def _build_attachment_summary(
    kind: AttachmentKind,
    mime_type: str | None,
    name: str | None,
    status: AttachmentStatus,
) -> str:
    label = {
        "image": "图片",
        "pdf": "PDF",
        "doc": "DOC",
        "docx": "DOCX",
        "xlsx": "XLSX",
        "file": "文件",
        "other": "未知文件",
    }[kind]
    name_part = f"“{name}”" if name else "未命名附件"
    mime_part = f"（{mime_type}）" if mime_type else ""
    if status == "unsupported":
        return f"{label}附件 {name_part}{mime_part} 已识别，但当前不在 Phase 1 支持范围内。"
    return f"{label}附件 {name_part}{mime_part} 已识别；当前仅完成协议归一化与状态登记，尚未进行语义解析。"


def build_attachment_artifact(
    block: Mapping[str, Any], index: int
) -> AttachmentArtifact | None:
    block_type = block.get("type")
    if not isinstance(block_type, str) or block_type not in {"image", "file"}:
        return None

    mime_type = _resolve_mime_type(block)
    kind = _resolve_attachment_kind(block_type, mime_type)
    status = _resolve_attachment_status(kind)
    name = _resolve_attachment_name(block)
    fingerprint = _resolve_attachment_fingerprint(block)
    provenance: dict[str, Any] = {"phase": "phase1", "source": "message_block"}
    if fingerprint is not None:
        provenance["fingerprint"] = fingerprint
    artifact: AttachmentArtifact = {
        "attachment_id": f"att_{index}",
        "kind": kind,
        "mime_type": mime_type,
        "status": status,
        "source_type": block_type,
        "name": name,
        "summary_for_model": _build_attachment_summary(kind, mime_type, name, status),
        "parsed_text": None,
        "structured_data": None,
        "provenance": provenance,
        "confidence": None,
        "error": None,
    }
    payload = block.get("base64") or block.get("data")
    if isinstance(payload, str) and payload.strip():
        artifact["source_payload_base64"] = payload
    return artifact


def _find_latest_human_message_attachment_context(
    messages: Sequence[Any],
) -> tuple[int, Any, list[Any]] | None:
    for idx in range(len(messages) - 1, -1, -1):
        message = messages[idx]
        if _get_message_type(message) not in {"human", "user"}:
            continue
        content = _get_message_content(message)
        if not isinstance(content, list):
            continue
        if any(_is_attachment_block(item) for item in content):
            return idx, message, content
    return None


def _collect_attachment_pairs_from_content(
    content: Sequence[Any], *, start_index: int = 1
) -> list[tuple[AttachmentArtifact, Mapping[str, Any]]]:
    pairs: list[tuple[AttachmentArtifact, Mapping[str, Any]]] = []
    next_index = start_index
    for item in content:
        if not isinstance(item, Mapping):
            continue
        artifact = build_attachment_artifact(item, next_index)
        if artifact is None:
            continue
        pairs.append((artifact, item))
        next_index += 1
    return pairs


def collect_attachment_artifacts(messages: Sequence[Any]) -> list[AttachmentArtifact]:
    artifacts: list[AttachmentArtifact] = []
    next_index = 1
    for message in messages:
        content = _get_message_content(message)
        if not isinstance(content, list):
            continue
        pairs = _collect_attachment_pairs_from_content(content, start_index=next_index)
        artifacts.extend(artifact for artifact, _ in pairs)
        next_index += len(pairs)
    return artifacts


def get_latest_human_message_with_attachments(messages: Sequence[Any]) -> Any | None:
    context = _find_latest_human_message_attachment_context(messages)
    return None if context is None else context[1]


def collect_current_turn_attachment_artifacts(
    messages: Sequence[Any],
    *,
    start_index: int = 1,
) -> list[AttachmentArtifact]:
    context = _find_latest_human_message_attachment_context(messages)
    if context is None:
        return []
    _, _, content = context
    return [
        artifact
        for artifact, _ in _collect_attachment_pairs_from_content(
            content, start_index=start_index
        )
    ]
