from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from langchain.messages import SystemMessage

from .protocol import (
    _copy_message_with_content,
    _find_latest_human_message_attachment_context,
    _is_attachment_block,
)
from .types import (
    _MULTIMODAL_PROMPT_HEADER,
    AttachmentArtifact,
    MULTIMODAL_ATTACHMENTS_KEY,
    MULTIMODAL_SUMMARY_KEY,
    MultimodalAgentState,
)


def _artifact_model_text(artifact: AttachmentArtifact) -> str:
    return _artifact_model_text_with_options(
        artifact,
        include_parsed_text=False,
        parsed_text_max_chars=0,
    )


def _artifact_model_text_with_options(
    artifact: AttachmentArtifact,
    *,
    include_parsed_text: bool,
    parsed_text_max_chars: int,
) -> str:
    lines: list[str] = []
    name = artifact.get("name") or artifact.get("attachment_id") or "附件"
    kind = artifact.get("kind") or "file"
    lines.append(f"[附件: {name}; kind={kind}; status={artifact.get('status', 'unknown')}]")

    summary = artifact.get("summary_for_model")
    if isinstance(summary, str) and summary.strip():
        lines.append(f"摘要: {summary.strip()}")

    structured_data = artifact.get("structured_data")
    if isinstance(structured_data, Mapping) and structured_data:
        key_points = structured_data.get("key_points")
        if isinstance(key_points, list) and key_points:
            trimmed_points = [str(item).strip() for item in key_points[:6] if str(item).strip()]
            if trimmed_points:
                lines.append("关键要点:")
                lines.extend([f"- {item}" for item in trimmed_points])

    if include_parsed_text and parsed_text_max_chars > 0:
        parsed_text = artifact.get("parsed_text")
        if isinstance(parsed_text, str) and parsed_text.strip():
            trimmed = parsed_text.strip()
            preview = trimmed[:parsed_text_max_chars]
            suffix = " ...[已截断]" if len(trimmed) > parsed_text_max_chars else ""
            lines.append("解析文本片段:")
            lines.append(preview + suffix)

    return "\n".join(lines)


def _rewrite_latest_human_message_for_model(
    messages: Sequence[Any],
    artifacts: Sequence[AttachmentArtifact],
    *,
    include_parsed_text: bool = False,
    parsed_text_max_chars: int = 2000,
    rewrite_artifact_count: int | None = None,
) -> list[Any]:
    if not artifacts:
        return list(messages)

    context = _find_latest_human_message_attachment_context(messages)
    if context is None:
        return list(messages)

    latest_index, message, content = context

    limit = (
        len(artifacts)
        if rewrite_artifact_count is None
        else max(0, min(len(artifacts), rewrite_artifact_count))
    )
    artifact_iter = iter(artifacts[:limit])
    rewritten_content: list[Any] = []
    for item in content:
        if not _is_attachment_block(item):
            rewritten_content.append(item)
            continue

        artifact = next(artifact_iter, None)
        if artifact is None:
            rewritten_content.append(item)
            continue

        rewritten_content.append(
            {
                "type": "text",
                "text": _artifact_model_text_with_options(
                    artifact,
                    include_parsed_text=include_parsed_text,
                    parsed_text_max_chars=parsed_text_max_chars,
                ),
            }
        )

    rewritten_messages = list(messages)
    rewritten_messages[latest_index] = _copy_message_with_content(
        message, rewritten_content
    )
    return rewritten_messages


def build_multimodal_summary(artifacts: Sequence[AttachmentArtifact]) -> str | None:
    return build_multimodal_summary_with_options(
        artifacts,
        include_parsed_text=False,
        parsed_text_max_chars=0,
    )


def build_multimodal_summary_with_options(
    artifacts: Sequence[AttachmentArtifact],
    *,
    include_parsed_text: bool,
    parsed_text_max_chars: int,
) -> str | None:
    if not artifacts:
        return None
    lines = ["检测到以下多模态附件："]
    for artifact in artifacts:
        summary = artifact["summary_for_model"]
        if artifact["status"] == "failed":
            lines.append(f"- 附件解析失败：{summary}")
        elif artifact["status"] == "unsupported":
            lines.append(f"- 附件暂不支持：{summary}")
        else:
            lines.append(f"- {summary}")
            structured_data = artifact.get("structured_data")
            if isinstance(structured_data, Mapping):
                key_points = structured_data.get("key_points")
                if isinstance(key_points, list) and key_points:
                    trimmed_points = [str(item).strip() for item in key_points[:3] if str(item).strip()]
                    if trimmed_points:
                        lines.append("  关键要点:")
                        lines.extend([f"  - {item}" for item in trimmed_points])
            if include_parsed_text and parsed_text_max_chars > 0:
                parsed_text = artifact.get("parsed_text")
                if isinstance(parsed_text, str) and parsed_text.strip():
                    trimmed = parsed_text.strip()
                    preview = trimmed[:parsed_text_max_chars]
                    suffix = " ...[已截断]" if len(trimmed) > parsed_text_max_chars else ""
                    lines.append("  解析文本片段:")
                    lines.append(f"  {preview}{suffix}")
    lines.append(
        "请优先基于高层摘要和关键要点理解附件；更长的原始解析文本应由工具在需要时从状态中读取，而不是由模型直接搬运为工具参数。"
    )
    return "\n".join(lines)


def _apply_multimodal_state(
    state: MultimodalAgentState, artifacts: Sequence[AttachmentArtifact]
) -> MultimodalAgentState:
    if artifacts:
        state[MULTIMODAL_ATTACHMENTS_KEY] = list(artifacts)
    else:
        state.pop(MULTIMODAL_ATTACHMENTS_KEY, None)

    summary = build_multimodal_summary(artifacts)
    if summary:
        state[MULTIMODAL_SUMMARY_KEY] = summary
    else:
        state.pop(MULTIMODAL_SUMMARY_KEY, None)
    return state


def _extract_system_message_text(existing: SystemMessage | None) -> str:
    if existing is None:
        return ""
    if isinstance(existing.content, str):
        return existing.content

    text_parts: list[str] = []
    for block in existing.content_blocks:
        if not isinstance(block, Mapping):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str):
            text_parts.append(text)
    return "".join(text_parts)


def build_multimodal_system_message(
    existing: SystemMessage | None, summary: str | None
) -> SystemMessage | None:
    header = f"\n\n{_MULTIMODAL_PROMPT_HEADER}"
    existing_content = _extract_system_message_text(existing)
    if _MULTIMODAL_PROMPT_HEADER in existing_content:
        existing_content = existing_content.split(
            f"\n\n{_MULTIMODAL_PROMPT_HEADER}", 1
        )[0].rstrip()
        if not existing_content:
            existing_content = existing_content.strip()
    if not summary:
        return SystemMessage(content=existing_content) if existing_content else None
    content = (
        f"{existing_content}{header}{summary}"
        if existing_content
        else f"{_MULTIMODAL_PROMPT_HEADER}{summary}"
    )
    return SystemMessage(content=content)
