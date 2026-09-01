from __future__ import annotations

import asyncio


def test_deep_agent_declares_skill_and_subagent_capabilities() -> None:
    """Construction-level check; cross-worker namespace isolation needs a real fixture."""

    async def run() -> None:
        from runtime_service.services.deep_agent_demo.agent import get_agent

        first = await get_agent({"configurable": {"thread_id": "deep-a"}})
        second = await get_agent({"configurable": {"thread_id": "deep-b"}})
        assert first is not second
        assert "SkillsMiddleware.before_agent" in first.nodes
        tools_node = first.nodes["tools"].bound
        tools_by_name = getattr(tools_node, "_tools_by_name", {})
        assert "task" in tools_by_name
        assert "summarizer" in tools_by_name["task"].description

    asyncio.run(run())

