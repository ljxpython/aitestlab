from __future__ import annotations

import argparse
from uuid import UUID


def parse_uuid_arg(raw: str) -> str:
    text = str(raw).strip()
    if not text:
        raise argparse.ArgumentTypeError("project_id 不能为空")
    try:
        UUID(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "project_id 必须是 UUID，例如 5f419550-a3c7-49c6-9450-09154fd1bf7d"
        ) from exc
    return text


__all__ = ["parse_uuid_arg"]
