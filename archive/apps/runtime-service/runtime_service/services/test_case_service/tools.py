from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from runtime_service.integrations import (
    InteractionDataServiceClient,
    build_interaction_data_service_config,
)
from runtime_service.runtime.context import RuntimeContext
from runtime_service.services.test_case_service.document_persistence import (
    INVALID_PROJECT_ID_ERROR,
    MISSING_PROJECT_ID_ERROR,
    _coerce_string_list,
    _get_runtime_state,
    _require_uuid_project_id,
    _resolve_batch_id,
    _resolve_runtime_meta,
    collect_persisted_document_ids,
    persist_runtime_documents,
)
from runtime_service.services.test_case_service.schemas import (
    PersistTestCaseItem,
    TestCaseServiceConfig,
)
from runtime_service.tools.multimodal import read_multimodal_attachments

TEST_CASES_PATH = "/api/test-case-service/test-cases"


def _normalize_identity_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).casefold()


def _build_test_case_identity(item: PersistTestCaseItem) -> dict[str, Any]:
    normalized_case_id = _normalize_identity_text(item.case_id)
    if normalized_case_id:
        return {"mode": "case_id", "case_id": normalized_case_id}
    return {
        "mode": "semantic_title",
        "title": _normalize_identity_text(item.title),
        "module_name": _normalize_identity_text(item.module_name),
        "test_type": _normalize_identity_text(item.test_type),
    }


def _build_test_case_idempotency_keys(
    items: list[PersistTestCaseItem],
) -> list[str]:
    occurrence_by_identity: dict[str, int] = {}
    keys: list[str] = []
    for item in items:
        identity = _build_test_case_identity(item)
        identity_text = json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        occurrence = occurrence_by_identity.get(identity_text, 0) + 1
        occurrence_by_identity[identity_text] = occurrence
        digest_source = json.dumps(
            {"version": 1, "identity": identity, "occurrence": occurrence},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(digest_source).hexdigest()
        keys.append(f"tc:{digest[:40]}")
    return keys


def _merge_content_json(
    item: PersistTestCaseItem,
    *,
    bundle_title: str,
    bundle_summary: str,
    quality_review: dict[str, Any],
    export_format: str | None,
    runtime_meta: dict[str, Any],
    batch_id: str,
    source_document_ids: list[str],
    idempotency_key: str,
) -> dict[str, Any]:
    content = dict(item.content_json)
    content.setdefault("case_id", item.case_id)
    content.setdefault("title", item.title)
    content.setdefault("description", item.description)
    content.setdefault("module_name", item.module_name)
    content.setdefault("priority", item.priority)
    content.setdefault("test_type", item.test_type)
    content.setdefault("design_technique", item.design_technique)
    content.setdefault("preconditions", list(item.preconditions))
    content.setdefault("steps", list(item.steps))
    content.setdefault("test_data", dict(item.test_data))
    content.setdefault("expected_results", list(item.expected_results))
    content.setdefault("remarks", item.remarks)
    meta = content.get("meta") if isinstance(content.get("meta"), dict) else {}
    meta.update(
        {
            "bundle_title": bundle_title,
            "bundle_summary": bundle_summary,
            "quality_review": quality_review,
            "export_format": export_format,
            "batch_id": batch_id,
            "source_document_ids": source_document_ids,
            "test_case_idempotency_key": idempotency_key,
            **runtime_meta,
        }
    )
    content["meta"] = meta
    return content


def _build_test_case_payloads(
    *,
    items: list[PersistTestCaseItem],
    project_id: str,
    batch_id: str,
    source_document_ids: list[str],
    bundle_title: str,
    bundle_summary: str,
    quality_review: dict[str, Any],
    export_format: str | None,
    runtime_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    idempotency_keys = _build_test_case_idempotency_keys(items)
    for item, idempotency_key in zip(items, idempotency_keys, strict=False):
        content_json = _merge_content_json(
            item,
            bundle_title=bundle_title,
            bundle_summary=bundle_summary,
            quality_review=quality_review,
            export_format=export_format,
            runtime_meta=runtime_meta,
            batch_id=batch_id,
            source_document_ids=source_document_ids,
            idempotency_key=idempotency_key,
        )
        payloads.append(
            {
                "project_id": project_id,
                "batch_id": batch_id,
                "idempotency_key": idempotency_key,
                "case_id": item.case_id,
                "title": item.title,
                "description": item.description,
                "status": item.status,
                "module_name": item.module_name,
                "priority": item.priority,
                "source_document_ids": source_document_ids,
                "content_json": content_json,
            }
        )
    return payloads


def _persist_test_case_payloads(
    *,
    client: InteractionDataServiceClient,
    payloads: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    persisted_items: list[dict[str, Any]] = []
    failed_items: list[dict[str, str]] = []
    for payload in payloads:
        try:
            persisted_items.append(client.post_json(TEST_CASES_PATH, payload))
        except Exception as exc:
            failed_items.append(
                {
                    "title": str(payload.get("title") or ""),
                    "idempotency_key": str(payload.get("idempotency_key") or ""),
                    "error": str(exc),
                }
            )
    return persisted_items, failed_items


def build_test_case_service_tools(service_config: TestCaseServiceConfig) -> list[Any]:
    @tool(
        "persist_test_case_results",
        description=(
            "Persist the final formatted test cases and uploaded requirement documents to "
            "interaction-data-service. Use this only after requirement analysis, strategy, "
            "test-case design, quality review, and output formatting are complete."
        ),
    )
    def persist_test_case_results(
        bundle_title: str,
        runtime: ToolRuntime[RuntimeContext | Mapping[str, Any] | None, dict[str, Any]],
        bundle_summary: str = "",
        test_cases: list[PersistTestCaseItem] | None = None,
        quality_review: dict[str, Any] | None = None,
        export_format: str | None = None,
    ) -> str:
        if not service_config.persistence_enabled:
            return json.dumps(
                {
                    "status": "skipped_persistence_disabled",
                    "reason": "test_case_persistence_enabled=false",
                },
                ensure_ascii=False,
            )
        normalized_cases = test_cases or []
        if not normalized_cases:
            return json.dumps(
                {
                    "status": "skipped_empty_test_cases",
                    "reason": "no_test_cases",
                },
                ensure_ascii=False,
            )
        batch_id = _resolve_batch_id(runtime)
        runtime_meta = _resolve_runtime_meta(runtime)
        try:
            project_id = _require_uuid_project_id(runtime)
        except ValueError as exc:
            reason = str(exc)
            status = (
                "failed_missing_project_id"
                if reason == MISSING_PROJECT_ID_ERROR
                else "failed_invalid_project_id"
            )
            return json.dumps(
                {
                    "status": status,
                    "reason": reason,
                    "batch_id": batch_id,
                    "test_case_count": len(normalized_cases),
                },
                ensure_ascii=False,
            )
        state = _get_runtime_state(runtime)
        client = InteractionDataServiceClient(build_interaction_data_service_config(runtime.config))
        if not client.is_configured:
            return json.dumps(
                {
                    "status": "skipped_remote_not_configured",
                    "project_id": project_id,
                    "batch_id": batch_id,
                    "test_case_count": len(normalized_cases),
                },
                ensure_ascii=False,
            )
        document_outcome = persist_runtime_documents(
            runtime=runtime,
            state=state,
            service_config=service_config,
            client=client,
            messages=state.get("messages") if isinstance(state.get("messages"), list) else None,
        )
        if isinstance(state, dict):
            state["multimodal_attachments"] = document_outcome.attachments
        source_document_ids = collect_persisted_document_ids(
            {"multimodal_attachments": document_outcome.attachments}
        )
        if not source_document_ids and document_outcome.persisted_documents:
            source_document_ids = _coerce_string_list(
                [item.get("id") for item in document_outcome.persisted_documents]
            )
        quality_payload = quality_review or {}
        test_case_payloads = _build_test_case_payloads(
            items=normalized_cases,
            project_id=project_id,
            batch_id=batch_id,
            source_document_ids=source_document_ids,
            bundle_title=bundle_title,
            bundle_summary=bundle_summary,
            quality_review=quality_payload,
            export_format=export_format,
            runtime_meta=runtime_meta,
        )
        persisted_test_cases, failed_test_cases = _persist_test_case_payloads(
            client=client,
            payloads=test_case_payloads,
        )
        if failed_test_cases:
            status = "partial_failed" if persisted_test_cases else "failed_remote_request"
            return json.dumps(
                {
                    "status": status,
                    "project_id": project_id,
                    "batch_id": batch_id,
                    "document_status": document_outcome.status,
                    "persisted_document_count": len(source_document_ids),
                    "persisted_document_ids": source_document_ids,
                    "persisted_test_case_count": len(persisted_test_cases),
                    "persisted_test_case_ids": _coerce_string_list(
                        [item.get("id") for item in persisted_test_cases]
                    ),
                    "failed_test_case_count": len(failed_test_cases),
                    "failed_test_cases": failed_test_cases,
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "status": "persisted",
                "project_id": project_id,
                "batch_id": batch_id,
                "document_status": document_outcome.status,
                "persisted_document_count": len(source_document_ids),
                "persisted_document_ids": source_document_ids,
                "persisted_test_case_count": len(persisted_test_cases),
                "persisted_test_case_ids": _coerce_string_list(
                    [item.get("id") for item in persisted_test_cases]
                ),
            },
            ensure_ascii=False,
        )

    return [persist_test_case_results, read_multimodal_attachments]


__all__ = ["build_test_case_service_tools"]
