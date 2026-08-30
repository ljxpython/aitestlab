from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

filesystem_backend = importlib.import_module(
    "runtime_service.runtime.filesystem_backend"
)


def test_build_filesystem_backend_prepares_root_dir(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class DummyBackend:
        def __init__(self, *, root_dir: str, virtual_mode: bool) -> None:
            captured["root_dir"] = root_dir
            captured["virtual_mode"] = virtual_mode

    target_root = tmp_path / "sync-backend"
    monkeypatch.setattr(filesystem_backend, "FilesystemBackend", DummyBackend)

    backend = filesystem_backend.build_filesystem_backend(
        root_dir=target_root,
        virtual_mode=True,
    )

    assert isinstance(backend, DummyBackend)
    assert target_root.is_dir()
    assert captured == {
        "root_dir": str(target_root),
        "virtual_mode": True,
    }


def test_abuild_filesystem_backend_uses_to_thread(monkeypatch: Any) -> None:
    calls: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    class DummyBackend:
        def __init__(self, *, root_dir: str, virtual_mode: bool) -> None:
            self.root_dir = root_dir
            self.virtual_mode = virtual_mode

    async def fake_to_thread(func: Any, /, *args: Any, **kwargs: Any) -> Any:
        calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(filesystem_backend, "FilesystemBackend", DummyBackend)
    monkeypatch.setattr(filesystem_backend.asyncio, "to_thread", fake_to_thread)

    backend = asyncio.run(
        filesystem_backend.abuild_filesystem_backend(
            root_dir="/tmp/runtime-service-backend",
            virtual_mode=False,
        )
    )

    assert isinstance(backend, DummyBackend)
    assert backend.root_dir == "/tmp/runtime-service-backend"
    assert backend.virtual_mode is False
    assert len(calls) == 2
    assert calls[0][0] is filesystem_backend._prepare_root_dir
    assert calls[0][1] == ("/tmp/runtime-service-backend",)
    assert calls[0][2] == {}
    assert calls[1] == (
        DummyBackend,
        (),
        {
            "root_dir": "/tmp/runtime-service-backend",
            "virtual_mode": False,
        },
    )
