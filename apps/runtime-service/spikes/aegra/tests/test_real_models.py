from __future__ import annotations

import asyncio
import uuid

from .conftest import require_keys


def _value(result: object, key: str) -> object:
    return result.get(key) if isinstance(result, dict) else getattr(result, key)


def test_reference_agent_uses_real_deepseek(client, real_env: dict[str, str]) -> None:
    require_keys(real_env, "DEEPSEEK_PROXY_URL", "DEEPSEEK_PROXY_API_KEY", "DEEPSEEK_PROXY_DEFAULT_MODEL")

    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        result = await client.runs.wait(
            thread_id,
            "reference_agent",
            input={"messages": [{"role": "user", "content": "Reply with exactly: aegra-text-ok"}]},
            metadata={"spike_probe": "deepseek"},
            durability="sync",
        )
        assert result

    asyncio.run(run())


def test_multimodal_agent_uses_real_doubao(client, real_env: dict[str, str]) -> None:
    require_keys(real_env, "DOUBAO_API_BASE", "DOUBAO_API_KEY", "DOUBAO_MODEL")
    image = (
        "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAANElEQVR4nO3OMQ0AMAgAMDucCEIIEnEFMpYsPfq3OjN69qVycHBwcHBwcHBwcHBwcHD4+nAT8cMIsfghngAAAABJRU5ErkJggg=="
    )

    async def run() -> None:
        thread_id = str(uuid.uuid4())
        await client.threads.create(thread_id=thread_id, if_exists="raise")
        result = await client.runs.wait(
            thread_id,
            "spike_doubao_multimodal",
            input={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}},
                        ],
                    }
                ]
            },
            durability="sync",
        )
        assert result

    asyncio.run(run())
