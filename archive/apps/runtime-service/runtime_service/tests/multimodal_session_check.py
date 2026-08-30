from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, SystemMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.devtools.multimodal_frontend_compat import (  # noqa: E402
    build_human_message,
    file_path_to_frontend_content_block,
)
from runtime_service.middlewares.multimodal import (  # noqa: E402
    MULTIMODAL_ATTACHMENTS_KEY,
    MULTIMODAL_SUMMARY_KEY,
    MultimodalMiddleware,
)


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _resolve_default_pdfs() -> tuple[Path, Path]:
    test_data = _PROJECT_ROOT / "runtime_service" / "test_data"
    pdfs = sorted(test_data.glob("*.pdf"))
    if len(pdfs) < 2:
        raise FileNotFoundError("需要至少两个 PDF 文件用于会话累计验证。")
    return pdfs[0], pdfs[1]


def _build_request(
    *,
    text: str,
    blocks: list[dict[str, Any]],
    state: dict[str, Any] | None,
    system_prompt: str,
) -> ModelRequest:
    human = build_human_message(text, blocks=blocks)
    return ModelRequest(
        model=FakeListChatModel(responses=["ok"]),
        messages=[human],
        system_message=SystemMessage(content=system_prompt),
        state=cast(Any, state),
    )


def _run_once(
    middleware: MultimodalMiddleware, request: ModelRequest
) -> tuple[dict[str, Any], str]:
    captured: ModelRequest | None = None

    def handler(updated_request: ModelRequest) -> ModelResponse:
        nonlocal captured
        captured = updated_request
        return ModelResponse(result=[AIMessage(content="ok")])

    middleware.wrap_model_call(request, handler)
    assert captured is not None
    state = dict(captured.state or {})
    return state, captured.system_prompt or ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify multimodal session-scoped accumulation with real PDF files."
    )
    parser.add_argument("--pdf-a", help="第一个 PDF 路径。默认取 test_data 下第一个 pdf。")
    parser.add_argument("--pdf-b", help="第二个 PDF 路径。默认取 test_data 下第二个 pdf。")
    parser.add_argument(
        "--detail-mode",
        action="store_true",
        help="开启后注入解析文本片段。",
    )
    parser.add_argument(
        "--detail-text-max-chars",
        type=int,
        default=200,
        help="detail 模式下解析片段最大字符数。",
    )
    args = parser.parse_args(argv)

    if args.pdf_a and args.pdf_b:
        pdf_a = Path(args.pdf_a).expanduser().resolve()
        pdf_b = Path(args.pdf_b).expanduser().resolve()
    else:
        pdf_a, pdf_b = _resolve_default_pdfs()

    if not pdf_a.exists() or not pdf_b.exists():
        print("PDF 路径不存在。", file=sys.stderr)
        return 2

    middleware = MultimodalMiddleware(
        detail_mode=args.detail_mode,
        detail_text_max_chars=max(0, args.detail_text_max_chars),
    )
    system_prompt = "You are a helpful assistant."

    block_a = file_path_to_frontend_content_block(pdf_a)
    block_b = file_path_to_frontend_content_block(pdf_b)

    # 场景1：同一轮两个 PDF
    req_same_turn = _build_request(
        text="请分析这两个 PDF",
        blocks=[block_a, block_b],
        state={},
        system_prompt=system_prompt,
    )
    same_turn_state, same_turn_system = _run_once(middleware, req_same_turn)
    same_turn_attachments = cast(
        list[dict[str, Any]], same_turn_state.get(MULTIMODAL_ATTACHMENTS_KEY) or []
    )
    print("=== 场景1: 同一轮双PDF ===")
    print(
        _dump(
            {
                "attachments_count": len(same_turn_attachments),
                "attachment_names": [item.get("name") for item in same_turn_attachments],
                "has_multimodal_summary": MULTIMODAL_SUMMARY_KEY in same_turn_state,
                "system_contains_detail_text": "解析文本片段:" in same_turn_system,
            }
        )
    )

    # 场景2：分两轮上传，检查 session-scoped 累积
    req_turn1 = _build_request(
        text=f"先分析 {pdf_a.name}",
        blocks=[block_a],
        state={},
        system_prompt=system_prompt,
    )
    turn1_state, _ = _run_once(middleware, req_turn1)

    req_turn2 = _build_request(
        text=f"再分析 {pdf_b.name}",
        blocks=[block_b],
        state=turn1_state,
        system_prompt=system_prompt,
    )
    turn2_state, turn2_system = _run_once(middleware, req_turn2)
    turn2_attachments = cast(
        list[dict[str, Any]], turn2_state.get(MULTIMODAL_ATTACHMENTS_KEY) or []
    )
    print("=== 场景2: 分两轮累计 ===")
    print(
        _dump(
            {
                "attachments_count": len(turn2_attachments),
                "attachment_names": [item.get("name") for item in turn2_attachments],
                "has_multimodal_summary": MULTIMODAL_SUMMARY_KEY in turn2_state,
                "system_contains_detail_text": "解析文本片段:" in turn2_system,
            }
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
