from __future__ import annotations

from deepagents.middleware.subagents import SubAgent


def list_deepagent_skills() -> list[str]:
    return ["/skills/common", "/skills/research"]


def list_subagents() -> list[SubAgent]:
    return [
        SubAgent(
            name="research-subagent",
            description="Deep research assistant for collecting evidence and references.",
            system_prompt=(
                "You are a specialist researcher. Use concise evidence, cite assumptions, and "
                "return actionable findings for the parent agent."
            ),
            skills=["/skills/research"],
        )
    ]
