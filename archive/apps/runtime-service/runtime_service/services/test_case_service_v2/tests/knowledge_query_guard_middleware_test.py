from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from langchain.agents.middleware import ModelRequest
from langchain.messages import HumanMessage

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.services.test_case_service_v2.knowledge_query_guard_middleware import (  # noqa: E402
    TestCaseKnowledgeQueryGuardMiddleware,
    _resolve_project_id,
)


def _runtime(project_id: str | None) -> SimpleNamespace:
    user = None
    if project_id is not None:
        user = {
            "identity": "user-1",
            "tenant_id": "tenant-1",
            "role": "project_editor",
            "permissions": ["runtime:write"],
            "project_id": project_id,
        }
    return SimpleNamespace(server_info=SimpleNamespace(user=user))


def test_requires_guard_for_plain_business_generation_without_attachments() -> None:
    middleware = TestCaseKnowledgeQueryGuardMiddleware()
    request = SimpleNamespace(
        messages=[HumanMessage(content="请生成支付模块测试用例")],
        state={},
    )

    guarded, latest_user_text = middleware._requires_guard(request)

    assert guarded is True
    assert latest_user_text == "请生成支付模块测试用例"


def test_requires_guard_skips_when_multimodal_state_already_has_attachments() -> None:
    middleware = TestCaseKnowledgeQueryGuardMiddleware()
    request = SimpleNamespace(
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请基于这个PDF生成测试用例"},
                    {
                        "type": "text",
                        "text": "[附件: 接口文档.pdf; kind=pdf; status=parsed] 摘要: PDF 已完成文本抽取",
                    },
                ]
            )
        ],
        state={
            "multimodal_attachments": [
                {
                    "attachment_id": "att_1",
                    "kind": "pdf",
                    "status": "parsed",
                    "summary_for_model": "PDF 已完成文本抽取",
                }
            ]
        },
    )

    guarded, latest_user_text = middleware._requires_guard(request)

    assert guarded is False
    assert latest_user_text == ""


def test_resolve_project_id_only_reads_authenticated_runtime_user() -> None:
    request = ModelRequest(
        model=None,
        system_prompt="你正在处理项目：`state-project`",
        messages=[HumanMessage(content="请生成支付模块测试用例")],
        tools=[],
        state={"project_id": "state-project"},
        runtime=_runtime("context-project"),
    )

    assert _resolve_project_id(request) == "context-project"


def test_resolve_project_id_does_not_fallback_to_state_or_system_prompt() -> None:
    request = ModelRequest(
        model=None,
        system_prompt="当前项目 ID：`prompt-project`",
        messages=[HumanMessage(content="请生成支付模块测试用例")],
        tools=[],
        state={"project_id": "state-project"},
        runtime=_runtime(None),
    )

    assert _resolve_project_id(request) is None
