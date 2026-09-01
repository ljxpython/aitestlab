from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from langgraph.pregel import Pregel

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))

from support import BindableFakeChatModel


def test_reference_factory_returns_pregel() -> None:
    async def run() -> None:
        from runtime_service.services.reference_agent.agent import get_agent

        graph = await get_agent(
            {
                "configurable": {
                    "thread_id": "factory-spike",
                    "_runtime_model": BindableFakeChatModel(responses=["factory"]),
                }
            }
        )
        assert isinstance(graph, Pregel)

    asyncio.run(run())
