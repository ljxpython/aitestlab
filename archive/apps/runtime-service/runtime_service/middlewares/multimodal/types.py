from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal

from langchain.agents import AgentState
from typing_extensions import NotRequired, TypedDict

AttachmentKind = Literal["image", "pdf", "doc", "docx", "xlsx", "file", "other"]
AttachmentStatus = Literal["unprocessed", "parsed", "unsupported", "failed"]
DocumentAttachmentKind = Literal["doc", "docx", "xlsx"]

MULTIMODAL_ATTACHMENTS_KEY = "multimodal_attachments"
MULTIMODAL_SUMMARY_KEY = "multimodal_summary"
DEFAULT_MULTIMODAL_MODEL_ID = "doubao_vision_mini"
MULTIMODAL_PARSER_MODEL_ID_ENV = "MULTIMODAL_PARSER_MODEL_ID"
_MULTIMODAL_PROMPT_HEADER = "## Multimodal Attachments\n"

_DOC_MIME_TYPES: dict[str, DocumentAttachmentKind] = {
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}


class AttachmentArtifact(TypedDict):
    attachment_id: str
    kind: AttachmentKind
    mime_type: str | None
    status: AttachmentStatus
    source_type: str
    name: str | None
    summary_for_model: str
    parsed_text: str | None
    structured_data: dict[str, Any] | None
    provenance: dict[str, Any]
    confidence: float | None
    error: dict[str, Any] | None
    source_payload_base64: NotRequired[str | None]
    persisted_document_id: NotRequired[str | None]
    persist_status: NotRequired[str | None]
    persisted_at: NotRequired[str | None]
    persist_error: NotRequired[dict[str, Any] | None]


ParserResult = TypedDict(
    "ParserResult",
    {
        "summary_for_model": str,
        "parsed_text": str | None,
        "structured_data": dict[str, Any] | None,
        "confidence": float | None,
    },
)


AttachmentParser = Callable[[AttachmentArtifact, Mapping[str, Any]], AttachmentArtifact]
AsyncAttachmentParser = Callable[
    [AttachmentArtifact, Mapping[str, Any]], Awaitable[AttachmentArtifact]
]


def get_default_multimodal_model_id() -> str:
    env_value = str(os.getenv(MULTIMODAL_PARSER_MODEL_ID_ENV) or "").strip()
    return env_value or DEFAULT_MULTIMODAL_MODEL_ID


class MultimodalAgentState(AgentState):
    multimodal_attachments: list[AttachmentArtifact] | None
    multimodal_summary: str | None
