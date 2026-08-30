from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_community.utilities import SQLDatabase

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.runtime.runtime_request_resolver import (  # noqa: E402
    ResolvedRuntimeSettings,
)
from runtime_service.services.sql_agent import tools as sql_tools  # noqa: E402

sql_agent_graph = importlib.import_module("runtime_service.services.sql_agent.graph")


def test_sql_agent_defaults_to_empty_system_prompt() -> None:
    assert sql_agent_graph.SQL_AGENT_DEFAULTS.system_prompt == ""


def _invoke_tool(tool_obj: Any, args: dict[str, Any]) -> Any:
    return getattr(tool_obj, "invoke")(args)


def _create_sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(db_path)
    conn.execute("create table artist(id integer primary key, name text)")
    conn.execute("insert into artist(name) values ('Miles Davis')")
    conn.commit()
    conn.close()
    return db_path


def test_validate_read_only_sql_accepts_select_variants() -> None:
    assert sql_tools.validate_read_only_sql("SELECT * FROM artist LIMIT 5") is None
    assert (
        sql_tools.validate_read_only_sql(
            "WITH ranked AS (SELECT * FROM artist) SELECT * FROM ranked LIMIT 1"
        )
        is None
    )


def test_validate_read_only_sql_rejects_write_and_multi_statement() -> None:
    assert sql_tools.validate_read_only_sql("DELETE FROM artist") is not None
    assert (
        sql_tools.validate_read_only_sql("SELECT * FROM artist; DELETE FROM artist")
        is not None
    )


def test_sqlite_readonly_uri_blocks_writes(tmp_path: Path) -> None:
    db_path = _create_sqlite_db(tmp_path)
    db = SQLDatabase.from_uri(sql_tools._build_sqlite_readonly_uri(db_path))

    assert db.run("SELECT name FROM artist") == "[('Miles Davis',)]"
    error = db.run_no_throw("INSERT INTO artist(name) VALUES ('John Coltrane')")
    assert "readonly" in str(error).lower()


def test_build_sql_database_tools_wraps_query_tool(tmp_path: Path) -> None:
    db_path = _create_sqlite_db(tmp_path)
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    model = FakeListChatModel(responses=["SELECT * FROM artist LIMIT 5"])

    tools = sql_tools.build_sql_database_tools(model, db)
    names = [getattr(tool, "name", "") for tool in tools]
    assert names == [
        "sql_db_query",
        "sql_db_schema",
        "sql_db_list_tables",
        "sql_db_query_checker",
    ]
    assert isinstance(tools[0], sql_tools.ReadOnlyQuerySQLDatabaseTool)

    rows = _invoke_tool(tools[0], {"query": "SELECT name FROM artist LIMIT 1"})
    blocked = _invoke_tool(tools[0], {"query": "DROP TABLE artist"})

    assert "Miles Davis" in str(rows)
    assert blocked == "Only read-only SELECT queries are allowed in sql_agent."


def test_build_lazy_chinook_database_defers_download_until_first_use(
    monkeypatch: Any, tmp_path: Path
) -> None:
    called = {"value": False}

    def fake_download() -> Path:
        called["value"] = True
        return _create_sqlite_db(tmp_path)

    monkeypatch.setattr(sql_tools, "download_chinook_database", fake_download)
    lazy_db = sql_tools.build_lazy_chinook_database()

    assert called["value"] is False
    assert list(lazy_db.get_usable_table_names()) == ["artist"]
    assert called["value"] is True


def test_build_sql_agent_service_config_reads_private_flags() -> None:
    config = {"configurable": {"sql_agent_top_k": "9"}}

    service_config = sql_tools.build_sql_agent_service_config(config)
    assert service_config.top_k == 9


def test_sql_graph_resolve_required_tools_includes_chart_tools(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        sql_agent_graph,
        "build_sql_agent_tools",
        lambda model, config=None: ["sql_tool", model],
    )
    monkeypatch.setattr(sql_agent_graph, "_get_chart_tools", lambda: ["chart_tool"])

    settings = ResolvedRuntimeSettings(
        context=RuntimeContext(),
        model="runtime-model",
        system_prompt="",
        enable_tools=False,
        requested_public_tool_names=[],
    )

    resolved_tools = sql_agent_graph._resolve_required_tools(settings)

    assert resolved_tools == ["sql_tool", "runtime-model", "chart_tool"]


def test_sql_graph_build_sql_system_prompt_uses_runtime_prompt(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_build_sql_agent_system_prompt(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "sql system prompt"

    monkeypatch.setattr(
        sql_agent_graph,
        "build_sql_agent_system_prompt",
        fake_build_sql_agent_system_prompt,
    )

    settings = ResolvedRuntimeSettings(
        context=RuntimeContext(),
        model="runtime-model",
        system_prompt="custom runtime prompt",
        enable_tools=False,
        requested_public_tool_names=[],
    )

    prompt = sql_agent_graph._build_sql_system_prompt(settings)

    assert prompt == "sql system prompt"
    assert captured["custom_instructions"] == "custom runtime prompt"


def test_sql_graph_exports_static_graph_symbol() -> None:
    assert hasattr(sql_agent_graph, "graph")
    assert not hasattr(sql_agent_graph, "make_graph")
    assert hasattr(sql_agent_graph.graph, "invoke")


def test_langgraph_registers_sql_agent() -> None:
    langgraph_file = _PROJECT_ROOT / "runtime_service" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "sql_agent" in data["graphs"]
