"""Runtime-owned safety and cleanup policy for Thread workspaces."""

from __future__ import annotations

import fcntl
import os
import shutil
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from langgraph_runtime_pg.deepagent_workspace import resolve_workspace_virtual_path


@dataclass(frozen=True, slots=True)
class WorkspaceLimits:
    max_file_bytes: int = 10 * 1024 * 1024
    max_files: int = 10_000
    max_total_bytes: int = 1024 * 1024 * 1024

    @classmethod
    def from_env(cls) -> WorkspaceLimits:
        defaults = cls()
        return cls(
            max_file_bytes=_positive_int(
                "RUNTIME_WORKSPACE_MAX_FILE_BYTES", defaults.max_file_bytes
            ),
            max_files=_positive_int("RUNTIME_WORKSPACE_MAX_FILES", defaults.max_files),
            max_total_bytes=_positive_int(
                "RUNTIME_WORKSPACE_MAX_TOTAL_BYTES", defaults.max_total_bytes
            ),
        )


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def resolve_workspace_path(workspace_root: Path, path: str) -> Path:
    """Resolve a virtual path and reject symlinked paths that escape the root."""

    root = workspace_root.resolve()
    raw_path = str(path).strip()
    current = root
    for component in PurePosixPath(raw_path).parts:
        if component == "/":
            continue
        current /= component
        if current.is_symlink():
            raise ValueError("workspace path must not contain symlinks")
    resolved = resolve_workspace_virtual_path(root, path)
    relative = resolved.relative_to(root)
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            raise ValueError("workspace path must not contain symlinks")
    return resolved


def validate_workspace_write(
    workspace_root: Path,
    path: str,
    content: str,
    *,
    limits: WorkspaceLimits,
) -> Path:
    """Validate one write before handing it to the provider backend."""

    if not isinstance(content, str):
        raise TypeError("workspace content must be text")
    target = resolve_workspace_path(workspace_root, path)
    content_bytes = len(content.encode("utf-8"))
    if content_bytes > limits.max_file_bytes:
        raise ValueError("workspace file exceeds configured limit")
    if not target.exists() and _file_count(workspace_root) >= limits.max_files:
        raise ValueError("workspace file count exceeds configured limit")
    existing_bytes = target.stat().st_size if target.is_file() else 0
    if _total_file_bytes(workspace_root) - existing_bytes + content_bytes > limits.max_total_bytes:
        raise ValueError("workspace total size exceeds configured limit")
    return target


@contextmanager
def workspace_write_lock(workspace_root: Path) -> Iterator[None]:
    """Serialize quota validation and mutation for one shared Thread root."""

    if workspace_root.is_symlink():
        raise ValueError("workspace root must not be a symlink")
    root = workspace_root.resolve()
    if not root.is_dir():
        raise ValueError("workspace root must be a directory")
    lock_path = root.parent / f".{root.name}.runtime.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _file_count(root: Path) -> int:
    # ponytail: bounded provider-backed workspaces can use an O(n) scan; replace
    # with provider quota accounting when the workspace owner exposes it.
    return sum(1 for item in root.rglob("*") if item.is_file() and not item.is_symlink())


def _total_file_bytes(root: Path) -> int:
    return sum(
        item.stat().st_size
        for item in root.rglob("*")
        if item.is_file() and not item.is_symlink()
    )


def expired_workspace_threads(
    base_dir: Path,
    *,
    active_workspace_ids: Iterable[str] = (),
    max_age_seconds: int,
    now: float | None = None,
) -> list[Path]:
    """Return inactive `<tenant>/<project>/<thread>` roots older than the TTL."""

    if not base_dir.is_absolute() or max_age_seconds <= 0:
        raise ValueError("workspace cleanup requires an absolute root and positive TTL")
    base = base_dir.resolve()
    active = {str(item).strip("/") for item in active_workspace_ids if str(item).strip("/")}
    timestamp = time.time() if now is None else now
    expired: list[Path] = []
    for tenant in _directories(base):
        for project in _directories(tenant):
            for thread in _directories(project):
                workspace_id = thread.relative_to(base).as_posix()
                if workspace_id in active or thread.is_symlink():
                    continue
                try:
                    age = timestamp - thread.stat().st_mtime
                except OSError:
                    continue
                if age > max_age_seconds:
                    expired.append(thread)
    return expired


def cleanup_expired_workspace_threads(
    base_dir: Path,
    *,
    active_workspace_ids: Iterable[str] = (),
    max_age_seconds: int,
    now: float | None = None,
) -> list[str]:
    """Delete only inactive, expired Thread roots and return relative IDs."""

    base = base_dir.resolve()
    expired = expired_workspace_threads(
        base,
        active_workspace_ids=active_workspace_ids,
        max_age_seconds=max_age_seconds,
        now=now,
    )
    active = {str(item).strip("/") for item in active_workspace_ids if str(item).strip("/")}
    timestamp = time.time() if now is None else now
    removed: list[str] = []
    for thread in expired:
        try:
            with workspace_write_lock(thread):
                workspace_id = thread.relative_to(base).as_posix()
                if workspace_id in active or not thread.is_dir() or thread.is_symlink():
                    continue
                if timestamp - thread.stat().st_mtime <= max_age_seconds:
                    continue
                shutil.rmtree(thread)
                removed.append(workspace_id)
        except FileNotFoundError:
            continue
    return removed


def _directories(root: Path) -> list[Path]:
    try:
        return [item for item in root.iterdir() if item.is_dir() and not item.is_symlink()]
    except OSError:
        return []


__all__ = [
    "WorkspaceLimits",
    "cleanup_expired_workspace_threads",
    "expired_workspace_threads",
    "resolve_workspace_path",
    "validate_workspace_write",
    "workspace_write_lock",
]
