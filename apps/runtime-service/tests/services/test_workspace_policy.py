from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from runtime_service.services.workspace_policy import (
    WorkspaceLimits,
    cleanup_expired_workspace_threads,
    resolve_workspace_path,
    validate_workspace_write,
    workspace_write_lock,
)


def test_workspace_policy_rejects_oversized_files_and_file_quota(tmp_path: Path) -> None:
    root = tmp_path / "tenant" / "project" / "thread"
    root.mkdir(parents=True)
    with pytest.raises(ValueError, match="file exceeds"):
        validate_workspace_write(
            root,
            "/large.txt",
            "12345",
            limits=WorkspaceLimits(max_file_bytes=4, max_files=10),
        )


def test_workspace_policy_rejects_total_workspace_quota(tmp_path: Path) -> None:
    root = tmp_path / "tenant" / "project" / "thread"
    root.mkdir(parents=True)
    (root / "existing.txt").write_text("1234", encoding="utf-8")
    with pytest.raises(ValueError, match="total size"):
        validate_workspace_write(
            root,
            "/new.txt",
            "x",
            limits=WorkspaceLimits(max_file_bytes=10, max_files=10, max_total_bytes=4),
        )

    with pytest.raises(ValueError, match="total size"):
        validate_workspace_write(
            root,
            "/existing.txt",
            "12345",
            limits=WorkspaceLimits(max_file_bytes=10, max_files=10, max_total_bytes=4),
        )

    (root / "existing.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="file count"):
        validate_workspace_write(
            root,
            "/second.txt",
            "x",
            limits=WorkspaceLimits(max_file_bytes=4, max_files=1),
        )


def test_workspace_policy_rejects_symlinked_path(tmp_path: Path) -> None:
    root = tmp_path / "thread"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        resolve_workspace_path(root, "/linked/file.txt")


def test_cleanup_removes_only_expired_inactive_threads(tmp_path: Path) -> None:
    base = tmp_path / "workspaces"
    old = base / "tenant" / "project" / "old-thread"
    active = base / "tenant" / "project" / "active-thread"
    fresh = base / "tenant" / "project" / "fresh-thread"
    for root in (old, active, fresh):
        root.mkdir(parents=True)
    old_timestamp = 100.0
    os.utime(old, (old_timestamp, old_timestamp))
    os.utime(active, (old_timestamp, old_timestamp))

    removed = cleanup_expired_workspace_threads(
        base,
        active_workspace_ids=["tenant/project/active-thread"],
        max_age_seconds=10,
        now=200.0,
    )
    assert removed == ["tenant/project/old-thread"]
    assert not old.exists()
    assert active.exists()
    assert fresh.exists()


def test_workspace_write_lock_makes_quota_check_atomic(tmp_path: Path) -> None:
    root = tmp_path / "tenant" / "project" / "thread"
    root.mkdir(parents=True)
    limits = WorkspaceLimits(max_file_bytes=4, max_files=10, max_total_bytes=4)

    def write(path: str) -> str:
        try:
            with workspace_write_lock(root):
                target = validate_workspace_write(
                    root, path, "1234", limits=limits
                )
                target.write_text("1234", encoding="utf-8")
            return "written"
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("/one.txt", "/two.txt")))

    assert sorted(results) == ["rejected", "written"]
    assert (root / "one.txt").exists() ^ (root / "two.txt").exists()


def test_workspace_write_lock_rejects_symlink_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        with workspace_write_lock(linked_root):
            pass
