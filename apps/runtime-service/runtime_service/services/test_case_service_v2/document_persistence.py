from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from langgraph.config import get_config
from runtime_service.integrations import (
    InteractionDataServiceClient,
    build_interaction_data_service_config,
)
from runtime_service.middlewares.multimodal import MULTIMODAL_ATTACHMENTS_KEY
from runtime_service.middlewares.multimodal import protocol as _multimodal_protocol
from runtime_service.runtime.config_utils import read_configurable
from runtime_service.runtime.runtime_request_resolver import resolve_trusted_runtime_context
from runtime_service.services.test_case_service_v2.schemas import TestCaseServiceConfig

TEST_CASE_DOCUMENTS_PATH = "/api/test-case-service/documents"
TEST_CASE_DOCUMENT_ASSETS_PATH = "/api/test-case-service/documents/assets"
PERSIST_STATUS_PENDING = "pending"
PERSIST_STATUS_PERSISTED = "persisted"
PERSIST_STATUS_FAILED = "failed"
PERSIST_STATUS_SKIPPED = "skipped"
MISSING_PROJECT_ID_ERROR = "test_case_project_id_required"
INVALID_PROJECT_ID_ERROR = "test_case_project_id_must_be_uuid"


@dataclass(frozen=True)
class DocumentPersistenceOutcome:
    status: str
    project_id: str | None
    batch_id: str | None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    persisted_documents: list[dict[str, Any]] = field(default_factory=list)
    persisted_document_ids: list[str] = field(default_factory=list)
    failed_attachment_ids: list[str] = field(default_factory=list)
    skipped_attachment_ids: list[str] = field(default_factory=list)


def _coerce_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {str(key): item for key, item in value.items()}


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _coerce_optional_text(item)
        if text:
            items.append(text)
    return items


def _get_state_messages(state: Mapping[str, Any] | None) -> list[Any]:
    if not isinstance(state, Mapping):
        return []
    messages = state.get("messages")
    return list(messages) if isinstance(messages, list) else []


def _get_runtime_state(
    runtime: Any,
) -> dict[str, Any]:
    state = getattr(runtime, "state", {})
    return state if isinstance(state, dict) else {}


def _get_runtime_config(runtime: Any) -> Mapping[str, Any]:
    config = getattr(runtime, "config", None)
    if isinstance(config, Mapping):
        return config
    try:
        fallback = get_config()
    except RuntimeError:
        return {}
    return fallback if isinstance(fallback, Mapping) else {}


def _resolve_project_id(runtime: Any) -> str | None:
    try:
        context = resolve_trusted_runtime_context(runtime)
    except ValueError:
        return None
    return _coerce_optional_text(context.project_id)


def _require_project_id(runtime: Any) -> str:
    project_id = _resolve_project_id(runtime)
    if project_id:
        return project_id
    raise ValueError(MISSING_PROJECT_ID_ERROR)


def _is_valid_uuid_text(value: Any) -> bool:
    text = _coerce_optional_text(value)
    if not text:
        return False
    try:
        UUID(text)
    except ValueError:
        return False
    return True


def _require_uuid_project_id(runtime: Any) -> str:
    project_id = _require_project_id(runtime)
    if _is_valid_uuid_text(project_id):
        return project_id
    raise ValueError(INVALID_PROJECT_ID_ERROR)


def _resolve_batch_id(runtime: Any) -> str:
    config = _get_runtime_config(runtime)
    configurable = read_configurable(config)
    metadata = config.get("metadata")
    metadata_map = metadata if isinstance(metadata, Mapping) else {}
    state = _get_runtime_state(runtime)
    thread_id = _coerce_optional_text(configurable.get("thread_id") or state.get("thread_id"))
    run_id = _coerce_optional_text(config.get("run_id"))
    explicit = _coerce_optional_text(
        configurable.get("batch_id") or metadata_map.get("batch_id") or state.get("batch_id")
    )
    if explicit:
        return explicit
    suffix = thread_id or run_id or "default"
    return f"test-case-service:{suffix}"


def _resolve_runtime_meta(runtime: Any) -> dict[str, Any]:
    config = _get_runtime_config(runtime)
    configurable = read_configurable(config)
    state = _get_runtime_state(runtime)
    return {
        "thread_id": _coerce_optional_text(configurable.get("thread_id") or state.get("thread_id")),
        "run_id": _coerce_optional_text(config.get("run_id")),
        "agent_key": "test_case_service_v2",
    }


def _build_document_idempotency_key(attachment: Mapping[str, Any], *, batch_id: str) -> str:
    provenance = _coerce_mapping(attachment.get("provenance")) or {}
    fingerprint = _coerce_optional_text(provenance.get("fingerprint"))
    if fingerprint:
        return fingerprint

    payload = {
        "batch_id": batch_id,
        "attachment_id": _coerce_optional_text(attachment.get("attachment_id")),
        "kind": _coerce_optional_text(attachment.get("kind")),
        "mime_type": _coerce_optional_text(attachment.get("mime_type")),
        "name": _coerce_optional_text(attachment.get("name")),
        "summary_for_model": _coerce_optional_text(attachment.get("summary_for_model")),
        "parsed_text": _coerce_optional_text(attachment.get("parsed_text")),
        "structured_data": _coerce_mapping(attachment.get("structured_data")),
        "source_type": _coerce_optional_text(attachment.get("source_type")),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_document_payload(
    *,
    attachment: Mapping[str, Any],
    state: Mapping[str, Any],
    project_id: str,
    batch_id: str,
    runtime_meta: Mapping[str, Any],
    idempotency_key: str,
    storage_path: str | None,
    asset_payload: Mapping[str, Any] | None,
    asset_error: str | None,
) -> dict[str, Any] | None:
    parse_status = _coerce_optional_text(attachment.get("status")) or "unprocessed"
    if parse_status == "unprocessed":
        return None

    filename = (
        _coerce_optional_text(attachment.get("name"))
        or _coerce_optional_text(attachment.get("attachment_id"))
        or "attachment"
    )
    content_type = _coerce_optional_text(attachment.get("mime_type")) or "application/octet-stream"
    source_kind = (
        _coerce_optional_text(attachment.get("kind"))
        or _coerce_optional_text(attachment.get("source_type"))
        or "upload"
    )
    multimodal_summary = _coerce_optional_text(state.get("multimodal_summary")) or ""
    provenance = _coerce_mapping(attachment.get("provenance")) or {}
    runtime_section = _coerce_mapping(provenance.get("runtime")) or {}
    runtime_section.update(
        {
            key: value
            for key, value in runtime_meta.items()
            if _coerce_optional_text(value)
        }
    )
    provenance["runtime"] = runtime_section
    asset_section = _coerce_mapping(provenance.get("asset")) or {}
    if storage_path:
        asset_section["storage_path"] = storage_path
    if isinstance(asset_payload, Mapping):
        for key in ("filename", "content_type", "size", "sha256"):
            if asset_payload.get(key) is not None:
                asset_section[key] = asset_payload.get(key)
    if asset_error:
        asset_section["error"] = asset_error
    elif asset_section.get("error") is not None:
        asset_section.pop("error", None)
    if asset_section:
        provenance["asset"] = asset_section
    return {
        "project_id": project_id,
        "batch_id": batch_id,
        "idempotency_key": idempotency_key,
        "filename": filename,
        "content_type": content_type,
        "storage_path": storage_path,
        "source_kind": source_kind,
        "parse_status": parse_status,
        "summary_for_model": (
            _coerce_optional_text(attachment.get("summary_for_model"))
            or multimodal_summary
            or f"Parsed {source_kind} attachment."
        ),
        "parsed_text": _coerce_optional_text(attachment.get("parsed_text")),
        "structured_data": _coerce_mapping(attachment.get("structured_data")),
        "provenance": provenance,
        "confidence": attachment.get("confidence")
        if isinstance(attachment.get("confidence"), (int, float))
        else None,
        "error": _coerce_mapping(attachment.get("error")),
    }


def _collect_attachment_blocks_by_fingerprint(
    messages: list[Any] | None,
) -> dict[str, Mapping[str, Any]]:
    normalized_messages = _multimodal_protocol.normalize_messages(messages or [])
    blocks_by_fingerprint: dict[str, Mapping[str, Any]] = {}
    next_index = 1
    for message in normalized_messages:
        content = getattr(message, "content", None)
        if content is None and isinstance(message, Mapping):
            content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, Mapping):
                continue
            artifact = _multimodal_protocol.build_attachment_artifact(item, next_index)
            if artifact is None:
                continue
            next_index += 1
            provenance = _coerce_mapping(artifact.get("provenance")) or {}
            fingerprint = _coerce_optional_text(provenance.get("fingerprint"))
            if fingerprint and fingerprint not in blocks_by_fingerprint:
                blocks_by_fingerprint[fingerprint] = item
    return blocks_by_fingerprint


def _decode_block_payload(block: Mapping[str, Any] | None) -> bytes | None:
    if not isinstance(block, Mapping):
        return None
    payload = block.get("base64") or block.get("data")
    if not isinstance(payload, str) or not payload.strip():
        return None
    try:
        return base64.b64decode(payload)
    except Exception:
        return None


def _decode_attachment_payload(attachment: Mapping[str, Any]) -> bytes | None:
    payload = attachment.get("source_payload_base64")
    if not isinstance(payload, str) or not payload.strip():
        return None
    try:
        return base64.b64decode(payload)
    except Exception:
        return None


def _upload_document_asset(
    *,
    client: InteractionDataServiceClient,
    attachment: Mapping[str, Any],
    source_block: Mapping[str, Any] | None,
    project_id: str,
    batch_id: str,
    idempotency_key: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if (_coerce_optional_text(attachment.get("status")) or "unprocessed") == "unprocessed":
        return None, None
    file_bytes = _decode_attachment_payload(attachment) or _decode_block_payload(source_block)
    if file_bytes is None:
        return None, "raw_attachment_payload_missing"
    filename = (
        _coerce_optional_text(attachment.get("name"))
        or _coerce_optional_text(attachment.get("attachment_id"))
        or "document"
    )
    content_type = _coerce_optional_text(attachment.get("mime_type")) or "application/octet-stream"
    try:
        payload = client.post_multipart(
            TEST_CASE_DOCUMENT_ASSETS_PATH,
            form_data={
                "project_id": project_id,
                "batch_id": batch_id,
                "idempotency_key": idempotency_key,
                "filename": filename,
                "content_type": content_type,
            },
            file_field_name="file",
            file_name=filename,
            file_bytes=file_bytes,
            content_type=content_type,
        )
        return payload, None
    except Exception as exc:
        return None, str(exc)


def collect_persisted_document_ids(state: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(state, Mapping):
        return []
    attachments = state.get(MULTIMODAL_ATTACHMENTS_KEY)
    if not isinstance(attachments, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in attachments:
        if not isinstance(item, Mapping):
            continue
        document_id = _coerce_optional_text(item.get("persisted_document_id"))
        persist_status = _coerce_optional_text(item.get("persist_status"))
        if document_id and persist_status == PERSIST_STATUS_PERSISTED and document_id not in seen:
            seen.add(document_id)
            ids.append(document_id)
    return ids


def _mark_attachment_status(
    attachment: dict[str, Any],
    *,
    status: str,
    error_message: str | None = None,
    persisted_document_id: str | None = None,
    persisted_at: str | None = None,
    storage_path: str | None = None,
) -> dict[str, Any]:
    attachment.pop("source_payload_base64", None)
    attachment["persist_status"] = status
    if persisted_document_id is not None:
        attachment["persisted_document_id"] = persisted_document_id
    if persisted_at is not None:
        attachment["persisted_at"] = persisted_at
    if storage_path is not None:
        attachment["storage_path"] = storage_path
    if error_message:
        attachment["persist_error"] = {"message": error_message}
    else:
        attachment.pop("persist_error", None)
    return attachment


def persist_runtime_documents(
    *,
    runtime: Any,
    state: Mapping[str, Any] | None,
    service_config: TestCaseServiceConfig,
    client: InteractionDataServiceClient | None = None,
    messages: list[Any] | None = None,
) -> DocumentPersistenceOutcome:
    current_state = dict(state or {})
    attachments_raw = current_state.get(MULTIMODAL_ATTACHMENTS_KEY)
    if not isinstance(attachments_raw, list):
        return DocumentPersistenceOutcome(
            status="no_attachments",
            project_id=None,
            batch_id=None,
        )

    resolved_config = _get_runtime_config(runtime)
    resolved_context = getattr(runtime, "context", None) if runtime is not None else None
    resolved_server_info = (
        getattr(runtime, "server_info", None) if runtime is not None else None
    )
    runtime_like = type(
        "_RuntimeProxy",
        (),
        {
            "state": current_state,
            "config": resolved_config,
            "context": resolved_context,
            "server_info": resolved_server_info,
        },
    )()
    project_id = _require_uuid_project_id(runtime_like)
    batch_id = _resolve_batch_id(runtime_like)
    resolved_client = client or InteractionDataServiceClient(
        build_interaction_data_service_config(runtime_like.config)
    )
    runtime_meta = _resolve_runtime_meta(runtime_like)
    source_messages = list(messages) if isinstance(messages, list) else _get_state_messages(current_state)
    source_blocks_by_fingerprint = _collect_attachment_blocks_by_fingerprint(source_messages)
    updated_attachments: list[dict[str, Any]] = []
    persisted_documents: list[dict[str, Any]] = []
    failed_attachment_ids: list[str] = []
    skipped_attachment_ids: list[str] = []

    for raw_item in attachments_raw:
        if not isinstance(raw_item, Mapping):
            continue
        attachment = dict(raw_item)
        attachment_id = _coerce_optional_text(attachment.get("attachment_id")) or "attachment"
        persisted_document_id = _coerce_optional_text(attachment.get("persisted_document_id"))
        persist_status = _coerce_optional_text(attachment.get("persist_status"))

        if persisted_document_id and persist_status == PERSIST_STATUS_PERSISTED:
            updated_attachments.append(attachment)
            persisted_documents.append({"id": persisted_document_id})
            continue

        idempotency_key = _build_document_idempotency_key(attachment, batch_id=batch_id)
        provenance = _coerce_mapping(attachment.get("provenance")) or {}
        fingerprint = _coerce_optional_text(provenance.get("fingerprint"))
        source_block = (
            source_blocks_by_fingerprint.get(fingerprint)
            if fingerprint
            else None
        )
        asset_payload: dict[str, Any] | None = None
        asset_error: str | None = None
        if resolved_client.is_configured:
            asset_payload, asset_error = _upload_document_asset(
                client=resolved_client,
                attachment=attachment,
                source_block=source_block,
                project_id=project_id,
                batch_id=batch_id,
                idempotency_key=idempotency_key,
            )

        payload = _build_document_payload(
            attachment=attachment,
            state=current_state,
            project_id=project_id,
            batch_id=batch_id,
            runtime_meta=runtime_meta,
            idempotency_key=idempotency_key,
            storage_path=_coerce_optional_text(
                asset_payload.get("storage_path") if isinstance(asset_payload, Mapping) else None
            ),
            asset_payload=asset_payload,
            asset_error=asset_error,
        )
        if payload is None:
            updated_attachments.append(
                _mark_attachment_status(attachment, status=PERSIST_STATUS_PENDING)
            )
            skipped_attachment_ids.append(attachment_id)
            continue

        if not resolved_client.is_configured:
            updated_attachments.append(
                _mark_attachment_status(
                    attachment,
                    status=PERSIST_STATUS_SKIPPED,
                    error_message="interaction_data_service_not_configured",
                )
            )
            skipped_attachment_ids.append(attachment_id)
            continue

        try:
            persisted = resolved_client.post_json(TEST_CASE_DOCUMENTS_PATH, payload)
            document_id = _coerce_optional_text(persisted.get("id"))
            persisted_at = _coerce_optional_text(persisted.get("created_at"))
            updated_attachments.append(
                _mark_attachment_status(
                    attachment,
                    status=PERSIST_STATUS_PERSISTED,
                    persisted_document_id=document_id,
                    persisted_at=persisted_at,
                    storage_path=_coerce_optional_text(persisted.get("storage_path")),
                )
            )
            persisted_documents.append(persisted)
        except Exception as exc:
            updated_attachments.append(
                _mark_attachment_status(
                    attachment,
                    status=PERSIST_STATUS_FAILED,
                    error_message=str(exc),
                )
            )
            failed_attachment_ids.append(attachment_id)

    persisted_document_ids = _coerce_string_list(
        [item.get("id") for item in persisted_documents]
    )
    if failed_attachment_ids:
        status = "partial_failed" if persisted_document_ids else "failed"
    elif persisted_document_ids:
        status = "persisted"
    elif skipped_attachment_ids:
        status = "skipped"
    else:
        status = "no_attachments"

    return DocumentPersistenceOutcome(
        status=status,
        project_id=project_id,
        batch_id=batch_id,
        attachments=updated_attachments,
        persisted_documents=persisted_documents,
        persisted_document_ids=persisted_document_ids,
        failed_attachment_ids=failed_attachment_ids,
        skipped_attachment_ids=skipped_attachment_ids,
    )


async def apersist_runtime_documents(
    *,
    runtime: Any,
    state: Mapping[str, Any] | None,
    service_config: TestCaseServiceConfig,
    client: InteractionDataServiceClient | None = None,
    messages: list[Any] | None = None,
) -> DocumentPersistenceOutcome:
    return await asyncio.to_thread(
        persist_runtime_documents,
        runtime=runtime,
        state=state,
        service_config=service_config,
        client=client,
        messages=messages,
    )


__all__ = [
    "DocumentPersistenceOutcome",
    "PERSIST_STATUS_FAILED",
    "PERSIST_STATUS_PENDING",
    "PERSIST_STATUS_PERSISTED",
    "PERSIST_STATUS_SKIPPED",
    "TEST_CASE_DOCUMENT_ASSETS_PATH",
    "TEST_CASE_DOCUMENTS_PATH",
    "_coerce_mapping",
    "_coerce_optional_text",
    "_coerce_string_list",
    "_get_runtime_state",
    "_get_runtime_config",
    "_require_project_id",
    "_require_uuid_project_id",
    "_resolve_batch_id",
    "_resolve_project_id",
    "_resolve_runtime_meta",
    "_is_valid_uuid_text",
    "INVALID_PROJECT_ID_ERROR",
    "MISSING_PROJECT_ID_ERROR",
    "apersist_runtime_documents",
    "collect_persisted_document_ids",
    "persist_runtime_documents",
]
