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
from runtime_service.tests.services_test_case_service_debug import (  # noqa: E402
    _print_section,
    _resolve_pdf_path,
    _resolve_runtime_model_preview,
    _stream_agent_run,
)

DOCUMENTS_PATH = "/api/test-case-service/documents"
TEST_CASES_PATH = "/api/test-case-service/test-cases"
PERSISTENCE_STATUSES = (
    "persisted",
    "partial_failed",
    "failed_remote_request",
    "failed_invalid_project_id",
    "skipped_remote_not_configured",
    "skipped_empty_test_cases",
    "failed_missing_project_id",
)


def _verify_remote_results(
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
    test_cases = client.get_json(
        TEST_CASES_PATH,
        params={"project_id": project_id, "batch_id": batch_id, "limit": 50},
    )
    case_items = test_cases.get("items", []) if isinstance(test_cases.get("items"), list) else []
    return {
        "documents_total": documents.get("total"),
        "document_ids": [item.get("id") for item in documents.get("items", []) if isinstance(item, dict)],
        "test_cases_total": test_cases.get("total"),
        "test_case_titles": [
            item.get("title") for item in case_items if isinstance(item, dict)
        ],
        "test_case_source_document_ids": [
            {
                "title": item.get("title"),
                "source_document_ids": item.get("source_document_ids"),
            }
            for item in case_items
            if isinstance(item, dict)
        ],
        "raw_documents": documents,
        "raw_test_cases": test_cases,
    }


def _detect_persistence_status(output_text: Any) -> str | None:
    if not isinstance(output_text, str) or not output_text:
        return None
    for status in PERSISTENCE_STATUSES:
        if (
            f'"status":"{status}"' in output_text
            or f'"status": "{status}"' in output_text
        ):
            return status
    return None


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a real end-to-end persistence validation for test_case_service."
    )
    parser.add_argument("--pdf", help="要上传的 PDF 路径。默认使用 runtime_service/test_data 下第一个 PDF。")
    parser.add_argument(
        "--question",
        default=(
            "请按最小交付模式执行：1）先读取相关 skills；2）基于这个 PDF 给出 1 段需求摘要；3）输出不超过 4 条正式测试用例；"
            "4）给出 1 条质量评审结论；5）立即调用持久化工具把附件解析结果和正式测试用例保存到数据库；"
            "6）最后只简短汇报保存结果。除上述内容外不要展开。"
        ),
        help="发送给 test_case_service 的真实问题。",
    )
    parser.add_argument("--model-id", default="deepseek_chat", help="主模型 ID。")
    parser.add_argument(
        "--project-id",
        required=True,
        type=parse_uuid_arg,
        help="显式 project_id；必须是 UUID，真实链路验证不再允许 default project fallback。",
    )
    parser.add_argument(
        "--parser-model-id",
        default=None,
        help="可选：覆盖多模态解析模型 ID。",
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
    thread_id = str(uuid4())
    batch_id = f"test-case-service:{thread_id}"
    message = build_human_message_from_paths(args.question, [pdf_path])

    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "interaction_data_service_timeout_seconds": args.interaction_timeout,
        }
    }
    if args.interaction_url:
        config["configurable"]["interaction_data_service_url"] = args.interaction_url
    if args.parser_model_id:
        config["configurable"]["test_case_multimodal_parser_model_id"] = args.parser_model_id
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
        project_id=project_id,
    )
    model_preview = _resolve_runtime_model_preview(args.model_id)
    _print_section(
        "Persistence Input",
        {
            "pdf_path": str(pdf_path),
            "question": args.question,
            "model_id": args.model_id,
            **model_preview,
            "project_id": project_id,
            "thread_id": thread_id,
            "batch_id": batch_id,
            "interaction_data_service_url": build_interaction_data_service_config(config).service_url,
            "interaction_timeout_seconds": args.interaction_timeout,
        },
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
    if "persist_test_case_results" not in graph_report.get("tool_calls", []):
        _print_section(
            "Remote Verification Skipped",
            {"reason": "persist_test_case_results_not_called"},
        )
        return 1
    persistence_status = _detect_persistence_status(graph_report.get("output_text"))
    if persistence_status and persistence_status != "persisted":
        _print_section(
            "Remote Verification Skipped",
            {
                "reason": "persistence_not_completed",
                "persistence_status": persistence_status,
            },
        )
        return 1

    try:
        remote_report = await asyncio.to_thread(
            _verify_remote_results,
            config=config,
            project_id=project_id,
            batch_id=batch_id,
        )
    except Exception as exc:
        _print_section(
            "Remote Verification Failed",
            {
                "reason": "interaction_data_service_request_failed",
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                "persistence_status": persistence_status,
            },
        )
        return 1
    _print_section("Remote Verification", remote_report)

    if int(remote_report.get("documents_total") or 0) <= 0:
        print("文档未写入远端服务", file=sys.stderr)
        return 1
    if int(remote_report.get("test_cases_total") or 0) <= 0:
        print("测试用例未写入远端服务", file=sys.stderr)
        return 1
    if any(
        not isinstance(item.get("source_document_ids"), list) or not item.get("source_document_ids")
        for item in remote_report.get("test_case_source_document_ids", [])
        if isinstance(item, dict)
    ):
        print("存在测试用例未关联 source_document_ids", file=sys.stderr)
        return 1
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
