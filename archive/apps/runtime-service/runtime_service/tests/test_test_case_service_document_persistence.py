from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.devtools.multimodal_frontend_compat import build_human_message_from_paths
from runtime_service.middlewares.multimodal import MULTIMODAL_ATTACHMENTS_KEY
from runtime_service.middlewares.multimodal import protocol as multimodal_protocol
from runtime_service.services.test_case_service.document_persistence import (
    INVALID_PROJECT_ID_ERROR,
    MISSING_PROJECT_ID_ERROR,
    PERSIST_STATUS_PERSISTED,
    persist_runtime_documents,
)
from runtime_service.services.test_case_service.schemas import (
    TestCaseServiceConfig as ServiceConfig,
)


class _FakeInteractionDataClient:
    def __init__(self) -> None:
        self.multipart_requests: list[dict[str, Any]] = []
        self.json_requests: list[dict[str, Any]] = []

    @property
    def is_configured(self) -> bool:
        return True

    def post_multipart(
        self,
        path: str,
        *,
        form_data: dict[str, Any],
        file_field_name: str,
        file_name: str,
        file_bytes: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        self.multipart_requests.append(
            {
                "path": path,
                "form_data": dict(form_data),
                "file_field_name": file_field_name,
                "file_name": file_name,
                "file_bytes": file_bytes,
                "content_type": content_type,
            }
        )
        extension = Path(file_name).suffix or ".bin"
        return {
            "storage_path": f"test-case-service/{form_data['project_id']}/{form_data['batch_id']}/asset{extension}",
            "filename": file_name,
            "content_type": content_type,
            "size": len(file_bytes),
            "sha256": "fake-sha256",
        }

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.json_requests.append({"path": path, "payload": dict(payload)})
        return {
            "id": "doc-1",
            "storage_path": payload.get("storage_path"),
            "created_at": "2026-03-31T14:00:00+08:00",
        }


def _server_info(project_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        user={
            "identity": "user-1",
            "tenant_id": "tenant-1",
            "role": "project_editor",
            "permissions": ["runtime:write"],
            "project_id": project_id,
        }
    )


def test_persist_runtime_documents_uploads_pdf_asset_from_request_messages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    pdf_path.write_bytes(pdf_bytes)

    message = build_human_message_from_paths("请分析附件", [pdf_path])
    normalized_messages = multimodal_protocol.normalize_messages([message])
    attachments = multimodal_protocol.collect_current_turn_attachment_artifacts(normalized_messages)
    assert len(attachments) == 1

    attachment = dict(attachments[0])
    attachment["status"] = "parsed"
    attachment["summary_for_model"] = "PDF 已解析"
    attachment["parsed_text"] = "这是 PDF 的解析结果"

    state = {MULTIMODAL_ATTACHMENTS_KEY: [attachment]}
    runtime = SimpleNamespace(
        state=state,
        config={
            "configurable": {
                "thread_id": "thread-test-1",
                "batch_id": "test-case-service:batch-test-1",
            }
        },
        server_info=_server_info("5f419550-a3c7-49c6-9450-09154fd1bf7d"),
    )
    client = _FakeInteractionDataClient()

    outcome = persist_runtime_documents(
        runtime=runtime,
        state=state,
        service_config=ServiceConfig(),
        client=client,
        messages=normalized_messages,
    )

    assert outcome.status == "persisted"
    assert len(client.multipart_requests) == 1
    assert client.multipart_requests[0]["file_bytes"] == pdf_bytes
    assert client.multipart_requests[0]["file_name"] == "sample.pdf"
    assert len(client.json_requests) == 1
    assert client.json_requests[0]["payload"]["storage_path"] == (
        "test-case-service/5f419550-a3c7-49c6-9450-09154fd1bf7d/"
        "test-case-service:batch-test-1/asset.pdf"
    )
    assert outcome.attachments[0]["persist_status"] == PERSIST_STATUS_PERSISTED
    assert outcome.attachments[0]["storage_path"] == (
        "test-case-service/5f419550-a3c7-49c6-9450-09154fd1bf7d/"
        "test-case-service:batch-test-1/asset.pdf"
    )
    assert outcome.attachments[0].get("persist_error") is None


def test_persist_runtime_documents_uploads_image_asset_from_request_messages(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    image_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDAT\x08\x99c```\x00\x00\x00\x04\x00\x01\xf6\x178U"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    image_path.write_bytes(image_bytes)

    message = build_human_message_from_paths("请分析图片附件", [image_path])
    normalized_messages = multimodal_protocol.normalize_messages([message])
    attachments = multimodal_protocol.collect_current_turn_attachment_artifacts(normalized_messages)
    assert len(attachments) == 1

    attachment = dict(attachments[0])
    attachment["status"] = "parsed"
    attachment["summary_for_model"] = "图片已解析"
    attachment["parsed_text"] = "这是图片的解析结果"

    state = {MULTIMODAL_ATTACHMENTS_KEY: [attachment]}
    runtime = SimpleNamespace(
        state=state,
        config={
            "configurable": {
                "thread_id": "thread-test-image-1",
                "batch_id": "test-case-service:batch-test-image-1",
            }
        },
        server_info=_server_info("5f419550-a3c7-49c6-9450-09154fd1bf7d"),
    )
    client = _FakeInteractionDataClient()

    outcome = persist_runtime_documents(
        runtime=runtime,
        state=state,
        service_config=ServiceConfig(),
        client=client,
        messages=normalized_messages,
    )

    assert outcome.status == "persisted"
    assert len(client.multipart_requests) == 1
    assert client.multipart_requests[0]["file_bytes"] == image_bytes
    assert client.multipart_requests[0]["file_name"] == "sample.png"
    assert client.multipart_requests[0]["content_type"] == "image/png"
    assert client.json_requests[0]["payload"]["content_type"] == "image/png"
    assert client.json_requests[0]["payload"]["storage_path"] == (
        "test-case-service/5f419550-a3c7-49c6-9450-09154fd1bf7d/"
        "test-case-service:batch-test-image-1/asset.png"
    )
    assert outcome.attachments[0]["persist_status"] == PERSIST_STATUS_PERSISTED
    assert outcome.attachments[0]["storage_path"] == (
        "test-case-service/5f419550-a3c7-49c6-9450-09154fd1bf7d/"
        "test-case-service:batch-test-image-1/asset.png"
    )


def test_persist_runtime_documents_prefers_runtime_context_project_id(tmp_path: Path) -> None:
    pdf_path = tmp_path / "context-sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    message = build_human_message_from_paths("请分析附件", [pdf_path])
    normalized_messages = multimodal_protocol.normalize_messages([message])
    attachments = multimodal_protocol.collect_current_turn_attachment_artifacts(normalized_messages)
    attachment = dict(attachments[0])
    attachment["status"] = "parsed"
    attachment["summary_for_model"] = "PDF 已解析"
    attachment["parsed_text"] = "这是 PDF 的解析结果"
    state = {MULTIMODAL_ATTACHMENTS_KEY: [attachment]}
    runtime = SimpleNamespace(
        state=state,
        config={"configurable": {"thread_id": "thread-test-2", "batch_id": "test-case-service:batch-test-2"}},
        server_info=_server_info("5f419550-a3c7-49c6-9450-09154fd1bf7d"),
    )
    client = _FakeInteractionDataClient()

    outcome = persist_runtime_documents(
        runtime=runtime,
        state=state,
        service_config=ServiceConfig(),
        client=client,
        messages=normalized_messages,
    )

    assert outcome.project_id == "5f419550-a3c7-49c6-9450-09154fd1bf7d"
    assert client.json_requests[0]["payload"]["project_id"] == "5f419550-a3c7-49c6-9450-09154fd1bf7d"


def test_persist_runtime_documents_requires_project_id(tmp_path: Path) -> None:
    pdf_path = tmp_path / "missing-project.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    message = build_human_message_from_paths("请分析附件", [pdf_path])
    normalized_messages = multimodal_protocol.normalize_messages([message])
    attachments = multimodal_protocol.collect_current_turn_attachment_artifacts(normalized_messages)
    attachment = dict(attachments[0])
    attachment["status"] = "parsed"
    attachment["summary_for_model"] = "PDF 已解析"
    attachment["parsed_text"] = "这是 PDF 的解析结果"
    state = {MULTIMODAL_ATTACHMENTS_KEY: [attachment]}
    runtime = SimpleNamespace(
        state=state,
        config={"configurable": {"thread_id": "thread-test-3", "batch_id": "test-case-service:batch-test-3"}},
        server_info=SimpleNamespace(user=None),
    )
    client = _FakeInteractionDataClient()

    try:
        persist_runtime_documents(
            runtime=runtime,
            state=state,
            service_config=ServiceConfig(),
            client=client,
            messages=normalized_messages,
        )
    except ValueError as exc:
        assert str(exc) == MISSING_PROJECT_ID_ERROR
    else:
        raise AssertionError("persist_runtime_documents should require project_id")


def test_persist_runtime_documents_rejects_configurable_project_id_as_public_contract(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "configurable-project.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    message = build_human_message_from_paths("请分析附件", [pdf_path])
    normalized_messages = multimodal_protocol.normalize_messages([message])
    attachments = multimodal_protocol.collect_current_turn_attachment_artifacts(normalized_messages)
    attachment = dict(attachments[0])
    attachment["status"] = "parsed"
    attachment["summary_for_model"] = "PDF 已解析"
    attachment["parsed_text"] = "这是 PDF 的解析结果"
    state = {MULTIMODAL_ATTACHMENTS_KEY: [attachment]}
    runtime = SimpleNamespace(
        state=state,
        config={
            "configurable": {
                "project_id": "5f419550-a3c7-49c6-9450-09154fd1bf7d",
                "thread_id": "thread-test-configurable-project",
                "batch_id": "test-case-service:batch-test-configurable-project",
            }
        },
        server_info=SimpleNamespace(user=None),
    )
    client = _FakeInteractionDataClient()

    try:
        persist_runtime_documents(
            runtime=runtime,
            state=state,
            service_config=ServiceConfig(),
            client=client,
            messages=normalized_messages,
        )
    except ValueError as exc:
        assert str(exc) == MISSING_PROJECT_ID_ERROR
    else:
        raise AssertionError(
            "persist_runtime_documents must not read project_id from configurable"
        )


def test_persist_runtime_documents_rejects_non_uuid_project_id(tmp_path: Path) -> None:
    pdf_path = tmp_path / "invalid-project.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    message = build_human_message_from_paths("请分析附件", [pdf_path])
    normalized_messages = multimodal_protocol.normalize_messages([message])
    attachments = multimodal_protocol.collect_current_turn_attachment_artifacts(normalized_messages)
    attachment = dict(attachments[0])
    attachment["status"] = "parsed"
    attachment["summary_for_model"] = "PDF 已解析"
    attachment["parsed_text"] = "这是 PDF 的解析结果"
    state = {MULTIMODAL_ATTACHMENTS_KEY: [attachment]}
    runtime = SimpleNamespace(
        state=state,
        config={
            "configurable": {
                "thread_id": "thread-test-invalid-project",
                "batch_id": "test-case-service:batch-test-invalid-project",
            }
        },
        server_info=_server_info("project-not-uuid"),
    )
    client = _FakeInteractionDataClient()

    try:
        persist_runtime_documents(
            runtime=runtime,
            state=state,
            service_config=ServiceConfig(),
            client=client,
            messages=normalized_messages,
        )
    except ValueError as exc:
        assert str(exc) == INVALID_PROJECT_ID_ERROR
    else:
        raise AssertionError("persist_runtime_documents should reject non-uuid project_id")


def test_persist_runtime_documents_does_not_allow_implicit_default_project_fallback(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "fallback-project-disabled.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    message = build_human_message_from_paths("请分析附件", [pdf_path])
    normalized_messages = multimodal_protocol.normalize_messages([message])
    attachments = multimodal_protocol.collect_current_turn_attachment_artifacts(normalized_messages)
    attachment = dict(attachments[0])
    attachment["status"] = "parsed"
    attachment["summary_for_model"] = "PDF 已解析"
    attachment["parsed_text"] = "这是 PDF 的解析结果"
    state = {MULTIMODAL_ATTACHMENTS_KEY: [attachment]}
    runtime = SimpleNamespace(
        state=state,
        config={"configurable": {"thread_id": "thread-test-4", "batch_id": "test-case-service:batch-test-4"}},
        server_info=SimpleNamespace(user=None),
    )
    client = _FakeInteractionDataClient()

    try:
        persist_runtime_documents(
            runtime=runtime,
            state=state,
            service_config=ServiceConfig(),
            client=client,
            messages=normalized_messages,
        )
    except ValueError as exc:
        assert str(exc) == MISSING_PROJECT_ID_ERROR
    else:
        raise AssertionError("default project fallback must not bypass RuntimeContext.project_id")
