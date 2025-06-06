import os

from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient

from examples.conf.config import settings

# 单例设计模式
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
