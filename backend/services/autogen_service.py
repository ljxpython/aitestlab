import asyncio
import os
import sys
import uuid
from typing import AsyncGenerator, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import ModelClientStreamingChunkEvent
from loguru import logger

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)

# 使用 backend 目录下的配置
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient

from backend.conf.config import settings

# 创建模型客户端
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


class AutoGenService:
    """AutoGen 服务类"""

    def __init__(
        self, max_agents: int = 100, cleanup_interval: int = 3600, agent_ttl: int = 7200
    ):
        """
        初始化 AutoGen 服务

        Args:
            max_agents: 最大 Agent 数量
            cleanup_interval: 清理检查间隔（秒）
            agent_ttl: Agent 生存时间（秒）
        """
        self.agents = {}
        self.max_agents = max_agents
        self.cleanup_interval = cleanup_interval
        self.agent_ttl = agent_ttl
        self._last_cleanup = asyncio.get_event_loop().time()
        logger.info(
            f"AutoGen 服务初始化 | 最大Agent数: {max_agents} | TTL: {agent_ttl}s"
        )

    def create_agent(
        self, conversation_id: str, system_message: str = "你是一个有用的AI助手"
    ) -> AssistantAgent:
        """创建或获取 Agent"""
        if conversation_id not in self.agents:
            logger.debug(f"创建新的 Agent | 对话ID: {conversation_id}")
            # 将 UUID 中的连字符替换为下划线，确保是有效的 Python 标识符
            safe_name = f"assistant_{conversation_id.replace('-', '_')}"
            agent = AssistantAgent(
                name=safe_name,
                model_client=openai_model_client,
                system_message=system_message,
                model_client_stream=True,
            )
            self.agents[conversation_id] = {
                "agent": agent,
                "created_at": asyncio.get_event_loop().time(),
                "last_used": asyncio.get_event_loop().time(),
            }
            logger.success(
                f"Agent 创建成功 | 对话ID: {conversation_id} | 名称: {safe_name}"
            )
        else:
            logger.debug(f"复用现有 Agent | 对话ID: {conversation_id}")
            # 更新最后使用时间
            self.agents[conversation_id]["last_used"] = asyncio.get_event_loop().time()
        return self.agents[conversation_id]["agent"]

    def _cleanup_expired_agents(self):
        """清理过期的 Agent"""
        current_time = asyncio.get_event_loop().time()
        expired_ids = []

        for conv_id, agent_info in self.agents.items():
            if current_time - agent_info["last_used"] > self.agent_ttl:
                expired_ids.append(conv_id)

        for conv_id in expired_ids:
            del self.agents[conv_id]
            logger.info(f"清理过期 Agent | 对话ID: {conv_id}")

        if expired_ids:
            logger.info(
                f"清理完成 | 清理数量: {len(expired_ids)} | 剩余数量: {len(self.agents)}"
            )

    def _cleanup_oldest_agents(self, target_count: int):
        """清理最旧的 Agent 到目标数量"""
        if len(self.agents) <= target_count:
            return

        # 按最后使用时间排序，清理最旧的
        sorted_agents = sorted(self.agents.items(), key=lambda x: x[1]["last_used"])

        cleanup_count = len(self.agents) - target_count
        for i in range(cleanup_count):
            conv_id = sorted_agents[i][0]
            del self.agents[conv_id]
            logger.info(f"清理最旧 Agent | 对话ID: {conv_id}")

        logger.info(
            f"容量清理完成 | 清理数量: {cleanup_count} | 剩余数量: {len(self.agents)}"
        )

    def _auto_cleanup(self):
        """自动清理检查"""
        current_time = asyncio.get_event_loop().time()

        # 检查是否需要清理
        if current_time - self._last_cleanup < self.cleanup_interval:
            return

        logger.debug("开始自动清理检查...")

        # 清理过期的 Agent
        self._cleanup_expired_agents()

        # 如果数量仍然超过限制，清理最旧的
        if len(self.agents) > self.max_agents:
            logger.warning(
                f"Agent 数量超过限制 | 当前: {len(self.agents)} | 限制: {self.max_agents}"
            )
            self._cleanup_oldest_agents(self.max_agents // 2)  # 清理到一半容量

        self._last_cleanup = current_time

    async def chat_stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        system_message: str = "你是一个有用的AI助手",
    ) -> AsyncGenerator[str, None]:
        """流式聊天"""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        logger.info(
            f"开始流式聊天 | 对话ID: {conversation_id} | 消息: {message[:100]}..."
        )

        # 执行自动清理
        self._auto_cleanup()

        agent = self.create_agent(conversation_id, system_message)

        try:
            # 获取流式响应
            logger.debug(f"调用 Agent 流式响应 | 对话ID: {conversation_id}")
            result = agent.run_stream(task=message)

            chunk_count = 0
            async for item in result:
                if isinstance(item, ModelClientStreamingChunkEvent):
                    if item.content:
                        chunk_count += 1
                        logger.debug(
                            f"收到流式数据块 {chunk_count} | 对话ID: {conversation_id} | 内容: {item.content[:50]}..."
                        )
                        yield item.content

            logger.success(
                f"流式聊天完成 | 对话ID: {conversation_id} | 总块数: {chunk_count}"
            )

        except Exception as e:
            logger.error(f"流式聊天失败 | 对话ID: {conversation_id} | 错误: {e}")
            yield f"错误: {str(e)}"

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        system_message: str = "你是一个有用的AI助手",
    ) -> tuple[str, str]:
        """非流式聊天"""
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        logger.info(
            f"开始普通聊天 | 对话ID: {conversation_id} | 消息: {message[:100]}..."
        )

        # 执行自动清理
        self._auto_cleanup()

        agent = self.create_agent(conversation_id, system_message)

        try:
            logger.debug(f"调用 Agent 普通响应 | 对话ID: {conversation_id}")
            result = await agent.run(task=message)
            response = str(result)
            logger.success(
                f"普通聊天完成 | 对话ID: {conversation_id} | 响应长度: {len(response)}"
            )
            return response, conversation_id
        except Exception as e:
            logger.error(f"普通聊天失败 | 对话ID: {conversation_id} | 错误: {e}")
            return f"错误: {str(e)}", conversation_id

    def clear_conversation(self, conversation_id: str):
        """清除对话"""
        if conversation_id in self.agents:
            logger.info(f"清除对话 | 对话ID: {conversation_id}")
            del self.agents[conversation_id]
            logger.success(f"对话清除成功 | 对话ID: {conversation_id}")
        else:
            logger.warning(f"尝试清除不存在的对话 | 对话ID: {conversation_id}")

    def get_agent_stats(self) -> dict:
        """获取 Agent 统计信息"""
        current_time = asyncio.get_event_loop().time()
        active_count = 0
        expired_count = 0

        for agent_info in self.agents.values():
            if current_time - agent_info["last_used"] <= self.agent_ttl:
                active_count += 1
            else:
                expired_count += 1

        return {
            "total_agents": len(self.agents),
            "active_agents": active_count,
            "expired_agents": expired_count,
            "max_agents": self.max_agents,
            "agent_ttl": self.agent_ttl,
            "cleanup_interval": self.cleanup_interval,
        }

    def force_cleanup(self):
        """强制执行清理"""
        logger.info("执行强制清理...")
        self._cleanup_expired_agents()
        if len(self.agents) > self.max_agents:
            self._cleanup_oldest_agents(self.max_agents // 2)
        logger.info("强制清理完成")


# 全局服务实例
def create_autogen_service():
    """创建 AutoGen 服务实例"""
    try:
        # 尝试导入配置
        from backend.conf.config import settings

        # 使用配置中的参数，如果没有则使用默认值
        max_agents = getattr(settings, "autogen", {}).get("max_agents", 100)
        cleanup_interval = getattr(settings, "autogen", {}).get(
            "cleanup_interval", 3600
        )
        agent_ttl = getattr(settings, "autogen", {}).get("agent_ttl", 7200)

        return AutoGenService(
            max_agents=max_agents,
            cleanup_interval=cleanup_interval,
            agent_ttl=agent_ttl,
        )
    except ImportError:
        logger.warning("无法导入配置，使用默认参数")
        return AutoGenService()


autogen_service = create_autogen_service()
