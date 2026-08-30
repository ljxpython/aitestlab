# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import langgraph_sdk

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
from runtime_service.tests.live_args import parse_uuid_arg  # noqa: E402
from runtime_service.tests.services_test_case_service_debug import (  # noqa: E402
    _print_section,
    _resolve_pdf_path,
)

DOCUMENTS_PATH = "/api/test-case-service/documents"
DEFAULT_PLATFORM_API_URL = "http://127.0.0.1:2024"
DEFAULT_DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_GRAPH_ID = "test_case_agent"
DEFAULT_MODEL_ID = "deepseek_chat"
DEFAULT_PLATFORM_API_TOKEN_ENV_KEYS = (
    "PLATFORM_API_TOKEN",
    "PLATFORM_ACCESS_TOKEN",
)


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def _build_langgraph_url(platform_api_url: str) -> str:
    base = _normalize_base_url(platform_api_url)
    return f"{base}/api/langgraph"


def _build_management_assistants_url(platform_api_url: str, project_id: str) -> str:
    base = _normalize_base_url(platform_api_url)
    return f"{base}/_management/projects/{project_id}/assistants"


def _build_langgraph_assistants_search_url(platform_api_url: str) -> str:
    base = _normalize_base_url(platform_api_url)
    return f"{base}/api/langgraph/assistants/search"


def _resolve_platform_token(args: argparse.Namespace) -> str | None:
    raw = str(getattr(args, "platform_token", "") or "").strip()
    if raw:
        return raw
    for key in DEFAULT_PLATFORM_API_TOKEN_ENV_KEYS:
        value = str(os.getenv(key, "") or "").strip()
        if value:
            return value
    return None


def _build_platform_headers(
    args: argparse.Namespace,
    *,
    project_id: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    token = _resolve_platform_token(args)
    if token:
        headers["authorization"] = (
            token if token.lower().startswith("bearer ") else f"Bearer {token}"
        )
    if isinstance(project_id, str) and project_id.strip():
        headers["x-project-id"] = project_id.strip()
    return headers


def _build_interaction_config(args: argparse.Namespace) -> dict[str, Any]:
    configurable: dict[str, Any] = {
        "interaction_data_service_timeout_seconds": args.interaction_timeout,
    }
    if args.interaction_url:
        configurable["interaction_data_service_url"] = args.interaction_url
    if args.interaction_token:
        configurable["interaction_data_service_token"] = args.interaction_token
    return {"configurable": configurable}


def _build_interaction_client(args: argparse.Namespace) -> InteractionDataServiceClient:
    client = InteractionDataServiceClient(
        build_interaction_data_service_config(_build_interaction_config(args))
    )
    if not client.is_configured:
        raise RuntimeError("interaction_data_service_not_configured")
    return client


def _fetch_documents_total(
    *,
    client: InteractionDataServiceClient,
    project_id: str,
) -> int:
    payload = client.get_json(
        DOCUMENTS_PATH,
        params={"project_id": project_id, "limit": 1, "offset": 0},
    )
    return int(payload.get("total") or 0)


def _fetch_batch_documents(
    *,
    client: InteractionDataServiceClient,
    project_id: str,
    batch_id: str,
) -> dict[str, Any]:
    payload = client.get_json(
        DOCUMENTS_PATH,
        params={"project_id": project_id, "batch_id": batch_id, "limit": 20, "offset": 0},
    )
    items = payload.get("items", []) if isinstance(payload.get("items"), list) else []
    return {
        "total": int(payload.get("total") or 0),
        "items": [
            {
                "id": item.get("id"),
                "project_id": item.get("project_id"),
                "batch_id": item.get("batch_id"),
                "filename": item.get("filename"),
                "parse_status": item.get("parse_status"),
                "storage_path": item.get("storage_path"),
            }
            for item in items
            if isinstance(item, dict)
        ],
    }


def _extract_last_ai_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("type") not in {"ai", "assistant"}:
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
    return ""


async def _resolve_assistant_id(args: argparse.Namespace) -> str:
    if isinstance(args.assistant_id, str) and args.assistant_id.strip():
        return args.assistant_id.strip()

    timeout = httpx.Timeout(args.platform_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        management_url = _build_management_assistants_url(
            args.platform_api_url, args.project_id
        )
        headers = _build_platform_headers(args, project_id=args.project_id)
        params = {"graph_id": args.graph_id, "limit": 20, "offset": 0}
        try:
            response = await client.get(management_url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items", []) if isinstance(payload.get("items"), list) else []
            for item in items:
                assistant_id = (
                    item.get("langgraph_assistant_id") if isinstance(item, dict) else None
                )
                if isinstance(assistant_id, str) and assistant_id.strip():
                    return assistant_id.strip()
        except httpx.HTTPError:
            pass

        search_url = _build_langgraph_assistants_search_url(args.platform_api_url)
        response = await client.post(
            search_url,
            headers=headers,
            json={"graph_id": args.graph_id, "limit": 50},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload if isinstance(payload, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("graph_id") or "").strip() != args.graph_id:
                continue
            assistant_id = item.get("assistant_id")
            if isinstance(assistant_id, str) and assistant_id.strip():
                return assistant_id.strip()

    raise RuntimeError(f"assistant_not_found_for_graph:{args.graph_id}")


async def _run_positive_case(
    *,
    args: argparse.Namespace,
    assistant_id: str,
    message: Any,
    interaction_client: InteractionDataServiceClient,
) -> dict[str, Any]:
    batch_id = f"platform-api-project-scope-live:{uuid4()}"
    counts_before = {
        "selected_project_documents": _fetch_documents_total(
            client=interaction_client,
            project_id=args.project_id,
        ),
        "default_project_documents": _fetch_documents_total(
            client=interaction_client,
            project_id=args.default_project_id,
        ),
    }

    client = langgraph_sdk.get_client(
        url=_build_langgraph_url(args.platform_api_url),
        headers=_build_platform_headers(args, project_id=args.project_id),
    )
    thread = await client.threads.create(metadata={"source": "project-scope-live"})
    result = await client.runs.wait(
        thread["thread_id"],
        assistant_id,
        input={"messages": [{"role": "user", "content": message.content}]},
        config={"configurable": {"model_id": args.model_id}},
        metadata={"batch_id": batch_id, "source": "project-scope-live"},
        raise_error=True,
    )

    counts_after = {
        "selected_project_documents": _fetch_documents_total(
            client=interaction_client,
            project_id=args.project_id,
        ),
        "default_project_documents": _fetch_documents_total(
            client=interaction_client,
            project_id=args.default_project_id,
        ),
    }
    selected_batch = _fetch_batch_documents(
        client=interaction_client,
        project_id=args.project_id,
        batch_id=batch_id,
    )
    default_batch = _fetch_batch_documents(
        client=interaction_client,
        project_id=args.default_project_id,
        batch_id=batch_id,
    )

    report = {
        "batch_id": batch_id,
        "thread_id": thread.get("thread_id"),
        "thread_metadata": thread.get("metadata"),
        "assistant_preview": _extract_last_ai_text(result)[:400],
        "counts_before": counts_before,
        "counts_after": counts_after,
        "selected_batch_documents": selected_batch,
        "default_batch_documents": default_batch,
    }

    if not isinstance(thread.get("metadata"), dict) or thread["metadata"].get("project_id") != args.project_id:
        raise AssertionError("thread_project_metadata_missing")
    if counts_after["selected_project_documents"] < counts_before["selected_project_documents"] + 1:
        raise AssertionError("selected_project_document_count_did_not_increase")
    if counts_after["default_project_documents"] != counts_before["default_project_documents"]:
        raise AssertionError("default_project_document_count_changed")
    if selected_batch["total"] <= 0:
        raise AssertionError("selected_project_batch_documents_missing")
    if default_batch["total"] != 0:
        raise AssertionError("default_project_batch_documents_should_be_zero")
    for item in selected_batch["items"]:
        if item.get("project_id") != args.project_id:
            raise AssertionError("selected_project_document_project_id_mismatch")
        if not item.get("storage_path"):
            raise AssertionError("selected_project_document_storage_path_missing")
    return report


async def _run_negative_case(
    *,
    args: argparse.Namespace,
    assistant_id: str,
    message: Any,
    interaction_client: InteractionDataServiceClient,
) -> dict[str, Any]:
    batch_id = f"platform-api-project-scope-negative:{uuid4()}"
    counts_before = {
        "selected_project_documents": _fetch_documents_total(
            client=interaction_client,
            project_id=args.project_id,
        ),
        "default_project_documents": _fetch_documents_total(
            client=interaction_client,
            project_id=args.default_project_id,
        ),
    }

    client = langgraph_sdk.get_client(
        url=_build_langgraph_url(args.platform_api_url),
        headers=_build_platform_headers(args),
    )
    thread = await client.threads.create(metadata={"source": "project-scope-negative"})

    error_summary: dict[str, Any] = {}
    try:
        await client.runs.wait(
            thread["thread_id"],
            assistant_id,
            input={"messages": [{"role": "user", "content": message.content}]},
            config={"configurable": {"model_id": args.model_id}},
            metadata={"batch_id": batch_id, "source": "project-scope-negative"},
            raise_error=True,
        )
    except Exception as exc:
        error_summary = {
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        }
        response = getattr(exc, "response", None)
        if response is not None:
            error_summary["status_code"] = response.status_code
            error_summary["response_text"] = response.text[:1000]
    else:
        raise AssertionError("negative_case_should_fail_without_project_scope")

    counts_after = {
        "selected_project_documents": _fetch_documents_total(
            client=interaction_client,
            project_id=args.project_id,
        ),
        "default_project_documents": _fetch_documents_total(
            client=interaction_client,
            project_id=args.default_project_id,
        ),
    }
    selected_batch = _fetch_batch_documents(
        client=interaction_client,
        project_id=args.project_id,
        batch_id=batch_id,
    )
    default_batch = _fetch_batch_documents(
        client=interaction_client,
        project_id=args.default_project_id,
        batch_id=batch_id,
    )

    report = {
        "batch_id": batch_id,
        "thread_id": thread.get("thread_id"),
        "thread_metadata": thread.get("metadata"),
        "error": error_summary,
        "counts_before": counts_before,
        "counts_after": counts_after,
        "selected_batch_documents": selected_batch,
        "default_batch_documents": default_batch,
    }

    if error_summary.get("status_code") != 400:
        raise AssertionError("negative_case_should_return_http_400")
    if "test_case_project_id_required" not in str(error_summary.get("response_text")):
        raise AssertionError("negative_case_should_expose_project_required_error")
    if counts_after != counts_before:
        raise AssertionError("negative_case_should_not_change_document_counts")
    if selected_batch["total"] != 0 or default_batch["total"] != 0:
        raise AssertionError("negative_case_should_not_persist_documents")
    return report


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate platform-api project scope injection with real PDF/model/input. "
            "This script runs a positive case with x-project-id and a negative case without it."
        )
    )
    parser.add_argument(
        "--project-id",
        required=True,
        type=parse_uuid_arg,
        help="要验证的真实 project_id，必须是 UUID。",
    )
    parser.add_argument(
        "--default-project-id",
        default=DEFAULT_DEFAULT_PROJECT_ID,
        type=parse_uuid_arg,
        help="默认兜底项目 ID，用于确认没有脏写入；必须是 UUID。",
    )
    parser.add_argument(
        "--platform-api-url",
        default=DEFAULT_PLATFORM_API_URL,
        help="platform-api 基地址，默认 http://127.0.0.1:2024 。",
    )
    parser.add_argument(
        "--platform-token",
        default=None,
        help=(
            "platform-api Bearer token；不传则尝试读取环境变量 "
            "PLATFORM_API_TOKEN / PLATFORM_ACCESS_TOKEN。"
        ),
    )
    parser.add_argument(
        "--platform-timeout",
        type=float,
        default=60.0,
        help="platform-api/management 请求超时，单位秒。",
    )
    parser.add_argument(
        "--assistant-id",
        default=None,
        help="显式 assistant_id；不传则按 graph_id 从 platform-api 管理面解析。",
    )
    parser.add_argument(
        "--graph-id",
        default=DEFAULT_GRAPH_ID,
        help="当未显式传 assistant_id 时，用于解析目标 assistant 的 graph_id。",
    )
    parser.add_argument(
        "--pdf",
        help="要上传的 PDF 路径。默认使用 runtime_service/test_data 下第一个 PDF。",
    )
    parser.add_argument(
        "--question",
        default="请基于上传 PDF 给出 1 段简短摘要，不要调用持久化工具。",
        help="发送给 test_case_service 的真实问题。",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="真实运行时模型 ID；默认 deepseek_chat。",
    )
    parser.add_argument(
        "--interaction-url",
        default=None,
        help="显式 interaction-data-service URL；不传则走环境变量或默认配置。",
    )
    parser.add_argument(
        "--interaction-token",
        default=None,
        help="显式 interaction-data-service Bearer Token。",
    )
    parser.add_argument(
        "--interaction-timeout",
        type=int,
        default=60,
        help="interaction-data-service HTTP 超时，单位秒。",
    )
    return parser


async def _main_async(args: argparse.Namespace) -> int:
    pdf_path = _resolve_pdf_path(args.pdf)
    assistant_id = await _resolve_assistant_id(args)
    interaction_client = _build_interaction_client(args)
    message = build_human_message_from_paths(args.question, [pdf_path])

    _print_section(
        "Input",
        {
            "pdf_path": str(pdf_path),
            "project_id": args.project_id,
            "default_project_id": args.default_project_id,
            "platform_api_url": _normalize_base_url(args.platform_api_url),
            "platform_token_configured": bool(_resolve_platform_token(args)),
            "langgraph_url": _build_langgraph_url(args.platform_api_url),
            "assistant_id": assistant_id,
            "graph_id": args.graph_id,
            "model_id": args.model_id,
            "interaction_data_service_url": build_interaction_data_service_config(
                _build_interaction_config(args)
            ).service_url,
        },
    )

    positive_report = await _run_positive_case(
        args=args,
        assistant_id=assistant_id,
        message=message,
        interaction_client=interaction_client,
    )
    _print_section("Positive Case", positive_report)

    negative_report = await _run_negative_case(
        args=args,
        assistant_id=assistant_id,
        message=message,
        interaction_client=interaction_client,
    )
    _print_section("Negative Case", negative_report)

    _print_section(
        "Validation Summary",
        {
            "status": "ok",
            "validated_chain": "platform-api -> runtime-service -> interaction-data-service",
            "positive_batch_id": positive_report["batch_id"],
            "negative_batch_id": negative_report["batch_id"],
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
