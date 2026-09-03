#!/usr/bin/env python3
"""Safely inspect or remove expired inactive Thread Workspaces."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from runtime_service.services.demo.workspace_demo.policy import (
    cleanup_expired_workspace_threads,
    expired_workspace_threads,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(os.environ.get("GRAPHHARBOR_WORKSPACE_ROOT", "")),
    )
    parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=int(os.environ.get("RUNTIME_WORKSPACE_TTL_SECONDS", "0")),
    )
    parser.add_argument(
        "--active-workspace-id",
        action="append",
        default=[],
        help="Repeat for each active tenant/project/thread path.",
    )
    parser.add_argument(
        "--active-file",
        type=Path,
        help="Newline-separated active tenant/project/thread paths from the Thread store.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete expired inactive workspaces; default is dry-run.",
    )
    args = parser.parse_args()
    active = list(args.active_workspace_id)
    if args.active_file is not None:
        active.extend(
            line.strip()
            for line in args.active_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    if not args.workspace_root.is_absolute() or args.max_age_seconds <= 0:
        parser.error("an absolute --workspace-root and positive --max-age-seconds are required")

    if args.apply:
        removed = cleanup_expired_workspace_threads(
            args.workspace_root,
            active_workspace_ids=active,
            max_age_seconds=args.max_age_seconds,
        )
        print(json.dumps({"mode": "apply", "removed": removed}, ensure_ascii=False))
    else:
        candidates = expired_workspace_threads(
            args.workspace_root,
            active_workspace_ids=active,
            max_age_seconds=args.max_age_seconds,
        )
        base = args.workspace_root.resolve()
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "candidates": [item.relative_to(base).as_posix() for item in candidates],
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
