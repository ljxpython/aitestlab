import os

from app.log.log import logger
from app.settings.config import settings
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient

# pip install -U "autogen-agentchat"
# pip install -U "autogen-ext[openai]"

# 配置日志

# 设置超时和重试
TIMEOUT_SECONDS = settings.LLM_MODEL_SETTINGS.get("timeout_seconds", 120)
MAX_RETRIES = settings.LLM_MODEL_SETTINGS.get("max_retries", 3)

# 默认API配置
DEFAULT_MODEL = settings.LLM_MODEL_SETTINGS.get("base_model", {}).get(
    "model", "deepseek-chat"
)
DEFAULT_API_BASE = settings.LLM_MODEL_SETTINGS.get("base_model", {}).get(
    "base_url", "https://api.deepseek.com/v1"
)
DEFAULT_API_KEY = settings.LLM_MODEL_SETTINGS.get("base_model", {}).get(
    "api_key", "sk-8eacd99135e043a8b2452df3dff107f8"
)

try:
    model_client = OpenAIChatCompletionClient(
        model=DEFAULT_MODEL,
        base_url=DEFAULT_API_BASE,
        api_key=DEFAULT_API_KEY,
        max_retries=MAX_RETRIES,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": ModelFamily.UNKNOWN,
        },
    )
    logger.info(f"初始化模型客户端成功: {DEFAULT_MODEL}, API Base: {DEFAULT_API_BASE}")
except Exception as e:
    logger.error(f"初始化模型客户端失败: {str(e)}")
