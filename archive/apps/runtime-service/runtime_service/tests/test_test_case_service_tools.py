from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.services.test_case_service.document_persistence import (
    DocumentPersistenceOutcome,
)
from runtime_service.services.test_case_service.schemas import (
    PersistTestCaseItem,
    TestCaseServiceConfig as ServiceConfig,
)
from runtime_service.services.test_case_service import tools as test_case_tools
from runtime_service.services.test_case_service.tools import (
    _build_test_case_idempotency_keys,
    build_test_case_service_tools,
)

VALID_PROJECT_ID = "5f419550-a3c7-49c6-9450-09154fd1bf7d"


def test_build_test_case_idempotency_keys_prefers_case_id() -> None:
    first = PersistTestCaseItem(
        case_id="TC-LOGIN-001",
        title="登录成功",
        module_name="认证中心",
        test_type="functional",
        steps=["输入正确账号密码"],
        expected_results=["登录成功"],
    )
    second = PersistTestCaseItem(
        case_id=" tc-login-001 ",
        title="登录成功-文案调整",
        module_name="账号服务",
        test_type="regression",
        steps=["输入正确账号密码并点击登录"],
        expected_results=["进入首页"],
    )

    first_run_keys = _build_test_case_idempotency_keys([first])
    second_run_keys = _build_test_case_idempotency_keys([second])

    assert len(first_run_keys) == 1
    assert len(second_run_keys) == 1
    assert first_run_keys[0] == second_run_keys[0]


def test_build_test_case_idempotency_keys_falls_back_to_semantic_identity() -> None:
    first = PersistTestCaseItem(
        title="登录失败",
        module_name="认证中心",
        test_type="functional",
        steps=["输入错误密码"],
        expected_results=["提示密码错误"],
    )
    second = PersistTestCaseItem(
        title="  登录失败  ",
        module_name="认证中心",
        test_type="functional",
        steps=["输入错误密码并点击登录"],
        expected_results=["展示失败提示"],
    )

    keys = _build_test_case_idempotency_keys([first, second])

    assert len(keys) == 2
    assert keys[0] != keys[1]

    rerun_keys = _build_test_case_idempotency_keys([first, second])
    assert rerun_keys == keys


def _build_runtime(
    *,
    project_id: str | None = None,
    thread_id: str = "thread-1",
    state: dict[str, Any] | None = None,
) -> Any:
    user = None
    if project_id is not None:
        user = {
            "identity": "user-1",
            "tenant_id": "tenant-1",
            "role": "project_editor",
            "permissions": ["runtime:write"],
            "project_id": project_id,
        }
    return SimpleNamespace(
        config={"configurable": {"thread_id": thread_id}},
        state=state or {},
        server_info=SimpleNamespace(user=user),
    )


def _build_test_case_item() -> PersistTestCaseItem:
    return PersistTestCaseItem(
        case_id="TC-LOGIN-001",
        title="登录成功",
        description="验证合法账号密码可登录",
        module_name="认证中心",
        test_type="functional",
        steps=["输入正确账号密码并点击登录"],
        expected_results=["登录成功并进入首页"],
    )


def test_persist_test_case_results_fails_when_project_id_missing() -> None:
    tool = build_test_case_service_tools(ServiceConfig())[0]

    result = json.loads(
        tool.func(
            bundle_title="登录测试",
            bundle_summary="",
            test_cases=[_build_test_case_item()],
            quality_review={},
            export_format=None,
            runtime=_build_runtime(project_id=None),
        )
    )

    assert result["status"] == "failed_missing_project_id"
    assert result["reason"] == "test_case_project_id_required"
    assert result["test_case_count"] == 1


def test_persist_test_case_results_skips_when_remote_not_configured(monkeypatch) -> None:
    class DummyClient:
        def __init__(self, _config: Any) -> None:
            self.is_configured = False

    monkeypatch.setattr(test_case_tools, "InteractionDataServiceClient", DummyClient)
    monkeypatch.setattr(
        test_case_tools,
        "build_interaction_data_service_config",
        lambda config: object(),
    )

    tool = build_test_case_service_tools(ServiceConfig())[0]
    result = json.loads(
        tool.func(
            bundle_title="登录测试",
            bundle_summary="",
            test_cases=[_build_test_case_item()],
            quality_review={},
            export_format=None,
            runtime=_build_runtime(project_id=VALID_PROJECT_ID),
        )
    )

    assert result["status"] == "skipped_remote_not_configured"
    assert result["project_id"] == VALID_PROJECT_ID
    assert result["test_case_count"] == 1


def test_persist_test_case_results_fails_when_project_id_is_not_uuid() -> None:
    tool = build_test_case_service_tools(ServiceConfig())[0]

    result = json.loads(
        tool.func(
            bundle_title="登录测试",
            bundle_summary="",
            test_cases=[_build_test_case_item()],
            quality_review={},
            export_format=None,
            runtime=_build_runtime(project_id="project-not-uuid"),
        )
    )

    assert result["status"] == "failed_invalid_project_id"
    assert result["reason"] == "test_case_project_id_must_be_uuid"
    assert result["test_case_count"] == 1


def test_persist_test_case_results_returns_structured_failure_when_remote_request_fails(
    monkeypatch,
) -> None:
    class DummyClient:
        def __init__(self, _config: Any) -> None:
            self.is_configured = True

        def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
            raise ConnectionError("connection refused")

    monkeypatch.setattr(test_case_tools, "InteractionDataServiceClient", DummyClient)
    monkeypatch.setattr(
        test_case_tools,
        "build_interaction_data_service_config",
        lambda config: object(),
    )
    monkeypatch.setattr(
        test_case_tools,
        "persist_runtime_documents",
        lambda **_: DocumentPersistenceOutcome(
            status="failed",
            project_id=VALID_PROJECT_ID,
            batch_id="batch-fixed",
            attachments=[],
            persisted_documents=[],
            persisted_document_ids=[],
        ),
    )
    monkeypatch.setattr(test_case_tools, "_resolve_batch_id", lambda runtime: "batch-fixed")
    monkeypatch.setattr(
        test_case_tools,
        "_resolve_runtime_meta",
        lambda runtime: {
            "thread_id": "thread-fixed",
            "run_id": "run-fixed",
            "agent_key": "test_case_service",
        },
    )

    tool = build_test_case_service_tools(ServiceConfig())[0]
    result = json.loads(
        tool.func(
            bundle_title="登录测试",
            bundle_summary="",
            test_cases=[_build_test_case_item()],
            quality_review={},
            export_format=None,
            runtime=_build_runtime(project_id=VALID_PROJECT_ID, state={"messages": []}),
        )
    )

    assert result["status"] == "failed_remote_request"
    assert result["project_id"] == VALID_PROJECT_ID
    assert result["batch_id"] == "batch-fixed"
    assert result["persisted_test_case_count"] == 0
    assert result["failed_test_case_count"] == 1
    assert result["failed_test_cases"][0]["title"] == "登录成功"
    assert "connection refused" in result["failed_test_cases"][0]["error"]


def test_persist_test_case_results_persists_cases_and_document_links(monkeypatch) -> None:
    posted_payloads: list[dict[str, Any]] = []

    class DummyClient:
        def __init__(self, _config: Any) -> None:
            self.is_configured = True

        def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
            posted_payloads.append({"path": path, "payload": payload})
            return {"id": f"remote-{len(posted_payloads)}"}

    monkeypatch.setattr(test_case_tools, "InteractionDataServiceClient", DummyClient)
    monkeypatch.setattr(
        test_case_tools,
        "build_interaction_data_service_config",
        lambda config: object(),
    )
    monkeypatch.setattr(
        test_case_tools,
        "persist_runtime_documents",
        lambda **_: DocumentPersistenceOutcome(
            status="persisted",
            project_id=VALID_PROJECT_ID,
            batch_id="batch-fixed",
            attachments=[
                {
                    "persist_status": "persisted",
                    "persisted_document_id": "doc-1",
                }
            ],
            persisted_documents=[{"id": "doc-1"}],
            persisted_document_ids=["doc-1"],
        ),
    )
    monkeypatch.setattr(test_case_tools, "_resolve_batch_id", lambda runtime: "batch-fixed")
    monkeypatch.setattr(
        test_case_tools,
        "_resolve_runtime_meta",
        lambda runtime: {
            "thread_id": "thread-fixed",
            "run_id": "run-fixed",
            "agent_key": "test_case_service",
        },
    )

    runtime = _build_runtime(project_id=VALID_PROJECT_ID, state={"messages": []})
    tool = build_test_case_service_tools(ServiceConfig())[0]
    result = json.loads(
        tool.func(
            bundle_title="登录测试",
            bundle_summary="最小交付",
            test_cases=[_build_test_case_item()],
            quality_review={"summary": "ok"},
            export_format="json",
            runtime=runtime,
        )
    )

    assert result["status"] == "persisted"
    assert result["project_id"] == VALID_PROJECT_ID
    assert result["batch_id"] == "batch-fixed"
    assert result["persisted_document_ids"] == ["doc-1"]
    assert result["persisted_test_case_count"] == 1
    assert result["persisted_test_case_ids"] == ["remote-1"]
    assert runtime.state["multimodal_attachments"] == [
        {
            "persist_status": "persisted",
            "persisted_document_id": "doc-1",
        }
    ]

    assert len(posted_payloads) == 1
    posted = posted_payloads[0]
    assert posted["path"] == test_case_tools.TEST_CASES_PATH
    payload = posted["payload"]
    assert payload["project_id"] == VALID_PROJECT_ID
    assert payload["batch_id"] == "batch-fixed"
    assert payload["source_document_ids"] == ["doc-1"]
    assert payload["content_json"]["meta"]["source_document_ids"] == ["doc-1"]
    assert payload["content_json"]["meta"]["bundle_title"] == "登录测试"


def test_build_test_case_service_tools_exposes_multimodal_reader() -> None:
    tools = build_test_case_service_tools(ServiceConfig())
    tool_names = [tool.name for tool in tools]

    assert tool_names == ["persist_test_case_results", "read_multimodal_attachments"]
