from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from runtime_service.tools.registry import get_tool_catalog

# ==================== 内部能力接口 ====================
# 向前端/调用方暴露统一工具池：
# - GET /tools：查询可选工具清单
router = APIRouter(prefix="/internal/capabilities", tags=["capabilities"])


@router.get("/tools")
def list_tools() -> dict[str, Any]:
    # 固定排序，保证前端展示顺序稳定。
    tools = sorted(get_tool_catalog().values(), key=lambda item: item["name"])
    return {"count": len(tools), "tools": tools}
