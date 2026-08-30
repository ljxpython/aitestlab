from __future__ import annotations

# pyright: reportMissingImports=false

import asyncio
import base64
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from deepagents.middleware.skills import append_to_system_message
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.middlewares.multimodal import (  # noqa: E402
    MULTIMODAL_ATTACHMENTS_KEY,
    MULTIMODAL_SUMMARY_KEY,
    AttachmentArtifact,
    MultimodalMiddleware,
    _extract_openai_response_text,
    _extract_pdf_text,
    _parse_model_response,
    _resolve_parser_transport,
    build_attachment_artifact,
    build_multimodal_system_message,
    normalize_messages,
)

from runtime_service.devtools.multimodal_frontend_compat import (  # noqa: E402
    build_human_message,
    decode_block_bytes,
    file_path_to_frontend_content_block,
)


def _fake_success_parser(
    artifact: AttachmentArtifact, block: Mapping[str, Any]
) -> AttachmentArtifact:
    del block
    next_artifact = dict(artifact)
    next_artifact["status"] = "parsed"
    next_artifact["summary_for_model"] = f"{artifact['kind']} 已解析：{artifact['name']}"
    next_artifact["parsed_text"] = "测试解析文本"
    next_artifact["structured_data"] = {"key_points": ["测试解析"]}
    return cast(AttachmentArtifact, next_artifact)


def test_parser_model_override_uses_platform_runtime_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "runtime_service.middlewares.multimodal.middleware.get_config",
        lambda: {
            "configurable": {
                "platform_runtime": {
                    "multimodal_parser_model_id": "runtime-parser-model",
                }
            }
        },
    )
    middleware = MultimodalMiddleware(parser_model_id="default-parser-model")

    assert middleware._resolve_parser_model_id() == "runtime-parser-model"


def test_build_attachment_artifact_for_frontend_image_block() -> None:
    artifact = build_attachment_artifact(
        {
            "type": "image",
            "mimeType": "image/png",
            "data": "abc123",
            "metadata": {"name": "screen.png"},
        },
        1,
    )
    assert artifact is not None
    assert artifact["kind"] == "image"
    assert artifact["mime_type"] == "image/png"
    assert artifact["status"] == "unprocessed"
    assert artifact["name"] == "screen.png"


def test_build_attachment_artifact_for_docx_block() -> None:
    artifact = build_attachment_artifact(
        {
            "type": "file",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "data": "abc123",
            "metadata": {"filename": "report.docx"},
        },
        2,
    )
    assert artifact is not None
    assert artifact["kind"] == "docx"
    assert artifact["status"] == "unprocessed"


def test_normalize_messages_converts_frontend_blocks_to_langchain_shape() -> None:
    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "请看附件"},
                {
                    "type": "image",
                    "mimeType": "image/png",
                    "data": "abc123",
                    "metadata": {"name": "screen.png"},
                },
                {
                    "type": "file",
                    "mimeType": "application/pdf",
                    "data": "pdfbase64",
                    "metadata": {"filename": "report.pdf"},
                },
            ]
        )
    ]

    normalized = normalize_messages(messages)
    content = cast(list[dict[str, Any]], normalized[0].content)
    assert isinstance(content, list)
    assert content[1]["base64"] == "abc123"
    assert content[1]["mime_type"] == "image/png"
    assert content[2]["base64"] == "pdfbase64"
    assert content[2]["mime_type"] == "application/pdf"


def test_multimodal_middleware_wrap_model_call_augments_request() -> None:
    def fake_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        next_artifact["summary_for_model"] = "PDF 已解析：这是测试摘要。"
        next_artifact["parsed_text"] = "测试 PDF 文本"
        next_artifact["structured_data"] = {"key_points": ["测试摘要"]}
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(parser=fake_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "帮我看下这个 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdfbase64",
                        "metadata": {"filename": "report.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        system_prompt = updated_request.system_prompt or ""
        assert "Base prompt" in system_prompt
        assert "## Multimodal Attachments" in system_prompt
        state = cast(dict[str, Any], updated_request.state)
        assert MULTIMODAL_ATTACHMENTS_KEY in state
        assert MULTIMODAL_SUMMARY_KEY in state
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["status"] == "parsed"
        assert "PDF 已解析" in state[MULTIMODAL_SUMMARY_KEY]
        assert "关键要点" in state[MULTIMODAL_SUMMARY_KEY]
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert isinstance(content, list)
        assert content[1]["type"] == "text"
        assert "PDF 已解析" in content[1]["text"]
        assert "关键要点" in content[1]["text"]
        assert "测试 PDF 文本" not in content[1]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_before_model_records_state() -> None:
    middleware = MultimodalMiddleware()
    state = {
        "messages": [
            HumanMessage(
                content=[
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "abc",
                        "metadata": {"name": "screen.png"},
                    },
                ]
            )
        ]
    }
    updates = middleware.before_model(cast(Any, state), runtime=None)
    assert updates is not None
    assert MULTIMODAL_ATTACHMENTS_KEY in updates
    assert updates[MULTIMODAL_ATTACHMENTS_KEY][0]["kind"] == "image"
    assert MULTIMODAL_SUMMARY_KEY in updates


def test_multimodal_middleware_rewrites_current_turn_file_after_before_model() -> None:
    def fake_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        next_artifact["summary_for_model"] = f"PDF 已解析：{artifact['name']}"
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(parser=fake_parser)
    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "请分析这个 PDF"},
                {
                    "type": "file",
                    "mimeType": "application/pdf",
                    "data": "pdfbase64",
                    "metadata": {"filename": "report.pdf"},
                },
            ]
        )
    ]
    state = {"messages": messages}
    updates = middleware.before_model(cast(Any, state), runtime=None)
    assert updates is not None

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=messages,
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, updates),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        attachments = cast(
            list[dict[str, Any]], updated_request.state[MULTIMODAL_ATTACHMENTS_KEY]
        )
        assert attachments[0]["status"] == "parsed"
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "text"
        assert "PDF 已解析：report.pdf" in content[1]["text"]
        assert "file" not in {item.get("type") for item in content if isinstance(item, dict)}
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_awrap_model_call_augments_request() -> None:
    async def fake_async_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        next_artifact["summary_for_model"] = "DOC 已解析：这是测试摘要。"
        next_artifact["parsed_text"] = "测试 DOC 文本"
        next_artifact["structured_data"] = {"key_points": ["测试 DOC"]}
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(async_parser=fake_async_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {
                        "type": "file",
                        "mimeType": "application/msword",
                        "data": "docbase64",
                        "metadata": {"filename": "brief.doc"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    async def handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["kind"] == "doc"
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["status"] == "unprocessed"
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[0]["type"] == "text"
        assert "kind=doc" in content[0]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = asyncio.run(middleware.awrap_model_call(request, handler))
    assert response.result[0].text == "ok"


def test_multimodal_middleware_preserves_model_with_attachments() -> None:
    class DummyModel:
        def __init__(self) -> None:
            self.bound_kwargs: dict[str, Any] | None = None

        def bind(self, **kwargs: Any) -> "DummyModel":
            bound = DummyModel()
            bound.bound_kwargs = kwargs
            return bound

    base_model = DummyModel()
    middleware = MultimodalMiddleware(parser=_fake_success_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, base_model),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请分析这个 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdfbase64",
                        "metadata": {"filename": "report.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.model is base_model
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "text"
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_preserves_model_without_attachments() -> None:
    class DummyModel:
        def __init__(self) -> None:
            self.bound_kwargs: dict[str, Any] | None = None

        def bind(self, **kwargs: Any) -> "DummyModel":
            bound = DummyModel()
            bound.bound_kwargs = kwargs
            return bound

    base_model = DummyModel()
    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, base_model),
        messages=[HumanMessage(content="纯文本请求")],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.model is base_model
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_parser_failure_is_fail_soft() -> None:
    def failing_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "failed"
        next_artifact["summary_for_model"] = "附件解析失败：测试失败"
        next_artifact["error"] = {"message": "测试失败"}
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(parser=failing_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "imgbase64",
                        "metadata": {"name": "screen.png"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["status"] == "failed"
        assert "附件解析失败" in state[MULTIMODAL_SUMMARY_KEY]
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[0]["type"] == "text"
        assert "kind=image" in content[0]["text"]
        assert "附件解析失败：测试失败" in content[0]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_rewrites_image_blocks_for_model() -> None:
    def fake_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        next_artifact["summary_for_model"] = "图片已解析：界面包含登录入口与错误提示。"
        next_artifact["parsed_text"] = "详细 OCR 文本，不应直接注入主模型。"
        next_artifact["structured_data"] = {"key_points": ["登录入口", "错误提示"]}
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(parser=fake_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请看图片"},
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "imgbase64",
                        "metadata": {"name": "screen.png"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["kind"] == "image"
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["status"] == "parsed"
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "text"
        assert "kind=image" in content[1]["text"]
        assert "图片已解析：界面包含登录入口与错误提示。" in content[1]["text"]
        assert "关键要点" in content[1]["text"]
        assert "详细 OCR 文本" not in content[1]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_rewrites_mixed_image_and_pdf_blocks_in_order() -> None:
    def fake_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        if artifact["kind"] == "image":
            next_artifact["summary_for_model"] = "图片已解析：订单列表截图。"
            next_artifact["structured_data"] = {"key_points": ["订单编号", "金额"]}
            next_artifact["parsed_text"] = "图片 OCR 原文"
        else:
            next_artifact["summary_for_model"] = "PDF 已解析：结算规则说明。"
            next_artifact["structured_data"] = {"key_points": ["结算周期", "退款规则"]}
            next_artifact["parsed_text"] = "PDF 原文"
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(parser=fake_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请综合分析这两个附件"},
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "imgbase64",
                        "metadata": {"name": "screen.png"},
                    },
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdfbase64",
                        "metadata": {"filename": "report.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert [item["type"] for item in content] == ["text", "text", "text"]
        assert "图片已解析：订单列表截图。" in content[1]["text"]
        assert "订单编号" in content[1]["text"]
        assert "PDF 已解析：结算规则说明。" in content[2]["text"]
        assert "结算周期" in content[2]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_detail_mode_includes_parsed_text_preview() -> None:
    def fake_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        next_artifact["summary_for_model"] = "PDF 已解析：这是测试摘要。"
        next_artifact["parsed_text"] = "ABCDEFGHIJKL"
        next_artifact["structured_data"] = {"key_points": ["测试点"]}
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(
        parser=fake_parser,
        detail_mode=True,
        detail_text_max_chars=5,
    )
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请看这个 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdfbase64",
                        "metadata": {"filename": "report.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "text"
        assert "解析文本片段:" in content[1]["text"]
        assert "ABCDE ...[已截断]" in content[1]["text"]
        system_prompt = updated_request.system_prompt or ""
        assert "解析文本片段:" in system_prompt
        assert "ABCDE ...[已截断]" in system_prompt
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_extract_pdf_text_from_base64_payload() -> None:
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 72 100 Td (Hello PDF) Tj ET\nendstream endobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000113 00000 n \n0000000240 00000 n \n0000000334 00000 n \n"
        b"trailer<</Root 1 0 R/Size 6>>\nstartxref\n404\n%%EOF"
    )
    block = {
        "type": "file",
        "mimeType": "application/pdf",
        "data": base64.b64encode(pdf_bytes).decode("utf-8"),
        "metadata": {"filename": "hello.pdf"},
    }

    text, metadata = _extract_pdf_text(block)
    assert text is not None
    assert "Hello PDF" in text
    assert metadata is not None
    assert metadata["page_count"] == 1
    assert metadata["extraction"] == "pymupdf4llm_markdown"


def test_multimodal_summary_not_reinjected_on_follow_up_text_turn() -> None:
    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="这是一条纯文本追问")],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(
            Any,
            {
                MULTIMODAL_ATTACHMENTS_KEY: [{"attachment_id": "att_1"}],
                MULTIMODAL_SUMMARY_KEY: "旧摘要",
            },
        ),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        system_prompt = updated_request.system_prompt or ""
        state = cast(dict[str, Any], updated_request.state)
        assert "## Multimodal Attachments" not in system_prompt
        assert MULTIMODAL_ATTACHMENTS_KEY not in state
        assert MULTIMODAL_SUMMARY_KEY not in state
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_accumulates_pdf_artifacts_across_turns() -> None:
    middleware = MultimodalMiddleware(parser=_fake_success_parser)
    first_state: dict[str, Any] = {}

    first_request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "第一份 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdf_base64_a",
                        "metadata": {"filename": "a.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, first_state),
    )

    def first_handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        first_state.update(state)
        assert len(state[MULTIMODAL_ATTACHMENTS_KEY]) == 1
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(first_request, first_handler)

    second_request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "第二份 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdf_base64_b",
                        "metadata": {"filename": "b.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, first_state),
    )

    def second_handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        attachments = state[MULTIMODAL_ATTACHMENTS_KEY]
        assert len(attachments) == 2
        names = [item.get("name") for item in attachments]
        assert "a.pdf" in names
        assert "b.pdf" in names
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(second_request, second_handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_rewrites_only_current_turn_attachment_in_session() -> None:
    def fake_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        next_artifact["summary_for_model"] = f"PDF 已解析：{artifact['name']}"
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(parser=fake_parser)

    first_request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "第一份 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdf_base64_a",
                        "metadata": {"filename": "a.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )
    session_state: dict[str, Any] = {}

    def first_handler(updated_request: ModelRequest) -> ModelResponse:
        session_state.update(cast(dict[str, Any], updated_request.state))
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(first_request, first_handler)

    second_messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "第二份 PDF"},
                {
                    "type": "file",
                    "mimeType": "application/pdf",
                    "data": "pdf_base64_b",
                    "metadata": {"filename": "b.pdf"},
                },
            ]
        )
    ]
    before_model_state = dict(session_state)
    before_model_state["messages"] = second_messages
    second_updates = middleware.before_model(cast(Any, before_model_state), runtime=None)
    assert second_updates is not None

    second_request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=second_messages,
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {**session_state, **second_updates}),
    )

    def second_handler(updated_request: ModelRequest) -> ModelResponse:
        attachments = cast(
            list[dict[str, Any]], updated_request.state[MULTIMODAL_ATTACHMENTS_KEY]
        )
        assert [item["name"] for item in attachments] == ["a.pdf", "b.pdf"]
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "text"
        assert "PDF 已解析：b.pdf" in content[1]["text"]
        assert "PDF 已解析：a.pdf" not in content[1]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(second_request, second_handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_accumulates_image_and_pdf_across_turns() -> None:
    middleware = MultimodalMiddleware(parser=_fake_success_parser)
    session_state: dict[str, Any] = {}

    image_request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "先看图片"},
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "img_base64_a",
                        "metadata": {"name": "image-a.png"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, session_state),
    )

    def image_handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        session_state.update(state)
        assert len(state[MULTIMODAL_ATTACHMENTS_KEY]) == 1
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["kind"] == "image"
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(image_request, image_handler)

    pdf_request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "再看 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdf_base64_c",
                        "metadata": {"filename": "c.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, session_state),
    )

    def pdf_handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        attachments = state[MULTIMODAL_ATTACHMENTS_KEY]
        kinds = [item["kind"] for item in attachments]
        assert "image" in kinds
        assert "pdf" in kinds
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(pdf_request, pdf_handler)
    assert response.result[0].text == "ok"


def test_build_multimodal_system_message_removes_stale_section() -> None:
    existing = SystemMessage(
        content=(
            "BASE_PROMPT\n\n## Multimodal Attachments\n"
            "检测到以下多模态附件：\n- 旧摘要"
        )
    )
    next_message = build_multimodal_system_message(existing, None)
    assert next_message is not None
    assert next_message.content == "BASE_PROMPT"


def test_build_multimodal_system_message_preserves_content_blocks_text() -> None:
    existing = append_to_system_message(SystemMessage(content="BASE_PROMPT"), "SKILLS")

    next_message = build_multimodal_system_message(existing, None)

    assert next_message is not None
    assert next_message.content == "BASE_PROMPT\n\nSKILLS"


def test_multimodal_middleware_preserves_skills_system_prompt_without_attachments() -> None:
    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="请分析登录功能")],
        system_message=append_to_system_message(
            SystemMessage(content="BASE_PROMPT"),
            "## Skills System\n- requirement-analysis",
        ),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        system_message = updated_request.system_message
        assert system_message is not None
        assert "BASE_PROMPT" in cast(str, system_message.content)
        assert "## Skills System" in cast(str, system_message.content)
        assert "requirement-analysis" in cast(str, system_message.content)
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_parse_model_response_never_uses_raw_json_as_summary() -> None:
    raw = 'Here is the result: {"summary_for_model":"一张动漫头像","parsed_text":null,"structured_data":{"key_points":["头像"]},"confidence":0.98}'
    parsed = _parse_model_response(raw)
    assert parsed["summary_for_model"] == "一张动漫头像"
    assert parsed["structured_data"] == {"key_points": ["头像"]}


def test_extract_openai_response_text_rejects_null_choices() -> None:
    class FakeResponse:
        choices = None
        status = 400
        msg = "upstream gateway error"
        body = {"detail": "choices missing"}

    with pytest.raises(ValueError, match="Malformed OpenAI-compatible response"):
        _extract_openai_response_text(FakeResponse())


def test_multimodal_middleware_marks_malformed_openai_response_as_failed() -> None:
    class FakeCompletions:
        @staticmethod
        def create(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs

            class FakeResponse:
                choices = None
                status = 502
                msg = "bad gateway"
                body = {"detail": "choices missing"}

            return FakeResponse()

    class FakeClient:
        chat = type("FakeChat", (), {"completions": FakeCompletions()})()

    class FakeModel:
        model_name = "fake-openai-compatible"
        root_client = FakeClient()
        root_async_client = object()

    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请分析这张图片"},
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "imgbase64",
                        "metadata": {"name": "screen.png"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        attachment = state[MULTIMODAL_ATTACHMENTS_KEY][0]
        assert attachment["status"] == "failed"
        assert "Malformed OpenAI-compatible response" in attachment["summary_for_model"]
        assert "bad gateway" in attachment["summary_for_model"]
        return ModelResponse(result=[AIMessage(content="ok")])

    with patch(
        "runtime_service.middlewares.multimodal.resolve_model_by_id",
        return_value=FakeModel(),
    ):
        response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_multimodal_middleware_pdf_falls_back_to_extracted_text_on_malformed_summary_response() -> None:
    class FakeCompletions:
        @staticmethod
        def create(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs

            class FakeResponse:
                choices = None
                status = 434
                msg = "Invalid apiKey"
                body = {"detail": "choices missing"}

            return FakeResponse()

    class FakeClient:
        chat = type("FakeChat", (), {"completions": FakeCompletions()})()

    class FakeModel:
        model_name = "fake-openai-compatible"
        root_client = FakeClient()
        root_async_client = object()

    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请分析这个 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdfbase64",
                        "metadata": {"filename": "report.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        attachment = state[MULTIMODAL_ATTACHMENTS_KEY][0]
        assert attachment["status"] == "parsed"
        assert "PDF 已完成文本抽取" in attachment["summary_for_model"]
        assert "Alpha Beta Gamma" in attachment["parsed_text"]
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "text"
        assert "PDF 已完成文本抽取" in content[1]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    with (
        patch(
            "runtime_service.middlewares.multimodal.resolve_model_by_id",
            return_value=FakeModel(),
        ),
        patch(
            "runtime_service.middlewares.multimodal.parsing._prepare_pdf_artifact_for_parsing",
            return_value=(
                "Alpha Beta Gamma",
                {"page_count": 1, "extraction": "unit-test"},
                [{"page": 1, "text": "Alpha Beta Gamma"}],
                None,
            ),
        ),
    ):
        response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_multimodal_middleware_pdf_fallback_mentions_rate_limit_clearly() -> None:
    class FakeCompletions:
        @staticmethod
        def create(*args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            raise RuntimeError(
                "Error code: 429 - {'error': {'code': 'SetLimitExceeded', 'type': 'TooManyRequests'}}"
            )

    class FakeClient:
        chat = type("FakeChat", (), {"completions": FakeCompletions()})()

    class FakeModel:
        model_name = "fake-openai-compatible"
        root_client = FakeClient()
        root_async_client = object()

    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请分析这个 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdfbase64",
                        "metadata": {"filename": "report.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        attachment = state[MULTIMODAL_ATTACHMENTS_KEY][0]
        assert attachment["status"] == "parsed"
        assert "多模态摘要模型当前被限流或额度受限" in attachment["summary_for_model"]
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "text"
        assert "多模态摘要模型当前被限流或额度受限" in content[1]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    with (
        patch(
            "runtime_service.middlewares.multimodal.resolve_model_by_id",
            return_value=FakeModel(),
        ),
        patch(
            "runtime_service.middlewares.multimodal.parsing._prepare_pdf_artifact_for_parsing",
            return_value=(
                "Alpha Beta Gamma",
                {"page_count": 1, "extraction": "unit-test"},
                [{"page": 1, "text": "Alpha Beta Gamma"}],
                None,
            ),
        ),
    ):
        response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_resolve_parser_transport_uses_openai_clients() -> None:

    class FakeModel:
        model_name = "qwen3-vl-plus"
        root_client = object()
        root_async_client = object()

    with patch(
        "runtime_service.middlewares.multimodal.resolve_model_by_id",
        return_value=FakeModel(),
    ):
        model_name, root_client, root_async_client = _resolve_parser_transport(
            "iflow_qwen3-vl-plus"
        )
    assert model_name == "qwen3-vl-plus"
    assert root_client is FakeModel.root_client
    assert root_async_client is FakeModel.root_async_client


def test_frontend_compat_pdf_fixture_roundtrips_and_extracts_text() -> None:
    test_data_dir = Path(__file__).resolve().parents[1] / "test_data"
    pdf_path = next(test_data_dir.glob("*.pdf"), None)
    assert pdf_path is not None

    pdf_block = file_path_to_frontend_content_block(pdf_path)
    message = build_human_message("请解析这个 PDF", blocks=[pdf_block])
    normalized = normalize_messages([message])
    content = cast(list[dict[str, Any]], normalized[0].content)

    normalized_pdf_block = content[1]
    assert decode_block_bytes(normalized_pdf_block) == pdf_path.read_bytes()

    parsed_text, metadata = _extract_pdf_text(normalized_pdf_block)
    assert parsed_text is not None
    assert parsed_text.strip()
    assert metadata is not None
    assert metadata.get("page_count", 0) > 0


def test_frontend_compat_image_fixture_roundtrips_bytes() -> None:
    test_data_dir = Path(__file__).resolve().parents[1] / "test_data"
    image_path = next(test_data_dir.glob("*.jpeg"), None)
    assert image_path is not None

    image_block = file_path_to_frontend_content_block(image_path)
    assert decode_block_bytes(image_block) == image_path.read_bytes()
