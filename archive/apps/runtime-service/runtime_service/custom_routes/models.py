from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from runtime_service.conf.settings import list_model_catalog

router = APIRouter(prefix="/internal/capabilities", tags=["capabilities"])


@router.get("/models")
def list_models() -> dict[str, Any]:
    models = list_model_catalog()
    return {"count": len(models), "models": models}
