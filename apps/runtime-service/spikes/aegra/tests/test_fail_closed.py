from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import _doubao_multimodal_model
from validate_config import validate


def _config(tmp_path: Path, export: str) -> Path:
    (tmp_path / "graphs.py").write_text(
        "from langgraph.graph import StateGraph\n"
        "from langgraph.pregel import Pregel\n"
        "valid = object()\n"
        "def too_many(a, b, c): return valid\n",
        encoding="utf-8",
    )
    path = tmp_path / "aegra.json"
    path.write_text(json.dumps({"graphs": {"probe": f"./graphs.py:{export}"}}), encoding="utf-8")
    return path


def test_missing_export_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="export .* not found"):
        validate(_config(tmp_path, "missing"))


def test_unsupported_factory_signature_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="at most 2 parameters"):
        validate(_config(tmp_path, "too_many"))


def test_non_graph_export_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="must be Pregel"):
        validate(_config(tmp_path, "valid"))


def test_missing_multimodal_model_settings_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("DOUBAO_API_BASE", "DOUBAO_API_KEY", "DOUBAO_MODEL"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="Doubao settings are required"):
        _doubao_multimodal_model()
