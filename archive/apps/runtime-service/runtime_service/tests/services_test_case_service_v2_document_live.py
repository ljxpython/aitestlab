# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_ENV_FILE = _PROJECT_ROOT / "runtime_service" / ".env"
if _ENV_FILE.exists():
    from dotenv import load_dotenv

    load_dotenv(_ENV_FILE, override=False)

os.environ.setdefault("APP_ENV", "test")

from runtime_service.devtools.multimodal_frontend_compat import (  # noqa: E402
    build_human_message_from_paths,
)
from runtime_service.integrations import (  # noqa: E402
    InteractionDataServiceClient,
    build_interaction_data_service_config,
)
from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.tests.live_args import parse_uuid_arg  # noqa: E402
from runtime_service.tests.services_test_case_service_v2_debug import (  # noqa: E402
    _print_section,
    _resolve_pdf_path,
    _resolve_runtime_model_preview,
    _stream_agent_run,
)

DOCUMENTS_PATH = "/api/test-case-service/documents"


def _verify_remote_documents(
    *,
    config: RunnableConfig,
    project_id: str,
    batch_id: str,
) -> dict[str, Any]:
    client = InteractionDataServiceClient(build_interaction_data_service_config(config))
    if not client.is_configured:
        raise RuntimeError("interaction_data_service_not_configured")
    documents = client.get_json(
        DOCUMENTS_PATH,
        params={"project_id": project_id, "batch_id": batch_id, "limit": 20},
    )
    items = documents.get("items", []) if isinstance(documents.get("items"), list) else []
    return {
        "documents_total": documents.get("total"),
        "document_ids": [item.get("id") for item in items if isinstance(item, dict)],
        "idempotency_keys": [
            item.get("idempotency_key") for item in items if isinstance(item, dict)
        ],
        "parse_statuses": [item.get("parse_status") for item in items if isinstance(item, dict)],
        "filenames": [item.get("filename") for item in items if isinstance(item, dict)],
        "storage_paths": [item.get("storage_path") for item in items if isinstance(item, dict)],
        "raw_documents": documents,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate test_case_service_v2 document flow with a real PDF and a real model."
    )
    parser.add_argument("--pdf", help="要上传的 PDF 路径。默认使用 runtime_service/test_data 下第一个 PDF。")
    parser.add_argument(
        "--question",
        default=(
            "请按最小交付执行：1）先读取相关 skills；2）基于上传 PDF 给出 1 段简短需求摘要；"
            "3）列出不超过 3 条测试关注点；4）不要调用任何正式测试用例持久化工具。"
        ),
        help="发送给 test_case_service_v2 的真实问题。",
    )
    parser.add_argument("--model-id", default="deepseek_chat", help="主模型 ID。")
    parser.add_argument(
        "--project-id",
        required=True,
        type=parse_uuid_arg,
        help="显式 project_id；document live 验证必须是 UUID。",
    )
    parser.add_argument(
        "--parser-model-id",
        default="doubao_vision_mini",
        help="覆盖多模态解析模型 ID。",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        help="真实 graph 流式调用超时时间，单位秒。",
    )
    parser.add_argument(
        "--interaction-timeout",
        type=int,
        default=60,
        help="interaction-data-service HTTP 超时，单位秒。",
    )
    parser.add_argument(
        "--interaction-url",
        default=None,
        help="显式 interaction-data-service URL；不传则走环境变量或默认配置。",
    )
    return parser


async def _main_async(args: argparse.Namespace) -> int:
    pdf_path = _resolve_pdf_path(args.pdf)
    project_id = args.project_id
    batch_id = f"test-case-service-v2-document-live:{uuid4()}"
    message = build_human_message_from_paths(args.question, [pdf_path])

    base_configurable: dict[str, Any] = {
        "batch_id": batch_id,
        "interaction_data_service_timeout_seconds": args.interaction_timeout,
        "test_case_v2_persistence_enabled": True,
        "test_case_v2_knowledge_mcp_enabled": False,
        "test_case_v2_multimodal_parser_model_id": args.parser_model_id,
        "platform_local_debug": True,
        "platform_runtime": {
            "model_id": args.model_id,
            "multimodal_parser_model_id": args.parser_model_id,
        },
    }
    if args.interaction_url:
        base_configurable["interaction_data_service_url"] = args.interaction_url

    runtime_context = RuntimeContext(
        user_id="local-debug",
        tenant_id="local-debug",
        role="debug",
        permissions=[],
        project_id=project_id,
    )
    model_preview = _resolve_runtime_model_preview(args.model_id)
    _print_section(
        "Document Live Input",
        {
            "pdf_path": str(pdf_path),
            "question": args.question,
            "model_id": args.model_id,
            **model_preview,
            "parser_model_id": args.parser_model_id,
            "project_id": project_id,
            "batch_id": batch_id,
            "interaction_data_service_url": build_interaction_data_service_config(
                {"configurable": base_configurable}
            ).service_url,
            "interaction_timeout_seconds": args.interaction_timeout,
        },
    )

    thread_id = f"{batch_id}:run-1"
    config: RunnableConfig = {"configurable": dict(base_configurable, thread_id=thread_id)}
    _print_section(
        "Run Config",
        {"thread_id": thread_id, "batch_id": batch_id},
    )

    print("\n=== Graph Stream ===")
    graph_report = await _stream_agent_run(
        message=message,
        config=config,
        runtime_context=runtime_context,
        timeout_seconds=max(1.0, args.timeout),
    )
    print()
    _print_section("Graph Report", graph_report)
    if not graph_report.get("ok"):
        return 1

    remote_report = await asyncio.to_thread(
        _verify_remote_documents,
        config=config,
        project_id=project_id,
        batch_id=batch_id,
    )
    _print_section("Remote Documents", remote_report)

    total = int(remote_report.get("documents_total") or 0)
    if total <= 0:
        print("本次验证未查询到即时落库的 document。", file=sys.stderr)
        return 1
    if any(not path for path in (remote_report.get("storage_paths") or [])):
        print("存在 document 未写入 storage_path，原始 PDF 资产链路不完整。", file=sys.stderr)
        return 1

    _print_section(
        "Validation Summary",
        {
            "project_id": project_id,
            "batch_id": batch_id,
            "documents_total": total,
            "document_ids": remote_report.get("document_ids") or [],
        },
    )
    return 0


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
