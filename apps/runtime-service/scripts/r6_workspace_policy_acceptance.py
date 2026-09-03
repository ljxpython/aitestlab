"""Exercise Workspace quota atomicity and inactive-thread cleanup in subprocesses."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from runtime_service.services.demo.workspace_demo.policy import (
    WorkspaceLimits,
    cleanup_expired_workspace_threads,
    expired_workspace_threads,
    validate_workspace_write,
    workspace_write_lock,
)


def _attempt_write(root_value: str, name: str) -> str:
    root = Path(root_value)
    try:
        with workspace_write_lock(root):
            target = validate_workspace_write(
                root,
                f"/{name}.txt",
                "1234",
                limits=WorkspaceLimits(
                    max_file_bytes=4, max_files=2, max_total_bytes=4
                ),
            )
            target.write_text("1234", encoding="utf-8")
        return "written"
    except ValueError:
        return "rejected"


def _run(root: Path) -> dict[str, object]:
    root = root.resolve()
    quota_root = root / "quota" / "project" / "thread"
    quota_root.mkdir(parents=True)
    with ProcessPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                _attempt_write,
                [str(quota_root), str(quota_root)],
                ["one", "two"],
            )
        )

    old = root / "tenant" / "project" / "old-thread"
    active = root / "tenant" / "project" / "active-thread"
    fresh = root / "tenant" / "project" / "fresh-thread"
    for item in (old, active, fresh):
        item.mkdir(parents=True)
    os.utime(old, (100.0, 100.0))
    os.utime(active, (100.0, 100.0))
    os.utime(fresh, (195.0, 195.0))
    active_id = "tenant/project/active-thread"
    candidates = expired_workspace_threads(
        root, active_workspace_ids=[active_id], max_age_seconds=10, now=200.0
    )
    removed = cleanup_expired_workspace_threads(
        root, active_workspace_ids=[active_id], max_age_seconds=10, now=200.0
    )
    return {
        "status": "passed"
        if sorted(results) == ["rejected", "written"]
        and [item.relative_to(root).as_posix() for item in candidates]
        == ["tenant/project/old-thread"]
        and removed == ["tenant/project/old-thread"]
        and active.is_dir()
        and fresh.is_dir()
        else "failed",
        "quota_results": sorted(results),
        "cleanup_candidates": [item.relative_to(root).as_posix() for item in candidates],
        "removed": removed,
        "active_preserved": active.is_dir(),
        "fresh_preserved": fresh.is_dir(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path)
    args = parser.parse_args()
    if args.workspace_root is None:
        with tempfile.TemporaryDirectory(prefix="r6-workspace-policy-") as value:
            result = _run(Path(value))
    else:
        root = args.workspace_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        result = _run(root)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
