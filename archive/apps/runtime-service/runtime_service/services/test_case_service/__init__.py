from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runtime_service.services.test_case_service.graph import graph  # noqa: F401


def __getattr__(name: str) -> object:
    if name == "graph":
        from runtime_service.services.test_case_service.graph import graph

        return graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["graph"]

