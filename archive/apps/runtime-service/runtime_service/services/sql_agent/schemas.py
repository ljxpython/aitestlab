from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CHINOOK_DB_URL = "https://storage.googleapis.com/benchmarks-artifacts/chinook/Chinook.db"
CHINOOK_DB_FILENAME = "Chinook.db"
DEFAULT_DATABASE_NAME = "Chinook"
DEFAULT_TOP_K = 5
DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SQLAgentServiceConfig:
    top_k: int = DEFAULT_TOP_K


def get_service_root() -> Path:
    return Path(__file__).resolve().parent


def get_cache_dir() -> Path:
    return get_service_root() / ".cache"


def get_default_db_path() -> Path:
    return get_cache_dir() / CHINOOK_DB_FILENAME
