"""
LLM模型客户端配置
提供统一的OpenAI模型客户端实例，供整个应用使用
"""

from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient
from loguru import logger

from backend.conf.config import settings


def create_openai_model_client() -> OpenAIChatCompletionClient:
    """
    创建OpenAI模型客户端实例

    Returns:
        OpenAIChatCompletionClient: 配置好的模型客户端
    """
    try:
        logger.info("🤖 [LLM客户端] 开始创建OpenAI模型客户端")
        logger.info(f"   📋 模型: {settings.aimodel.model}")
        logger.info(f"   🌐 基础URL: {settings.aimodel.base_url}")
        logger.info(
            f"   🔑 API密钥: {'*' * (len(settings.aimodel.api_key) - 8) + settings.aimodel.api_key[-8:] if settings.aimodel.api_key else 'None'}"
        )

        # 创建模型客户端
        client = OpenAIChatCompletionClient(
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

        logger.success("✅ [LLM客户端] OpenAI模型客户端创建成功")
        return client

    except Exception as e:
        logger.error(f"❌ [LLM客户端] 创建OpenAI模型客户端失败: {e}")
        logger.error(f"   🐛 错误类型: {type(e).__name__}")
        logger.error(f"   📄 错误详情: {str(e)}")
        raise


# 创建全局模型客户端实例
try:
    openai_model_client = create_openai_model_client()
    logger.info("🌟 [LLM客户端] 全局OpenAI模型客户端实例已创建")
except Exception as e:
    logger.error(f"❌ [LLM客户端] 全局模型客户端创建失败: {e}")
    openai_model_client = None


def get_openai_model_client() -> OpenAIChatCompletionClient:
    """
    获取OpenAI模型客户端实例

    Returns:
        OpenAIChatCompletionClient: 模型客户端实例

    Raises:
        RuntimeError: 如果模型客户端未初始化
    """
    if openai_model_client is None:
        logger.error("❌ [LLM客户端] 模型客户端未初始化")
        raise RuntimeError("OpenAI模型客户端未初始化，请检查配置")

    return openai_model_client


def validate_model_client() -> bool:
    """
    验证模型客户端是否可用

    Returns:
        bool: 客户端是否可用
    """
    try:
        client = get_openai_model_client()
        if client is None:
            return False

        # 这里可以添加更多的验证逻辑，比如测试连接
        logger.debug("🔍 [LLM客户端] 模型客户端验证通过")
        return True

    except Exception as e:
        logger.error(f"❌ [LLM客户端] 模型客户端验证失败: {e}")
        return False


# 导出主要接口
__all__ = [
    "openai_model_client",
    "get_openai_model_client",
    "create_openai_model_client",
    "validate_model_client",
]
