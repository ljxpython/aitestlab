from __future__ import annotations

import asyncio
from pathlib import Path

from deepagents.backends import FilesystemBackend


def _prepare_root_dir(root_dir: str | Path) -> str:
    path = Path(root_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def build_filesystem_backend(
    *, root_dir: str | Path, virtual_mode: bool
) -> FilesystemBackend:
    return FilesystemBackend(
        root_dir=_prepare_root_dir(root_dir),
        virtual_mode=virtual_mode,
    )


async def abuild_filesystem_backend(
    *, root_dir: str | Path, virtual_mode: bool
) -> FilesystemBackend:
    """Construct FilesystemBackend without blocking the event loop."""

    prepared_root_dir = await asyncio.to_thread(_prepare_root_dir, root_dir)
    return await asyncio.to_thread(
        FilesystemBackend,
        root_dir=prepared_root_dir,
        virtual_mode=virtual_mode,
    )
