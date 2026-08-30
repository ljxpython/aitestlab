# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import argparse
import json
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

from runtime_service.integrations import (  # noqa: E402
    InteractionDataServiceClient,
    build_interaction_data_service_config,
)
from runtime_service.services.test_case_service.schemas import (  # noqa: E402
    PersistTestCaseItem,
)
from runtime_service.services.test_case_service.tools import (  # noqa: E402
    TEST_CASES_PATH,
    _build_test_case_payloads,
)
from runtime_service.tests.live_args import parse_uuid_arg  # noqa: E402


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _print_section(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    print(_json_dump(payload))


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate testcase idempotent persistence with the real interaction-data-service."
    )
    parser.add_argument(
        "--project-id",
        required=True,
        type=parse_uuid_arg,
        help="显式 project_id；必须是 UUID，真实链路验证不再允许 default project fallback。",
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="显式 batch_id；不传则自动生成。",
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


def _build_payloads(
    *,
    project_id: str,
    batch_id: str,
    version: int,
) -> list[dict[str, Any]]:
    bundle_title = "接口文档测试用例"
    bundle_summary = f"基于接口文档构造的第 {version} 版正式测试用例"
    runtime_meta = {
        "thread_id": f"case-idempotency-thread-v{version}",
        "run_id": f"case-idempotency-run-v{version}",
        "agent_key": "test_case_service",
    }
    quality_review = {
        "score": 0.9 + (version * 0.01),
        "summary": f"第 {version} 次写入用于验证 testcase 覆盖更新。",
    }

    cases = [
        PersistTestCaseItem(
            case_id="TC-API-001",
            title="接口鉴权成功",
            description=f"第 {version} 次保存：验证合法 token 可成功访问接口。",
            status="active",
            module_name="开放平台接口",
            priority="P0",
            test_type="functional",
            design_technique="equivalence",
            preconditions=["准备有效 token"],
            steps=[f"第 {version} 次：携带合法 token 调用接口"],
            expected_results=[f"第 {version} 次：返回 200 和正确业务数据"],
            remarks=f"version={version}",
            content_json={"origin": "接口文档", "version": version},
        ),
        PersistTestCaseItem(
            title="接口鉴权失败",
            description=f"第 {version} 次保存：验证无效 token 被拒绝。",
            status="draft" if version == 1 else "active",
            module_name="开放平台接口",
            priority="P1",
            test_type="functional",
            design_technique="negative",
            preconditions=["准备无效 token"],
            steps=[f"第 {version} 次：携带无效 token 调用接口"],
            expected_results=[f"第 {version} 次：返回 401 或明确错误码"],
            remarks=f"version={version}",
            content_json={"origin": "接口文档", "version": version},
        ),
    ]

    return _build_test_case_payloads(
        items=cases,
        project_id=project_id,
        batch_id=batch_id,
        source_document_ids=[],
        bundle_title=bundle_title,
        bundle_summary=bundle_summary,
        quality_review=quality_review,
        export_format="json",
        runtime_meta=runtime_meta,
    )


def _post_cases(
    *,
    client: InteractionDataServiceClient,
    payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [client.post_json(TEST_CASES_PATH, payload) for payload in payloads]


def _fetch_cases(
    *,
    client: InteractionDataServiceClient,
    project_id: str,
    batch_id: str,
) -> dict[str, Any]:
    return client.get_json(
        TEST_CASES_PATH,
        params={"project_id": project_id, "batch_id": batch_id, "limit": 50},
    )


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = _build_arg_parser().parse_args(argv)
    project_id = args.project_id
    batch_id = args.batch_id or f"test-case-service-case-idempotency:{uuid4()}"
    config: RunnableConfig = {
        "configurable": {
            "project_id": project_id,
            "interaction_data_service_timeout_seconds": args.interaction_timeout,
        }
    }
    if args.interaction_url:
        config["configurable"]["interaction_data_service_url"] = args.interaction_url

    client = InteractionDataServiceClient(build_interaction_data_service_config(config))
    if not client.is_configured:
        print("interaction_data_service_not_configured", file=sys.stderr)
        return 1

    payloads_v1 = _build_payloads(project_id=project_id, batch_id=batch_id, version=1)
    created_v1 = _post_cases(client=client, payloads=payloads_v1)
    listing_v1 = _fetch_cases(client=client, project_id=project_id, batch_id=batch_id)

    payloads_v2 = _build_payloads(project_id=project_id, batch_id=batch_id, version=2)
    created_v2 = _post_cases(client=client, payloads=payloads_v2)
    listing_v2 = _fetch_cases(client=client, project_id=project_id, batch_id=batch_id)

    _print_section(
        "Input",
        {
            "project_id": project_id,
            "batch_id": batch_id,
            "interaction_data_service_url": build_interaction_data_service_config(config).service_url,
        },
    )
    _print_section("Created V1", created_v1)
    _print_section("Listing V1", listing_v1)
    _print_section("Created V2", created_v2)
    _print_section("Listing V2", listing_v2)

    items_v2 = listing_v2.get("items", []) if isinstance(listing_v2.get("items"), list) else []
    total_v2 = int(listing_v2.get("total") or 0)
    if total_v2 != 2:
        print(f"期望 testcase 总数为 2，实际为 {total_v2}", file=sys.stderr)
        return 1

    id_map_v1 = {str(item.get("idempotency_key")): str(item.get("id")) for item in created_v1}
    id_map_v2 = {str(item.get("idempotency_key")): str(item.get("id")) for item in created_v2}
    if id_map_v1 != id_map_v2:
        print("两次写入命中的 testcase 记录不一致，幂等覆盖失败", file=sys.stderr)
        return 1

    by_key_v2 = {
        str(item.get("idempotency_key")): item
        for item in items_v2
        if isinstance(item, dict)
    }
    for payload in payloads_v2:
        key = str(payload.get("idempotency_key"))
        row = by_key_v2.get(key)
        if row is None:
            print(f"缺少幂等 key 对应记录: {key}", file=sys.stderr)
            return 1
        if row.get("description") != payload.get("description"):
            print(f"记录未被最新内容覆盖: {key}", file=sys.stderr)
            return 1

    print("\ncase idempotency live validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
