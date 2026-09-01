"""Fail-closed validation for the Spike graph configuration."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import sys
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph
from langgraph.pregel import Pregel


def _load_export(config_path: Path, graph_id: str, graph_path: str) -> Any:
    if ":" not in graph_path:
        raise ValueError(f"{graph_id}: invalid graph path {graph_path!r}")
    file_name, export_name = graph_path.split(":", 1)
    file_path = Path(file_name)
    if not file_path.is_absolute():
        file_path = (config_path.parent / file_path).resolve()
    if not file_path.exists():
        raise ValueError(f"{graph_id}: graph file not found: {file_path}")

    module_name = f"aegra_spike_validation_{graph_id.replace('.', '_').replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"{graph_id}: cannot import {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    if not hasattr(module, export_name):
        raise ValueError(f"{graph_id}: export {export_name!r} not found in {file_path}")
    return getattr(module, export_name)


async def _resolve_zero_arg(value: Any) -> Any:
    if inspect.isawaitable(value):
        value = await value
    if hasattr(value, "__aenter__") and hasattr(value, "__aexit__"):
        async with value as resolved:
            return resolved
    if hasattr(value, "__enter__") and hasattr(value, "__exit__"):
        with value as resolved:
            return resolved
    return value


def validate(config_path: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    graphs = config.get("graphs")
    if not isinstance(graphs, dict) or not graphs:
        raise ValueError("configuration must contain a non-empty 'graphs' object")

    for graph_id, graph_path in graphs.items():
        exported = _load_export(config_path, str(graph_id), str(graph_path))
        if not callable(exported):
            if not isinstance(exported, (Pregel, StateGraph)):
                raise TypeError(
                    f"{graph_id}: export must be Pregel, StateGraph, or a callable factory; "
                    f"got {type(exported).__name__}"
                )
            continue

        parameters = list(inspect.signature(exported).parameters.values())
        if len(parameters) > 2:
            raise TypeError(
                f"{graph_id}: factory supports at most 2 parameters; got {len(parameters)}"
            )
        if len(parameters) == 0:
            resolved = asyncio.run(_resolve_zero_arg(exported()))
            if not isinstance(resolved, (Pregel, StateGraph)):
                raise TypeError(
                    f"{graph_id}: zero-argument factory returned {type(resolved).__name__}, "
                    "expected Pregel or StateGraph"
                )


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "aegra.json").resolve()
    try:
        validate(path)
    except Exception as exc:
        print(f"Graph configuration rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"Graph configuration valid: {path}")
