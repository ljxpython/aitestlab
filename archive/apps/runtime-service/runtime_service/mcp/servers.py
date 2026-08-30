from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def get_mcp_server_specs() -> dict[str, dict[str, Any]]:
    graph_root = Path(__file__).resolve().parents[1]
    math_server = graph_root / "mcp" / "local_math_server.py"
    text_server = graph_root / "mcp" / "local_text_server.py"
    return {
        "local_math": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(math_server)],
        },
        "local_text": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(text_server)],
        },
    }
