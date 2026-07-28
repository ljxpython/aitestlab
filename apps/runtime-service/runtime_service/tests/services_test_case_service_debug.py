# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_ENV_FILE = _PROJECT_ROOT / "runtime_service" / ".env"
if _ENV_FILE.exists():
    from dotenv import load_dotenv

    load_dotenv(_ENV_FILE, override=False)

os.environ.setdefault("APP_ENV", "test")

from runtime_service.conf.settings import require_model_spec  # noqa: E402
from runtime_service.devtools.multimodal_frontend_compat import (  # noqa: E402
    build_human_message_from_paths,
    file_path_to_frontend_content_block,
)
from runtime_service.middlewares.multimodal import (  # noqa: E402
    MULTIMODAL_ATTACHMENTS_KEY,
    MULTIMODAL_SUMMARY_KEY,
    MultimodalMiddleware,
    normalize_messages,
)
from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.services.test_case_service.graph import (  # noqa: E402
    TEST_CASE_DEFAULTS,
    graph,
)
from runtime_service.services.test_case_service.prompts import SYSTEM_PROMPT  # noqa: E402
from runtime_service.services.test_case_service.schemas import (  # noqa: E402
    build_test_case_service_config,
)

KNOWLEDGE_TOOL_NAMES = {
    "query_project_knowledge",
    "list_project_knowledge_documents",
    "get_project_knowledge_document_status",
}


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _print_section(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(payload, str):
        print(payload)
        return
    print(_json_dump(payload))


def _resolve_runtime_model_preview(model_id: str | None) -> dict[str, str]:
    requested_model_id = model_id or TEST_CASE_DEFAULTS.model_id
    resolved_model_id, spec = require_model_spec(requested_model_id)
    return {
        "runtime_model_id": resolved_model_id,
        "runtime_model": spec["model"],
        "runtime_provider": spec["model_provider"],
    }


def _default_pdf_path() -> Path:
    test_data_dir = _PROJECT_ROOT / "runtime_service" / "test_data"
    pdfs = sorted(test_data_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDF found in {test_data_dir}")
    return pdfs[0]


def _resolve_pdf_path(raw: str | None) -> Path:
    if raw is None:
        return _default_pdf_path().resolve()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    return path.resolve()


def _chunk_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _message_snapshot(message: Any) -> dict[str, Any]:
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return {"type": getattr(message, "type", None), "content": content}

    normalized_content: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            normalized_content.append({"raw_type": type(item).__name__})
            continue
        payload = item.get("data") or item.get("base64")
        normalized_content.append(
            {
                "type": item.get("type"),
                "text_preview": (
                    item.get("text", "")[:200]
                    if isinstance(item.get("text"), str)
                    else None
                ),
                "mime_type": item.get("mimeType") or item.get("mime_type"),
                "payload_length": len(payload) if isinstance(payload, str) else 0,
                "metadata": item.get("metadata"),
            }
        )
    return {"type": getattr(message, "type", None), "content": normalized_content}


def _summarize_update(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {"event_type": type(event).__name__}

    summary: dict[str, Any] = {}
    for key, value in event.items():
        if key == "SkillsMiddleware.before_agent" and isinstance(value, dict):
            skills = value.get("skills_metadata")
            names = []
            if isinstance(skills, list):
                names = [
                    item.get("name")
                    for item in skills
                    if isinstance(item, dict) and isinstance(item.get("name"), str)
                ]
            summary[key] = {"skills_count": len(names), "skills": names}
            continue

        if key == "MultimodalMiddleware.before_model" and isinstance(value, dict):
            attachments = value.get(MULTIMODAL_ATTACHMENTS_KEY)
            summary[key] = {
                "attachments_count": (
                    len(attachments) if isinstance(attachments, list) else 0
                ),
                "attachment_statuses": [
                    item.get("status")
                    for item in attachments
                    if isinstance(item, dict)
                ]
                if isinstance(attachments, list)
                else [],
                "has_summary": MULTIMODAL_SUMMARY_KEY in value,
            }
            continue

        if key == "TestCaseDocumentPersistenceMiddleware.before_model" and isinstance(value, dict):
            attachments = value.get(MULTIMODAL_ATTACHMENTS_KEY)
            summary[key] = {
                "attachments_count": (
                    len(attachments) if isinstance(attachments, list) else 0
                ),
                "persist_statuses": [
                    item.get("persist_status")
                    for item in attachments
                    if isinstance(item, dict)
                ]
                if isinstance(attachments, list)
                else [],
                "persisted_document_ids": [
                    item.get("persisted_document_id")
                    for item in attachments
                    if isinstance(item, dict)
                ]
                if isinstance(attachments, list)
                else [],
                "has_persist_errors": any(
                    isinstance(item, dict) and item.get("persist_error")
                    for item in attachments
                )
                if isinstance(attachments, list)
                else False,
            }
            continue

        if key == "PatchToolCallsMiddleware.before_agent":
            summary[key] = {"note": "messages patched"}
            continue

        if isinstance(value, dict):
            summary[key] = {"keys": list(value.keys())[:8]}
            continue

        summary[key] = {"value_type": type(value).__name__}
    return summary


async def _run_multimodal_preflight(
    *,
    message: Any,
    config: RunnableConfig,
) -> dict[str, Any]:
    service_config = build_test_case_service_config(config)
    middleware = MultimodalMiddleware(
        parser_model_id=service_config.multimodal_parser_model_id,
        detail_mode=service_config.multimodal_detail_mode,
        detail_text_max_chars=service_config.multimodal_detail_text_max_chars,
    )

    normalized_messages = normalize_messages([message])
    initial_state = {"messages": normalized_messages}
    before_updates = middleware.before_model(cast(Any, initial_state), runtime=None) or {}
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=normalized_messages,
        system_message=SystemMessage(content=SYSTEM_PROMPT),
        state=cast(Any, before_updates),
    )

    captured: dict[str, Any] = {}

    async def handler(updated_request: ModelRequest) -> ModelResponse:
        captured["request"] = updated_request
        return ModelResponse(result=[AIMessage(content="ok")])

    await middleware.awrap_model_call(request, handler)
    updated_request = cast(ModelRequest, captured["request"])
    updated_messages = list(updated_request.messages)
    content = getattr(updated_messages[-1], "content", [])
    remaining_attachment_blocks = 0
    if isinstance(content, list):
        remaining_attachment_blocks = sum(
            1
            for item in content
            if isinstance(item, dict) and item.get("type") in {"file", "image"}
        )

    attachments = cast(
        list[dict[str, Any]],
        updated_request.state.get(MULTIMODAL_ATTACHMENTS_KEY) or [],
    )
    return {
        "parser_model_id": service_config.multimodal_parser_model_id,
        "detail_mode": service_config.multimodal_detail_mode,
        "attachments_count": len(attachments),
        "attachment_statuses": [item.get("status") for item in attachments],
        "remaining_attachment_blocks": remaining_attachment_blocks,
        "system_has_multimodal_section": "## Multimodal Attachments"
        in (
            updated_request.system_message.content
            if getattr(updated_request.system_message, "content", None)
            else ""
        ),
        "latest_message": _message_snapshot(updated_messages[-1]),
    }


async def _stream_agent_run(
    *,
    message: Any,
    config: RunnableConfig,
    runtime_context: RuntimeContext,
    timeout_seconds: float,
) -> dict[str, Any]:
    agent = graph
    stream_chunks: list[str] = []
    tool_calls: list[str] = []
    update_summaries: list[dict[str, Any]] = []

    async def _run_stream() -> None:
        async for mode, event in agent.astream(
            {"messages": [message]},
            config=config,
            context=runtime_context,
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                stream_message, _metadata = event
                text = _chunk_text(getattr(stream_message, "content", ""))
                if text:
                    stream_chunks.append(text)
                    print(text, end="", flush=True)

                for tool_call in getattr(stream_message, "tool_calls", []) or []:
                    if isinstance(tool_call, dict):
                        name = tool_call.get("name")
                    else:
                        name = getattr(tool_call, "name", None)
                    if isinstance(name, str) and name:
                        tool_calls.append(name)
                continue

            update_summary = _summarize_update(event)
            update_summaries.append(update_summary)
            print("\nupdate", _json_dump(update_summary), flush=True)

    try:
        await asyncio.wait_for(_run_stream(), timeout=timeout_seconds)
    except Exception as exc:
        return {
            "ok": False,
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
            "tool_calls": tool_calls,
            "updates": update_summaries,
            "output_text": "".join(stream_chunks),
        }

    return {
        "ok": True,
        "tool_calls": tool_calls,
        "knowledge_tool_calls": [name for name in tool_calls if name in KNOWLEDGE_TOOL_NAMES],
        "skill_related_tool_calls": [
            name for name in tool_calls if name in {"read_file", "ls", "glob"}
        ],
        "document_persistence_updates": [
            item.get("TestCaseDocumentPersistenceMiddleware.before_model")
            for item in update_summaries
            if isinstance(item, dict)
            and isinstance(item.get("TestCaseDocumentPersistenceMiddleware.before_model"), dict)
        ],
        "updates": update_summaries,
        "output_text": "".join(stream_chunks),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Debug test_case_service with a real PDF and a real model."
    )
    parser.add_argument("--pdf", help="要上传的 PDF 路径。默认使用 runtime_service/test_data 下第一个 PDF。")
    parser.add_argument(
        "--question",
        default="请先分析这个 PDF 的主要内容，再给出测试要点，并说明你实际使用了哪些 skills。",
        help="发送给 test_case_service 的真实问题。",
    )
    parser.add_argument(
        "--model-id",
        default="deepseek_chat",
        help="主模型 ID。",
    )
    parser.add_argument(
        "--parser-model-id",
        default=None,
        help="可选：覆盖多模态解析模型 ID。",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="真实 graph 流式调用超时时间，单位秒。",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="跳过 MultimodalMiddleware 预检。",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="可选：显式 project_id。用于知识库 MCP 或正式项目作用域联调。",
    )
    parser.add_argument(
        "--knowledge-mcp-url",
        default=None,
        help="可选：覆盖 test_case_service 私有知识库 MCP SSE 地址。",
    )
    parser.add_argument(
        "--knowledge-timeout",
        type=int,
        default=None,
        help="可选：覆盖知识库 MCP 连接超时秒数。",
    )
    parser.add_argument(
        "--knowledge-sse-read-timeout",
        type=int,
        default=None,
        help="可选：覆盖知识库 MCP SSE 读超时秒数。",
    )
    return parser


async def _main_async(args: argparse.Namespace) -> int:
    pdf_path = _resolve_pdf_path(args.pdf)
    block = file_path_to_frontend_content_block(pdf_path)
    message = build_human_message_from_paths(args.question, [pdf_path])

    config: RunnableConfig = {
        "configurable": {
            "thread_id": str(uuid4()),
        }
    }
    if args.parser_model_id:
        config["configurable"]["test_case_multimodal_parser_model_id"] = args.parser_model_id
    if args.knowledge_mcp_url:
        config["configurable"]["test_case_knowledge_mcp_url"] = args.knowledge_mcp_url
    if args.knowledge_timeout is not None:
        config["configurable"]["test_case_knowledge_timeout_seconds"] = args.knowledge_timeout
    if args.knowledge_sse_read_timeout is not None:
        config["configurable"]["test_case_knowledge_sse_read_timeout_seconds"] = (
            args.knowledge_sse_read_timeout
        )

    config["configurable"]["platform_local_debug"] = True
    config["configurable"]["platform_runtime"] = {
        "model_id": args.model_id,
        "multimodal_parser_model_id": args.parser_model_id,
    }
    runtime_context = RuntimeContext(
        user_id="local-debug",
        tenant_id="local-debug",
        role="debug",
        permissions=[],
        project_id=args.project_id,
    )
    service_config = build_test_case_service_config(config)
    model_preview = _resolve_runtime_model_preview(args.model_id)

    _print_section(
        "Input",
        {
            "pdf_path": str(pdf_path),
            "pdf_size_bytes": pdf_path.stat().st_size,
            "question": args.question,
            "model_id": args.model_id,
            "parser_model_id": service_config.multimodal_parser_model_id,
            **model_preview,
            "project_id": args.project_id,
            "knowledge_mcp_enabled": service_config.knowledge_mcp_enabled,
            "knowledge_mcp_url": service_config.knowledge_mcp_url,
            "knowledge_timeout_seconds": service_config.knowledge_timeout_seconds,
            "knowledge_sse_read_timeout_seconds": service_config.knowledge_sse_read_timeout_seconds,
        },
    )
    _print_section(
        "Frontend Block",
        {
            "type": block.get("type"),
            "mimeType": block.get("mimeType"),
            "payload_length": len(block.get("data", "")),
            "metadata": block.get("metadata"),
        },
    )

    if not args.skip_preflight:
        try:
            preflight_report = await _run_multimodal_preflight(
                message=message,
                config=config,
            )
        except Exception as exc:
            _print_section(
                "Preflight Error",
                {
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            return 1
        _print_section("Multimodal Preflight", preflight_report)

    print("\n=== Graph Stream ===")
    graph_report = await _stream_agent_run(
        message=message,
        config=config,
        runtime_context=runtime_context,
        timeout_seconds=max(1.0, args.timeout),
    )
    print()
    _print_section("Graph Report", graph_report)

    return 0 if graph_report.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = _build_arg_parser().parse_args(argv)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
