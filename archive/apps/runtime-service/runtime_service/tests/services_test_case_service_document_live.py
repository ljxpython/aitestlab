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
        "asset_errors": [
            (
                ((item.get("provenance") or {}).get("asset") or {}).get("error")
                if isinstance(item.get("provenance"), dict)
                else None
            )
            for item in items
            if isinstance(item, dict)
        ],
        "raw_documents": documents,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate test_case_service immediate document persistence with a real PDF and a real model."
    )
    parser.add_argument("--pdf", help="要上传的 PDF 路径。默认使用 runtime_service/test_data 下第一个 PDF。")
    parser.add_argument(
        "--question",
        default=(
            "请按最小交付执行：1）先读取相关 skills；2）基于上传 PDF 给出 1 段简短需求摘要；"
            "3）列出不超过 3 条测试关注点；4）不要调用任何持久化工具，也不要声称已保存。"
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
    parser.add_argument(
        "--runs",
        type=int,
        default=2,
        help="同一 batch 重复运行次数，默认 2 次，用于验证幂等。",
    )
    return parser


async def _run_once(
    *,
    message: Any,
    config: RunnableConfig,
    runtime_context: RuntimeContext,
    project_id: str,
    batch_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    print("\n=== Graph Stream ===")
    graph_report = await _stream_agent_run(
        message=message,
        config=config,
        runtime_context=runtime_context,
        timeout_seconds=max(1.0, timeout_seconds),
    )
    print()
    _print_section("Graph Report", graph_report)
    if not graph_report.get("ok"):
        return {
            "ok": False,
            "graph_report": graph_report,
        }

    remote_report = await asyncio.to_thread(
        _verify_remote_documents,
        config=config,
        project_id=project_id,
        batch_id=batch_id,
    )
    _print_section("Remote Documents", remote_report)
    return {
        "ok": True,
        "graph_report": graph_report,
        "remote_report": remote_report,
    }


async def _main_async(args: argparse.Namespace) -> int:
    pdf_path = _resolve_pdf_path(args.pdf)
    project_id = args.project_id
    batch_id = f"test-case-service-document-live:{uuid4()}"
    message = build_human_message_from_paths(args.question, [pdf_path])

    base_configurable: dict[str, Any] = {
        "batch_id": batch_id,
        "interaction_data_service_timeout_seconds": args.interaction_timeout,
    }
    if args.interaction_url:
        base_configurable["interaction_data_service_url"] = args.interaction_url
    if args.parser_model_id:
        base_configurable["test_case_multimodal_parser_model_id"] = args.parser_model_id
    base_configurable["platform_local_debug"] = True
    base_configurable["platform_runtime"] = {
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
        "Document Persistence Input",
        {
            "pdf_path": str(pdf_path),
            "question": args.question,
            "model_id": args.model_id,
            **model_preview,
            "project_id": project_id,
            "batch_id": batch_id,
            "runs": args.runs,
            "interaction_data_service_url": build_interaction_data_service_config(
                {"configurable": base_configurable}
            ).service_url,
            "interaction_timeout_seconds": args.interaction_timeout,
        },
    )

    run_reports: list[dict[str, Any]] = []
    for index in range(max(1, args.runs)):
        thread_id = f"{batch_id}:run-{index + 1}"
        config: RunnableConfig = {"configurable": dict(base_configurable, thread_id=thread_id)}
        _print_section(
            f"Run {index + 1} Config",
            {"thread_id": thread_id, "batch_id": batch_id},
        )
        run_report = await _run_once(
            message=message,
            config=config,
            runtime_context=runtime_context,
            project_id=project_id,
            batch_id=batch_id,
            timeout_seconds=args.timeout,
        )
        run_reports.append(run_report)
        if not run_report.get("ok"):
            return 1

    first_remote = run_reports[0]["remote_report"]
    final_remote = run_reports[-1]["remote_report"]
    first_total = int(first_remote.get("documents_total") or 0)
    final_total = int(final_remote.get("documents_total") or 0)
    first_ids = list(first_remote.get("document_ids") or [])
    final_ids = list(final_remote.get("document_ids") or [])

    if any("persist_test_case_results" in (report["graph_report"].get("tool_calls") or []) for report in run_reports):
        print("本次验证不应调用 persist_test_case_results，但模型实际调用了该工具。", file=sys.stderr)
        return 1
    if first_total <= 0:
        print("首轮运行后未查询到即时落库的 document。", file=sys.stderr)
        return 1
    if any(not path for path in (first_remote.get("storage_paths") or [])):
        print("存在 document 未写入 storage_path，原始 PDF 资产链路不完整。", file=sys.stderr)
        return 1
    if any(error for error in (first_remote.get("asset_errors") or [])):
        print("存在 document asset 错误，原始 PDF 资产链路未闭环。", file=sys.stderr)
        return 1
    if final_total != first_total:
        print(
            f"同一 batch 重复运行后 documents_total 发生变化: first={first_total}, final={final_total}",
            file=sys.stderr,
        )
        return 1
    if sorted(first_ids) != sorted(final_ids):
        print(
            "同一 batch 重复运行后 document_id 集合发生变化，幂等不成立。",
            file=sys.stderr,
        )
        return 1

    _print_section(
        "Validation Summary",
        {
            "documents_total": final_total,
            "document_ids": final_ids,
            "runs": args.runs,
            "idempotent": True,
            "tool_persistence_called": False,
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
