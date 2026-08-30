from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Literal, cast

import requests
from runtime_service.runtime.config_utils import read_configurable
from runtime_service.services.sql_agent.schemas import (
    CHINOOK_DB_URL,
    DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
    DEFAULT_TOP_K,
    SQLAgentServiceConfig,
    get_default_db_path,
)
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langchain_community.utilities import SQLDatabase
from langchain_core.callbacks import CallbackManagerForToolRun

_READ_ONLY_SQL_ERROR = "Only read-only SELECT queries are allowed in sql_agent."
_LEADING_COMMENT_PATTERN = re.compile(r"\A(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/)+", re.DOTALL)
_FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|attach|detach|pragma|"
    r"vacuum|begin|commit|rollback|savepoint|release|merge|upsert)\b",
    re.IGNORECASE,
)
def _parse_int(value: Any, default: int = DEFAULT_TOP_K) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def build_sql_agent_service_config(config: Any | None) -> SQLAgentServiceConfig:
    configurable = read_configurable(config)
    top_k = _parse_int(
        configurable.get("sql_agent_top_k")
        if "sql_agent_top_k" in configurable
        else os.getenv("SQL_AGENT_TOP_K"),
        default=DEFAULT_TOP_K,
    )
    return SQLAgentServiceConfig(top_k=top_k)


def _normalize_sql(query: str) -> str:
    normalized = query.strip()
    while True:
        updated = _LEADING_COMMENT_PATTERN.sub("", normalized, count=1).lstrip()
        if updated == normalized:
            return normalized
        normalized = updated


def validate_read_only_sql(query: str) -> str | None:
    normalized = _normalize_sql(query)
    if not normalized:
        return _READ_ONLY_SQL_ERROR

    body = normalized.rstrip().rstrip(";").strip()
    if not body:
        return _READ_ONLY_SQL_ERROR
    if ";" in body:
        return _READ_ONLY_SQL_ERROR
    if _FORBIDDEN_SQL_PATTERN.search(body):
        return _READ_ONLY_SQL_ERROR

    lowered = body.lower()
    if lowered.startswith("select"):
        return None
    if lowered.startswith("with") and "select" in lowered:
        return None
    return _READ_ONLY_SQL_ERROR


def _build_sqlite_readonly_uri(path: Path) -> str:
    return f"sqlite:///file:{path.resolve()}?mode=ro&uri=true"


def download_chinook_database(
    *,
    url: str = CHINOOK_DB_URL,
    destination: Path | None = None,
    timeout: int = DEFAULT_DOWNLOAD_TIMEOUT_SECONDS,
) -> Path:
    db_path = destination or get_default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        return db_path

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    db_path.write_bytes(response.content)
    return db_path


class LazySQLDatabase(SQLDatabase):
    def __init__(self, db_factory: Callable[[], SQLDatabase]) -> None:
        self._db_factory = db_factory
        self._db_instance: SQLDatabase | None = None

    def _db(self) -> SQLDatabase:
        if self._db_instance is None:
            self._db_instance = self._db_factory()
        return self._db_instance

    @property
    def dialect(self) -> str:
        return self._db().dialect

    def get_usable_table_names(self) -> Iterable[str]:
        return self._db().get_usable_table_names()

    def get_table_info_no_throw(self, table_names: list[str] | None = None) -> str:
        return self._db().get_table_info_no_throw(table_names)

    def run_no_throw(
        self,
        command: str,
        fetch: Literal["all", "one"] = "all",
        include_columns: bool = False,
        *,
        parameters: dict[str, Any] | None = None,
        execution_options: dict[str, Any] | None = None,
    ) -> Any:
        return self._db().run_no_throw(
            command,
            fetch=cast(Literal["all", "one"], fetch),
            include_columns=include_columns,
            parameters=parameters,
            execution_options=execution_options,
        )


class ReadOnlyQuerySQLDatabaseTool(QuerySQLDatabaseTool):
    def _run(
        self,
        query: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> Any:
        del run_manager
        error = validate_read_only_sql(query)
        if error is not None:
            return error
        return super()._run(query)


def build_lazy_chinook_database() -> SQLDatabase:
    def _factory() -> SQLDatabase:
        db_path = download_chinook_database()
        return SQLDatabase.from_uri(_build_sqlite_readonly_uri(db_path))

    return LazySQLDatabase(_factory)


def build_sql_database_tools(model: Any, db: SQLDatabase) -> list[Any]:
    toolkit = SQLDatabaseToolkit(db=db, llm=model)
    tools: list[Any] = []
    for tool in toolkit.get_tools():
        if getattr(tool, "name", "") != "sql_db_query":
            tools.append(tool)
            continue
        tools.append(
            ReadOnlyQuerySQLDatabaseTool(
                db=db,
                name=str(getattr(tool, "name", "sql_db_query")),
                description=str(getattr(tool, "description", "") or ""),
            )
        )
    return tools


def build_sql_agent_tools(model: Any, *, config: Any | None = None) -> list[Any]:
    del config
    tools = build_sql_database_tools(model, build_lazy_chinook_database())
    return tools


async def abuild_sql_agent_tools(model: Any, *, config: Any | None = None) -> list[Any]:
    return build_sql_agent_tools(model, config=config)


__all__ = [
    "LazySQLDatabase",
    "ReadOnlyQuerySQLDatabaseTool",
    "SQLAgentServiceConfig",
    "build_lazy_chinook_database",
    "build_sql_agent_service_config",
    "build_sql_agent_tools",
    "abuild_sql_agent_tools",
    "build_sql_database_tools",
    "download_chinook_database",
    "validate_read_only_sql",
]
