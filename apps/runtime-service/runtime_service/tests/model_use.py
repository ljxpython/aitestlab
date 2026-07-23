from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.runtime.modeling import resolve_model_by_id  # noqa: E402


def _build_model() -> Any:
    return resolve_model_by_id("openai_proxy_1").bind(
        temperature=0.2,
        max_tokens=512,
        top_p=0.95,
    )


async def run_iflow_deepseek_v3_case(prompt: str = "请只回复 ok") -> str:
    model = _build_model()
    response = await model.ainvoke([HumanMessage(content=prompt)])
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content
    return str(content)


async def main() -> None:
    output = await run_iflow_deepseek_v3_case(prompt='你是什么模型')
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
