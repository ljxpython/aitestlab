from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.conf.settings import (  # noqa: E402
    get_default_model_id,
    require_model_spec,
)
from runtime_service.runtime.modeling import resolve_model_by_id  # noqa: E402


def _maybe_load_local_env() -> None:
    """在本地单测时自动加载 `runtime_service/.env`（不覆盖已存在环境变量）。"""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _has_any_model_key() -> bool:
    return bool(
        os.getenv("MODEL_API_KEY")
        or os.getenv("MASS_KIMI_KEY")
        or os.getenv("GLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("KIMI_API_KEY")
    )


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:3] + "***" + value[-3:]


def test_model_smoke_ok() -> None:
    """模型连通性/鉴权烟囱测试。

    - 默认走 `resolve_model_by_id(model_id)`。
    - provider/model/base_url/api_key 来自 settings.yaml 的 model_id 映射。
    - 无可用 key 时自动 skip，避免 CI/无网环境失败。
    """

    _maybe_load_local_env()
    model_id = (os.getenv("MODEL_ID") or "").strip() or get_default_model_id()
    spec: dict[str, str] = {}
    try:
        _, spec = require_model_spec(model_id)
    except ValueError as exc:
        pytest.skip(f"Model group for '{model_id}' is not ready: {exc}")
        return

    provider = spec["model_provider"]
    model_name = spec["model"]
    base_url = spec["base_url"]
    api_key = spec["api_key"]

    if not _has_any_model_key() and not api_key:
        pytest.skip("No model API key configured in env")
    timeout_secs = float(os.getenv("MODEL_SMOKE_TIMEOUT_SECS", "20"))

    model = resolve_model_by_id(model_id)

    async def _run() -> str:
        resp = await asyncio.wait_for(
            model.ainvoke([HumanMessage(content="请只回复 ok")]),
            timeout=timeout_secs,
        )
        return getattr(resp, "content", "") or ""

    try:
        content = asyncio.run(_run())
    except TimeoutError as e:
        pytest.fail(
            "模型调用超时。\n"
            f"- model_id={model_id}\n"
            f"- provider={provider}\n"
            f"- model={model_name}\n"
            f"- base_url={base_url}\n"
            f"- api_key={_mask(api_key)}\n"
            f"- timeout_secs={timeout_secs}\n"
            "\n建议：先用 `uv run pytest runtime_service/tests/test_model_smoke.py -q` 直跑看具体报错；"
            "或调大超时：`MODEL_SMOKE_TIMEOUT_SECS=60`。\n"
        )
        raise e
    assert isinstance(content, str)
    assert content.strip(), "Model returned empty content"
