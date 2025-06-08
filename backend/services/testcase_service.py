"""
AI测试用例生成服务
使用AutoGen 0.5.7实现多智能体协作
"""

import asyncio
import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.messages import (
    ModelClientStreamingChunkEvent,
    TextMessage,
    UserInputRequestedEvent,
)
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import (
    CancellationToken,
    ClosureAgent,
    ClosureContext,
    DefaultTopicId,
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    TopicId,
    TypeSubscription,
    message_handler,
    type_subscription,
)
from loguru import logger
from pydantic import BaseModel, Field

from backend.models.chat import (
    AgentMessage,
    AgentType,
    FileUpload,
    TestCaseRequest,
    TestCaseResponse,
    TestCaseStreamChunk,
)

try:
    from examples.llms import openai_model_client
except ImportError:
    logger.warning("无法导入openai_model_client，请检查examples/llms.py")
    openai_model_client = None


# 定义消息类型
class RequirementAnalysis(BaseModel):
    """需求分析消息"""

    content: str = Field(..., description="用户上传的内容")
    files: Optional[List[dict]] = Field(default=None, description="上传的文件信息")
    conversation_id: str = Field(..., description="对话ID")


class TestCaseGeneration(BaseModel):
    """测试用例生成消息"""

    requirements: str = Field(..., description="分析后的需求")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(default=1, description="交互轮次")


class UserFeedback(BaseModel):
    """用户反馈消息"""

    feedback: str = Field(..., description="用户反馈内容")
    previous_testcases: str = Field(..., description="之前生成的测试用例")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(..., description="交互轮次")


# Topic类型定义
REQUIREMENT_TOPIC = "requirement_analysis"
TESTCASE_TOPIC = "testcase_generation"
FEEDBACK_TOPIC = "user_feedback"
RESULT_COLLECTION_TOPIC = "result_collection"


class TestCaseService:
    """AI测试用例生成服务"""

    def __init__(self):
        self.active_conversations = {}  # 存储活跃的对话状态
        self.max_rounds = 3  # 最大交互轮次
        logger.info("AI测试用例生成服务初始化完成")

    async def generate_testcase_stream(
        self, request: TestCaseRequest
    ) -> AsyncGenerator[TestCaseStreamChunk, None]:
        """流式生成测试用例"""

        conversation_id = request.conversation_id or str(uuid.uuid4())
        logger.info(
            f"开始生成测试用例 | 对话ID: {conversation_id} | 轮次: {request.round_number}"
        )

        try:
            # 创建运行时
            runtime = SingleThreadedAgentRuntime()

            # 注册智能体
            await self._register_agents(runtime, conversation_id)

            # 启动运行时
            runtime.start()

            # 根据请求类型发送不同的消息
            if request.round_number == 1:
                # 第一轮：需求分析
                content = self._prepare_content(request)
                files_info = (
                    self._prepare_files_info(request.files) if request.files else None
                )

                await runtime.publish_message(
                    RequirementAnalysis(
                        content=content,
                        files=files_info,
                        conversation_id=conversation_id,
                    ),
                    topic_id=DefaultTopicId(type=REQUIREMENT_TOPIC),
                )
            else:
                # 后续轮次：用户反馈
                if not request.user_feedback:
                    raise ValueError("后续轮次需要提供用户反馈")

                # 获取之前的测试用例
                previous_testcases = self.active_conversations.get(
                    conversation_id, {}
                ).get("last_testcases", "")

                await runtime.publish_message(
                    UserFeedback(
                        feedback=request.user_feedback,
                        previous_testcases=previous_testcases,
                        conversation_id=conversation_id,
                        round_number=request.round_number,
                    ),
                    topic_id=DefaultTopicId(type=FEEDBACK_TOPIC),
                )

            # 等待完成
            await runtime.stop_when_idle()

            # 获取结果
            conversation_state = self.active_conversations.get(conversation_id, {})
            messages = conversation_state.get("messages", [])

            # 发送所有消息
            for msg in messages:
                chunk = TestCaseStreamChunk(
                    content=msg["content"],
                    agent_type=AgentType(msg["agent_type"]),
                    agent_name=msg["agent_name"],
                    conversation_id=conversation_id,
                    round_number=request.round_number,
                    timestamp=datetime.now(),
                )
                yield chunk

            # 发送完成信号
            final_chunk = TestCaseStreamChunk(
                content="",
                agent_type=AgentType.USER_PROXY,
                agent_name="system",
                conversation_id=conversation_id,
                round_number=request.round_number,
                is_complete=True,
                timestamp=datetime.now(),
            )
            yield final_chunk

            # 关闭运行时
            await runtime.close()

        except Exception as e:
            logger.error(f"生成测试用例失败 | 对话ID: {conversation_id} | 错误: {e}")
            error_chunk = TestCaseStreamChunk(
                content=f"生成失败: {str(e)}",
                agent_type=AgentType.USER_PROXY,
                agent_name="system",
                conversation_id=conversation_id,
                round_number=request.round_number,
                is_complete=True,
                timestamp=datetime.now(),
            )
            yield error_chunk

    def _prepare_content(self, request: TestCaseRequest) -> str:
        """准备内容"""
        content_parts = []

        if request.text_content:
            content_parts.append(f"文本内容：\n{request.text_content}")

        if request.files:
            content_parts.append(f"上传了 {len(request.files)} 个文件")
            for file in request.files:
                content_parts.append(f"- {file.filename} ({file.content_type})")

        return "\n\n".join(content_parts)

    def _prepare_files_info(self, files: List[FileUpload]) -> List[dict]:
        """准备文件信息"""
        files_info = []
        for file in files:
            file_info = {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": file.size,
            }

            # 如果是文本文件，尝试解码内容
            if file.content_type.startswith("text/"):
                try:
                    content = base64.b64decode(file.content).decode("utf-8")
                    file_info["content"] = content[:1000]  # 限制长度
                except Exception as e:
                    logger.warning(f"解码文件内容失败: {e}")
                    file_info["content"] = "无法解码文件内容"

            files_info.append(file_info)

        return files_info

    async def _register_agents(
        self, runtime: SingleThreadedAgentRuntime, conversation_id: str
    ):
        """注册智能体到运行时"""

        # 注册需求分析智能体
        await RequirementAgent.register(
            runtime, REQUIREMENT_TOPIC, lambda: RequirementAgent(conversation_id, self)
        )

        # 注册测试用例生成智能体
        await TestCaseAgent.register(
            runtime, TESTCASE_TOPIC, lambda: TestCaseAgent(conversation_id, self)
        )

        # 注册用户反馈处理智能体
        await FeedbackAgent.register(
            runtime, FEEDBACK_TOPIC, lambda: FeedbackAgent(conversation_id, self)
        )

        # 注册结果收集智能体
        await ClosureAgent.register_closure(
            runtime,
            "result_collector",
            self._collect_result,
            subscriptions=lambda: [
                TypeSubscription(
                    topic_type=RESULT_COLLECTION_TOPIC, agent_type="result_collector"
                )
            ],
        )

    async def _collect_result(
        self, agent: ClosureContext, message: dict, ctx: MessageContext
    ) -> None:
        """收集智能体结果"""
        conversation_id = message.get("conversation_id")
        if not conversation_id:
            return

        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = {"messages": []}

        self.active_conversations[conversation_id]["messages"].append(message)

        # 如果是测试用例，保存最新的测试用例
        if message.get("agent_type") == AgentType.TESTCASE_AGENT.value:
            self.active_conversations[conversation_id]["last_testcases"] = message.get(
                "content", ""
            )


# 智能体实现


@type_subscription(topic_type=REQUIREMENT_TOPIC)
class RequirementAgent(RoutedAgent):
    """需求获取智能体"""

    def __init__(self, conversation_id: str, service: TestCaseService):
        super().__init__(description="需求分析智能体")
        self.conversation_id = conversation_id
        self.service = service
        self._prompt = """
你是一位资深的软件需求分析师，拥有超过10年的需求分析和软件测试经验。

你的任务是：
1. 仔细分析用户提供的内容（文本、文件等）
2. 识别出核心的功能需求和业务场景
3. 提取关键的业务规则和约束条件
4. 整理出清晰、结构化的需求描述

请用专业、清晰的语言输出分析结果，为后续的测试用例生成提供准确的需求基础。
        """

    @message_handler
    async def handle_requirement_analysis(
        self, message: RequirementAnalysis, ctx: MessageContext
    ) -> None:
        """处理需求分析"""
        logger.info(f"需求分析智能体开始工作 | 对话ID: {self.conversation_id}")

        if not openai_model_client:
            logger.error("OpenAI模型客户端未初始化")
            return

        agent = AssistantAgent(
            name="requirement_analyst",
            model_client=openai_model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        # 构建分析任务
        task_content = f"请分析以下内容的功能需求：\n\n{message.content}"
        if message.files:
            task_content += f"\n\n文件信息：\n"
            for file_info in message.files:
                task_content += f"- {file_info['filename']}: {file_info.get('content', '二进制文件')}\n"

        try:
            # 执行需求分析
            result = await agent.run(task=task_content)
            requirements = str(result)

            logger.success(f"需求分析完成 | 对话ID: {self.conversation_id}")

            # 发送结果到收集器
            await self.publish_message(
                {
                    "content": requirements,
                    "agent_type": AgentType.REQUIREMENT_AGENT.value,
                    "agent_name": "requirement_analyst",
                    "conversation_id": self.conversation_id,
                    "timestamp": datetime.now().isoformat(),
                },
                topic_id=TopicId(type=RESULT_COLLECTION_TOPIC, source=self.id.key),
            )

            # 发送给测试用例生成智能体
            await self.publish_message(
                TestCaseGeneration(
                    requirements=requirements,
                    conversation_id=self.conversation_id,
                    round_number=1,
                ),
                topic_id=TopicId(type=TESTCASE_TOPIC, source=self.id.key),
            )

        except Exception as e:
            logger.error(f"需求分析失败 | 对话ID: {self.conversation_id} | 错误: {e}")


@type_subscription(topic_type=TESTCASE_TOPIC)
class TestCaseAgent(RoutedAgent):
    """测试用例生成智能体"""

    def __init__(self, conversation_id: str, service: TestCaseService):
        super().__init__(description="测试用例生成智能体")
        self.conversation_id = conversation_id
        self.service = service
        self._prompt = """
你是一名拥有超过10年经验的资深软件测试架构师，精通各种测试方法论（如：等价类划分、边界值分析、因果图、场景法等），并且对用户体验和系统性能有深刻的理解。

你的任务是为接收到的功能需求，设计一份专业、全面、且易于执行的高质量测试用例。

测试要求：
1. 全面性：覆盖功能测试、UI/UX测试、兼容性测试、异常/边界测试、场景组合测试
2. 专业性：每个测试用例都应遵循标准格式，步骤清晰，预期结果明确
3. 输出格式：使用Markdown表格格式，包含用例ID、模块、优先级、测试类型、用例标题、前置条件、测试步骤、预期结果

请基于提供的需求，生成高质量的测试用例。
        """

    @message_handler
    async def handle_testcase_generation(
        self, message: TestCaseGeneration, ctx: MessageContext
    ) -> None:
        """处理测试用例生成"""
        logger.info(
            f"测试用例生成智能体开始工作 | 对话ID: {self.conversation_id} | 轮次: {message.round_number}"
        )

        if not openai_model_client:
            logger.error("OpenAI模型客户端未初始化")
            return

        agent = AssistantAgent(
            name="testcase_generator",
            model_client=openai_model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        task_content = f"基于以下需求生成测试用例：\n\n{message.requirements}"

        try:
            result = await agent.run(task=task_content)
            testcases = str(result)

            logger.success(f"测试用例生成完成 | 对话ID: {self.conversation_id}")

            # 发送结果到收集器
            await self.publish_message(
                {
                    "content": testcases,
                    "agent_type": AgentType.TESTCASE_AGENT.value,
                    "agent_name": "testcase_generator",
                    "conversation_id": self.conversation_id,
                    "timestamp": datetime.now().isoformat(),
                },
                topic_id=TopicId(type=RESULT_COLLECTION_TOPIC, source=self.id.key),
            )

        except Exception as e:
            logger.error(
                f"测试用例生成失败 | 对话ID: {self.conversation_id} | 错误: {e}"
            )


@type_subscription(topic_type=FEEDBACK_TOPIC)
class FeedbackAgent(RoutedAgent):
    """用户反馈处理智能体"""

    def __init__(self, conversation_id: str, service: TestCaseService):
        super().__init__(description="用户反馈处理智能体")
        self.conversation_id = conversation_id
        self.service = service
        self._prompt = """
你是一名拥有超过15年软件质量保证（SQA）经验的测试主管（Test Lead）。你以严谨、细致和注重细节而闻名。

你的任务是：
1. 仔细分析用户对测试用例的反馈意见
2. 识别需要改进的具体点
3. 基于反馈重新优化和完善测试用例
4. 确保修改后的测试用例更符合用户的期望和实际需求

请根据用户反馈，对测试用例进行针对性的改进和优化。
        """

    @message_handler
    async def handle_user_feedback(
        self, message: UserFeedback, ctx: MessageContext
    ) -> None:
        """处理用户反馈"""
        logger.info(
            f"用户反馈处理智能体开始工作 | 对话ID: {self.conversation_id} | 轮次: {message.round_number}"
        )

        if not openai_model_client:
            logger.error("OpenAI模型客户端未初始化")
            return

        agent = AssistantAgent(
            name="feedback_processor",
            model_client=openai_model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        task_content = f"""
用户反馈：{message.feedback}

之前的测试用例：
{message.previous_testcases}

请根据用户反馈，改进和优化测试用例。
        """

        try:
            result = await agent.run(task=task_content)
            improved_testcases = str(result)

            logger.success(f"用户反馈处理完成 | 对话ID: {self.conversation_id}")

            # 发送结果到收集器
            await self.publish_message(
                {
                    "content": improved_testcases,
                    "agent_type": AgentType.TESTCASE_AGENT.value,
                    "agent_name": "feedback_processor",
                    "conversation_id": self.conversation_id,
                    "timestamp": datetime.now().isoformat(),
                },
                topic_id=TopicId(type=RESULT_COLLECTION_TOPIC, source=self.id.key),
            )

        except Exception as e:
            logger.error(
                f"用户反馈处理失败 | 对话ID: {self.conversation_id} | 错误: {e}"
            )


# 全局服务实例
testcase_service = TestCaseService()
