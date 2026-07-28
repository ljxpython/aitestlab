# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_ENV_FILE = _PROJECT_ROOT / "runtime_service" / ".env"
if _ENV_FILE.exists():
    from dotenv import load_dotenv

    load_dotenv(_ENV_FILE, override=False)

os.environ.setdefault("APP_ENV", "test")

from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.tests.live_args import parse_uuid_arg  # noqa: E402
from runtime_service.tests.services_test_case_service_debug import (  # noqa: E402
    KNOWLEDGE_TOOL_NAMES,
    _print_section,
    _resolve_runtime_model_preview,
    _stream_agent_run,
)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate that test_case_service can call private knowledge MCP tools in a real agent run."
    )
    parser.add_argument(
        "--project-id",
        required=True,
        type=parse_uuid_arg,
        help="显式 project_id；知识库联调必须提供，且必须是 UUID。",
    )
    parser.add_argument(
        "--question",
        default=(
            "请先读取相关 skills，然后基于当前项目知识库中的需求文档和历史规则给出不超过 3 条测试关注点。"
            "如果不知道有哪些文档，先查看文档列表；如果怀疑文档未完成索引，再检查状态。"
            "不要保存结果。"
        ),
        help="发送给 test_case_service 的真实问题。",
    )
    parser.add_argument("--model-id", default="deepseek_chat", help="主模型 ID。")
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="真实 graph 流式调用超时时间，单位秒。",
    )
    parser.add_argument(
        "--knowledge-mcp-url",
        default="http://0.0.0.0:8000/sse",
        help="私有知识库 MCP 的 SSE 地址。",
    )
    parser.add_argument(
        "--knowledge-timeout",
        type=int,
        default=30,
        help="知识库 MCP 连接超时秒数。",
    )
    parser.add_argument(
        "--knowledge-sse-read-timeout",
        type=int,
        default=300,
        help="知识库 MCP SSE 读超时秒数。",
    )
    parser.add_argument(
        "--require-query-tool",
        action="store_true",
        help="要求本次真实联调必须至少调用一次 query_project_knowledge。",
    )
    return parser


async def _main_async(args: argparse.Namespace) -> int:
    thread_id = str(uuid4())
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "test_case_knowledge_mcp_enabled": True,
            "test_case_knowledge_mcp_url": args.knowledge_mcp_url,
            "test_case_knowledge_timeout_seconds": args.knowledge_timeout,
            "test_case_knowledge_sse_read_timeout_seconds": args.knowledge_sse_read_timeout,
            "platform_local_debug": True,
            "platform_runtime": {"model_id": args.model_id},
        }
    }
    runtime_context = RuntimeContext(
        user_id="local-debug",
        tenant_id="local-debug",
        role="debug",
        permissions=[],
        project_id=args.project_id,
    )
    model_preview = _resolve_runtime_model_preview(args.model_id)
    message = HumanMessage(content=args.question)

    _print_section(
        "Knowledge Live Input",
        {
            "question": args.question,
            "model_id": args.model_id,
            **model_preview,
            "project_id": args.project_id,
            "thread_id": thread_id,
            "knowledge_mcp_url": args.knowledge_mcp_url,
            "knowledge_timeout_seconds": args.knowledge_timeout,
            "knowledge_sse_read_timeout_seconds": args.knowledge_sse_read_timeout,
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
    _print_section("Knowledge Live Report", graph_report)

    if not graph_report.get("ok"):
        return 1

    knowledge_tool_calls = [
        name for name in (graph_report.get("tool_calls") or []) if name in KNOWLEDGE_TOOL_NAMES
    ]
    if not knowledge_tool_calls:
        print("本次验证未观察到任何知识库 MCP 工具调用。", file=sys.stderr)
        return 1
    if args.require_query_tool and "query_project_knowledge" not in knowledge_tool_calls:
        print(
            "本次验证要求命中 query_project_knowledge，但实际未调用该工具。",
            file=sys.stderr,
        )
        return 1
    if "persist_test_case_results" in (graph_report.get("tool_calls") or []):
        print("本次知识库验证不应调用 persist_test_case_results。", file=sys.stderr)
        return 1

    _print_section(
        "Knowledge Validation Summary",
        {
            "project_id": args.project_id,
            "knowledge_tool_calls": knowledge_tool_calls,
            "query_tool_required": bool(args.require_query_tool),
            "query_tool_called": "query_project_knowledge" in knowledge_tool_calls,
            "persist_called": False,
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
