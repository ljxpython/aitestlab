"""Fail-fast validation for the Runtime deployment env contract."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values


REQUIRED = (
    "PLATFORM_RUNTIME_DELEGATION_SECRET",
    "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET",
    "PLATFORM_RUNTIME_DELEGATION_ISSUER",
    "PLATFORM_RUNTIME_DELEGATION_AUDIENCE",
    "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER",
    "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE",
    "GRAPHHARBOR_WORKSPACE_ROOT",
    "DEEPSEEK_PROXY_URL",
    "DEEPSEEK_PROXY_API_KEY",
    "DEEPSEEK_PROXY_DEFAULT_MODEL",
)
NUMERIC = (
    "RUNTIME_WORKSPACE_MAX_FILE_BYTES",
    "RUNTIME_WORKSPACE_MAX_FILES",
    "RUNTIME_WORKSPACE_MAX_TOTAL_BYTES",
    "RUNTIME_WORKSPACE_TTL_SECONDS",
    "GRAPHHARBOR_RUN_TIMEOUT_SECONDS",
)
URLS = ("DEEPSEEK_PROXY_URL", "GPT_PROXY_URL", "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER")


def _settings(path: Path) -> dict[str, str]:
    file_values = {
        key: str(value)
        for key, value in dotenv_values(path).items()
        if value is not None
    }
    return {**file_values, **os.environ}


def _present(settings: dict[str, str], key: str) -> bool:
    return bool(settings.get(key, "").strip())


def validate(path: Path) -> list[str]:
    if not path.is_file():
        return [f"deployment env file is missing: {path}"]

    settings = _settings(path)
    errors = [f"{key} is empty" for key in REQUIRED if not _present(settings, key)]
    for key in NUMERIC:
        if not _present(settings, key):
            errors.append(f"{key} is empty")
            continue
        try:
            value = int(settings[key])
        except ValueError:
            errors.append(f"{key} must be an integer")
            continue
        if value <= 0:
            errors.append(f"{key} must be greater than zero")

    for key in URLS:
        value = settings.get(key, "").strip()
        if value and urlparse(value).scheme not in {"http", "https"}:
            errors.append(f"{key} must use http or https")

    for key in ("PLATFORM_RUNTIME_DELEGATION_SECRET", "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET"):
        if _present(settings, key) and len(settings[key].strip()) < 32:
            errors.append(f"{key} must be at least 32 characters")

    workspace_root = settings.get("GRAPHHARBOR_WORKSPACE_ROOT", "").strip()
    if workspace_root and not Path(workspace_root).is_absolute():
        errors.append("GRAPHHARBOR_WORKSPACE_ROOT must be absolute")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "deploy/.env.runtime-service",
    )
    args = parser.parse_args()
    errors = validate(args.env_file)
    if errors:
        for error in errors:
            print(f"CONFIG_ERROR {error}", file=sys.stderr)
        return 1
    print(f"Runtime deployment config valid: {args.env_file}")
    print("Validated required values without printing secret contents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
