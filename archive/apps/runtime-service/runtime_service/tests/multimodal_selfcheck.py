from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
    AttachmentArtifact,
    MultimodalMiddleware,
    MultimodalAgentState,
    get_default_multimodal_model_id,
    normalize_messages,
)

_DEFAULT_FIXTURE_SUFFIXES = (".pdf", ".jpeg", ".jpg", ".png", ".webp", ".gif")


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _print_section(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, str):
        print(payload)
        return
    print(_json_dump(payload))


def _default_fixture_paths() -> list[Path]:
    test_data_dir = _PROJECT_ROOT / "runtime_service" / "test_data"
    paths: list[Path] = []
    for suffix in _DEFAULT_FIXTURE_SUFFIXES:
        paths.extend(sorted(test_data_dir.glob(f"*{suffix}")))
    return sorted({path.resolve() for path in paths}, key=lambda item: item.name)


def _resolve_input_paths(positional: list[str], explicit_files: list[str]) -> list[Path]:
    raw_values = [*positional, *explicit_files]
    if not raw_values:
        return _default_fixture_paths()

    paths: list[Path] = []
    for raw in raw_values:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise FileNotFoundError(f"Missing input file: {path}")
        if path.is_dir():
            for suffix in _DEFAULT_FIXTURE_SUFFIXES:
                paths.extend(sorted(path.glob(f"*{suffix}")))
            continue
        paths.append(path)
    return sorted({path.resolve() for path in paths}, key=lambda item: item.name)


def _detect_mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed:
        return guessed
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    return ""


def _block_snapshot(block: dict[str, Any]) -> dict[str, Any]:
    payload = block.get("data") or block.get("base64")
    return {
        "type": block.get("type"),
        "mimeType": block.get("mimeType") or block.get("mime_type"),
        "payload_length": len(payload) if isinstance(payload, str) else 0,
        "metadata": block.get("metadata"),
    }


def _artifact_snapshot(
    artifact: Mapping[str, Any], *, preview_chars: int
) -> dict[str, Any]:
    parsed_text = artifact.get("parsed_text")
    return {
        "attachment_id": artifact.get("attachment_id"),
        "name": artifact.get("name"),
        "kind": artifact.get("kind"),
        "status": artifact.get("status"),
        "mime_type": artifact.get("mime_type"),
        "summary_for_model": artifact.get("summary_for_model"),
        "confidence": artifact.get("confidence"),
        "structured_data": artifact.get("structured_data"),
        "provenance": artifact.get("provenance"),
        "error": artifact.get("error"),
        "parsed_text_length": len(parsed_text) if isinstance(parsed_text, str) else 0,
        "parsed_text_preview": (
            parsed_text[:preview_chars] if isinstance(parsed_text, str) else None
        ),
    }


def _message_snapshot(message: Any) -> dict[str, Any]:
    content = getattr(message, "content", None)
    normalized_content = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                normalized_content.append(
                    {
                        "type": item.get("type"),
                        "text": item.get("text"),
                        "mimeType": item.get("mimeType") or item.get("mime_type"),
                        "payload_length": (
                            len(item.get("data") or item.get("base64"))
                            if isinstance(item.get("data") or item.get("base64"), str)
                            else 0
                        ),
                        "metadata": item.get("metadata"),
                    }
                )
            else:
                normalized_content.append(item)
    else:
        normalized_content = content
    return {
        "type": getattr(message, "type", None),
        "content": normalized_content,
    }


def _read_state_attachments(
    state: Mapping[str, Any] | None,
) -> list[AttachmentArtifact]:
    if state is None:
        return []
    value = state.get(MULTIMODAL_ATTACHMENTS_KEY)
    return value if isinstance(value, list) else []


def _read_state_summary(state: Mapping[str, Any] | None) -> str | None:
    if state is None:
        return None
    value = state.get(MULTIMODAL_SUMMARY_KEY)
    return value if isinstance(value, str) else None


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run multimodal middleware self-check for one or more local files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="附件路径。可直接传图片/PDF，也可传目录；为空时默认扫描 runtime_service/test_data。",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="附件路径。可重复传入多次。",
    )
    parser.add_argument(
        "--text",
        default="请分析这个附件，并告诉我主模型最终会看到什么。",
        help="模拟用户消息文本。",
    )
    parser.add_argument(
        "--system-prompt",
        default="You are a helpful assistant.",
        help="模拟 system prompt。",
    )
    parser.add_argument(
        "--parser-model-id",
        default=get_default_multimodal_model_id(),
        help="多模态解析模型 ID。",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=400,
        help="parsed_text 预览长度。",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="只跑协议归一化与 artifact 准备，不触发真实 parser 模型。",
    )
    parser.add_argument(
        "--detail-mode",
        action="store_true",
        help="开启后，把 parsed_text 片段也注入主模型消息与 system prompt。",
    )
    parser.add_argument(
        "--detail-text-max-chars",
        type=int,
        default=2000,
        help="detail 模式下注入的 parsed_text 最大字符数。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    mimetypes.add_type("image/webp", ".webp")

    args = _build_arg_parser().parse_args(argv)
    input_paths = _resolve_input_paths(args.paths, args.file)
    if not input_paths:
        print("未找到可用附件。请传入图片/PDF，或在 runtime_service/test_data 中放置样本。")
        return 2

    input_summary = [
        {
            "path": str(path),
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "mime": _detect_mime(path),
        }
        for path in input_paths
    ]
    _print_section("Input Files", input_summary)

    blocks = [file_path_to_frontend_content_block(path) for path in input_paths]
    _print_section("Frontend Blocks", [_block_snapshot(block) for block in blocks])

    raw_message = build_human_message(args.text, blocks=blocks)
    normalized_messages = normalize_messages([raw_message])
    _print_section("Normalized Messages", [_message_snapshot(msg) for msg in normalized_messages])

    middleware = MultimodalMiddleware(
        parser_model_id=args.parser_model_id,
        detail_mode=args.detail_mode,
        detail_text_max_chars=max(0, args.detail_text_max_chars),
    )
    prepared_state, pairs, rewrite_count = middleware._prepare_artifact_parsing(
        normalized_messages, {}
    )
    prepared_artifacts = [artifact for artifact, _ in pairs]
    _print_section(
        "Prepared Artifacts",
        [
            _artifact_snapshot(dict(artifact), preview_chars=args.preview_chars)
            for artifact in prepared_artifacts
        ],
    )
    _print_section("Rewrite Artifact Count", rewrite_count)
    _print_section(
        "Before Model State",
        middleware.before_model(
            MultimodalAgentState(messages=[raw_message]),
            runtime=None,
        )
        or {},
    )

    if args.prepare_only:
        print("\n只执行到 prepare 阶段，未触发 parser 模型调用。")
        return 0

    request = ModelRequest(
        model=FakeListChatModel(responses=["ok"]),
        messages=[raw_message],
        system_message=SystemMessage(content=args.system_prompt),
        state=None,
    )
    captured_request: ModelRequest | None = None

    def handler(updated_request: ModelRequest) -> ModelResponse:
        nonlocal captured_request
        captured_request = updated_request
        return ModelResponse(result=[AIMessage(content="ok")])

    try:
        middleware.wrap_model_call(request, handler)
    except Exception as exc:
        print(f"\nwrap_model_call 失败: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1

    if captured_request is None:
        print("\nwrap_model_call 未返回更新后的 request。", file=sys.stderr)
        return 1

    state = captured_request.state
    parsed_artifacts = _read_state_attachments(state)
    _print_section(
        "Parsed Artifacts",
        [
            _artifact_snapshot(artifact, preview_chars=args.preview_chars)
            for artifact in parsed_artifacts
        ],
    )
    _print_section(
        "Rewritten Messages",
        [_message_snapshot(message) for message in captured_request.messages],
    )
    _print_section(
        "Injected System Prompt",
        captured_request.system_prompt or "",
    )
    _print_section(
        "Multimodal Summary",
        _read_state_summary(state),
    )

    failed_statuses = [
        artifact.get("status")
        for artifact in parsed_artifacts
        if artifact.get("kind") in {"image", "pdf"} and artifact.get("status") != "parsed"
    ]
    if failed_statuses:
        print("\n存在未成功解析的 image/pdf 附件，请检查上面的 error 与 summary。", file=sys.stderr)
        return 1

    print("\n多模态中间件自测通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
