import asyncio

from autogen_core.models import ModelFamily, SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

from examples.conf.config import settings

openai_model_client = OpenAIChatCompletionClient(
    model=settings.aimodel.model,
    base_url=settings.aimodel.base_url,
    api_key=settings.aimodel.api_key,
    model_info={
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "family": ModelFamily.UNKNOWN,
        "structured_output": True,
        "multiple_system_messages": True,
    },
)


# 定义一个协程函数
async def main():
    result = await openai_model_client.create(
        [
            UserMessage(content="编写一段冒泡排序", source="user"),
            SystemMessage(content="你是python编程高手"),
        ]
    )
    print(result)
    await openai_model_client.close()


asyncio.run(main())
