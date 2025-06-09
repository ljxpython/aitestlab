"""
AI测试用例生成服务
使用AutoGen 0.5.7实现多智能体协作
仿照 examples/agent/testcase_agents.py 实现多智能体协作
参考 examples/topic.py 使用 SingleThreadedAgentRuntime + RoutedAgent + ClosureAgent
"""

import asyncio
import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Awaitable, Callable, List, Optional

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

# 添加文件解析相关导入
try:
    from llama_index.core import Document, SimpleDirectoryReader
except ImportError:
    logger.warning("无法导入llama_index，文件解析功能将不可用")
    Document = None
    SimpleDirectoryReader = None

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

# 添加文件解析工具函数
try:
    from rag_system.rag.utils import extract_text_from_llm
except ImportError:
    logger.warning("无法导入extract_text_from_llm，将使用简单文件读取")

    def extract_text_from_llm(file_path: str) -> str:
        """简单的文件读取实现"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"文件读取失败: {e}")
            return ""


# 定义topic类型 - 仿照examples/agent/testcase_agents.py
requirement_analysis_topic_type = "requirement_analysis"
testcase_generation_topic_type = "testcase_generation"
user_feedback_topic_type = "user_feedback"
testcase_review_topic_type = "testcase_review"
task_result_topic_type = "collect_result"

# 为了兼容性，保留旧的topic常量
REQUIREMENT_ANALYSIS_TOPIC = requirement_analysis_topic_type
TESTCASE_GENERATION_TOPIC = testcase_generation_topic_type
USER_FEEDBACK_TOPIC = user_feedback_topic_type
RESULT_COLLECTION_TOPIC = task_result_topic_type


# 定义消息类型 - 仿照examples/agent/testcase_agents.py
class RequirementMessage(BaseModel):
    """需求消息 - 仿照examples"""

    text_content: Optional[str] = Field(default="", description="文本内容")
    files: Optional[List[FileUpload]] = Field(default=None, description="上传的文件")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(default=1, description="轮次")
    user_feedback: Optional[str] = Field(default=None, description="用户反馈")


class ResponseMessage(BaseModel):
    """响应消息 - 仿照examples"""

    source: str = Field(..., description="消息来源")
    content: str = Field(..., description="消息内容")
    is_final: bool = Field(default=False, description="是否最终消息")


@dataclass
class TestCaseMessage:
    """测试用例消息 - 仿照examples"""

    source: str
    content: Any


# 为了兼容性，保留一些旧的消息类型
class RequirementAnalysisMessage(BaseModel):
    """需求分析消息 - 兼容性"""

    content: str = Field(..., description="用户上传的内容")
    files: Optional[List[dict]] = Field(default=None, description="上传的文件信息")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(default=1, description="轮次")


class TestCaseGenerationMessage(BaseModel):
    """测试用例生成消息 - 兼容性"""

    requirements: str = Field(..., description="分析后的需求")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(..., description="轮次")


class UserFeedbackMessage(BaseModel):
    """用户反馈消息 - 兼容性"""

    feedback: str = Field(..., description="用户反馈内容")
    previous_testcases: str = Field(..., description="之前生成的测试用例")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(..., description="轮次")


class AgentResultMessage(BaseModel):
    """智能体结果消息 - 兼容性"""

    content: str = Field(..., description="智能体输出内容")
    agent_type: str = Field(..., description="智能体类型")
    agent_name: str = Field(..., description="智能体名称")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(..., description="轮次")
    timestamp: str = Field(..., description="时间戳")
    is_complete: bool = Field(default=False, description="是否完成")


class TestCaseService:
    """AI测试用例生成服务"""

    def __init__(self):
        self.active_conversations = {}  # 存储活跃的对话状态
        self.max_rounds = 3  # 最大交互轮次
        self.collected_messages = {}  # 收集的消息，按对话ID分组
        logger.info("AI测试用例生成服务初始化完成")

    async def get_document_from_files(self, files: list[str]) -> str:
        """获取文件内容"""
        logger.info(f"开始解析文件 | 文件数量: {len(files)}")
        try:
            if not SimpleDirectoryReader or not Document:
                raise Exception("llama_index未安装，无法解析文件")

            data = SimpleDirectoryReader(input_files=files).load_data()
            doc = Document(text="\n\n".join([d.text for d in data[0:]]))
            logger.success(f"文件解析完成 | 内容长度: {len(doc.text)}")
            return doc.text
        except Exception as e:
            logger.error(f"文件读取失败: {str(e)}")
            raise Exception(f"文件读取失败: {str(e)}")

    async def get_document_from_llm_files(self, files: list[str]) -> str:
        """获取文件内容，支持图片、流程图、表格等数据"""
        logger.info(f"开始使用LLM解析文件 | 文件数量: {len(files)}")
        extract_contents = ""
        for file in files:
            try:
                logger.debug(f"正在解析文件: {file}")
                contents = extract_text_from_llm(file)
                extract_contents += contents + "\n\n--------------\n\n"
                logger.debug(f"文件解析完成: {file} | 内容长度: {len(contents)}")
            except Exception as e:
                logger.error(f"文件解析失败: {file} | 错误: {e}")
                extract_contents += (
                    f"文件 {file} 解析失败: {str(e)}\n\n--------------\n\n"
                )

        logger.success(f"LLM文件解析完成 | 总内容长度: {len(extract_contents)}")
        return extract_contents

    async def generate_testcase_stream(
        self, request: TestCaseRequest
    ) -> AsyncGenerator[TestCaseStreamChunk, None]:
        """
        流式生成测试用例
        使用 SingleThreadedAgentRuntime + RoutedAgent 实现智能体协作
        """
        conversation_id = request.conversation_id or str(uuid.uuid4())
        logger.info(
            f"开始生成测试用例 | 对话ID: {conversation_id} | 轮次: {request.round_number}"
        )

        if not openai_model_client:
            logger.error("OpenAI模型客户端未初始化")
            yield TestCaseStreamChunk(
                content="模型客户端未初始化，无法生成测试用例",
                agent_type=AgentType.USER_PROXY,
                agent_name="system",
                conversation_id=conversation_id,
                round_number=request.round_number,
                is_complete=True,
                timestamp=datetime.now(),
            )
            return

        try:
            # 创建运行时
            logger.info(
                f"[运行时] 创建 SingleThreadedAgentRuntime | 对话ID: {conversation_id}"
            )
            runtime = SingleThreadedAgentRuntime()

            # 注册智能体
            await self._register_agents(runtime, conversation_id)

            # 启动运行时
            logger.info(f"[运行时] 启动运行时 | 对话ID: {conversation_id}")
            runtime.start()

            # 初始化消息收集
            self.collected_messages[conversation_id] = []

            # 根据轮次发送不同的消息
            if request.round_number == 1:
                # 第一轮：需求分析
                logger.info(f"[消息发送] 发送需求分析消息 | 对话ID: {conversation_id}")
                content = await self._prepare_task_content(request)
                files_info = (
                    self._prepare_files_info(request.files) if request.files else None
                )

                await runtime.publish_message(
                    RequirementMessage(
                        text_content=content,
                        files=request.files,
                        conversation_id=conversation_id,
                        round_number=request.round_number,
                    ),
                    topic_id=DefaultTopicId(type=requirement_analysis_topic_type),
                )
            else:
                # 后续轮次：用户反馈
                logger.info(f"[消息发送] 发送用户反馈消息 | 对话ID: {conversation_id}")
                if not request.user_feedback:
                    raise ValueError("后续轮次需要提供用户反馈")

                # 获取之前的测试用例
                previous_testcases = self.active_conversations.get(
                    conversation_id, {}
                ).get("last_testcases", "")

                await runtime.publish_message(
                    TestCaseMessage(
                        source="user_feedback",
                        content=f"用户反馈：{request.user_feedback}\n\n之前的测试用例：\n{previous_testcases}",
                    ),
                    topic_id=DefaultTopicId(type=user_feedback_topic_type),
                )

            # 创建流式输出任务
            logger.info(f"[运行时] 开始流式输出任务 | 对话ID: {conversation_id}")

            # 启动后台任务等待完成
            async def wait_for_completion():
                await runtime.stop_when_idle()
                await runtime.close()
                logger.info(
                    f"[运行时] 任务完成，运行时已关闭 | 对话ID: {conversation_id}"
                )

            # 启动后台任务
            import asyncio

            completion_task = asyncio.create_task(wait_for_completion())

            # 实时流式输出收集的消息
            last_message_count = 0
            max_wait_time = 60  # 最大等待时间（秒）
            wait_time = 0

            while not completion_task.done() and wait_time < max_wait_time:
                # 检查是否有新消息
                messages = self.collected_messages.get(conversation_id, [])

                # 发送新消息
                if len(messages) > last_message_count:
                    for i in range(last_message_count, len(messages)):
                        msg = messages[i]
                        chunk = TestCaseStreamChunk(
                            content=msg["content"],
                            agent_type=AgentType(msg["agent_type"]),
                            agent_name=msg["agent_name"],
                            conversation_id=conversation_id,
                            round_number=request.round_number,
                            timestamp=datetime.fromisoformat(msg["timestamp"]),
                        )
                        logger.debug(
                            f"[流式输出] 发送消息块 | 智能体: {msg['agent_name']} | 对话ID: {conversation_id}"
                        )
                        yield chunk

                    last_message_count = len(messages)

                # 短暂等待
                await asyncio.sleep(0.1)
                wait_time += 0.1

            # 等待任务完成
            if not completion_task.done():
                logger.warning(
                    f"[运行时] 等待超时，强制完成 | 对话ID: {conversation_id}"
                )
                completion_task.cancel()
            else:
                await completion_task

            # 发送剩余消息（如果有）
            messages = self.collected_messages.get(conversation_id, [])
            if len(messages) > last_message_count:
                for i in range(last_message_count, len(messages)):
                    msg = messages[i]
                    chunk = TestCaseStreamChunk(
                        content=msg["content"],
                        agent_type=AgentType(msg["agent_type"]),
                        agent_name=msg["agent_name"],
                        conversation_id=conversation_id,
                        round_number=request.round_number,
                        timestamp=datetime.fromisoformat(msg["timestamp"]),
                    )
                    logger.debug(
                        f"[流式输出] 发送剩余消息块 | 智能体: {msg['agent_name']} | 对话ID: {conversation_id}"
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
            logger.success(
                f"[任务完成] 测试用例生成完成 | 对话ID: {conversation_id} | 总消息数: {len(messages)}"
            )
            yield final_chunk

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

    async def _register_agents(
        self, runtime: SingleThreadedAgentRuntime, conversation_id: str
    ):
        """注册智能体到运行时"""
        logger.info(f"[智能体注册] 开始注册智能体 | 对话ID: {conversation_id}")

        # 获取模型客户端
        model_client = openai_model_client
        if not model_client:
            logger.error("模型客户端未初始化")
            return

        # 注册需求分析智能体
        await RequirementAnalysisAgent.register(
            runtime,
            requirement_analysis_topic_type,
            lambda: RequirementAnalysisAgent(model_client),
        )

        # 注册测试用例生成智能体
        await TestCaseGenerationAgent.register(
            runtime,
            testcase_generation_topic_type,
            lambda: TestCaseGenerationAgent(model_client),
        )

        # 注册用户反馈处理智能体
        await UserFeedbackAgent.register(
            runtime,
            user_feedback_topic_type,
            lambda: UserFeedbackAgent(model_client),
        )

        # 注册测试用例评审智能体
        await TestCaseReviewAgent.register(
            runtime,
            testcase_review_topic_type,
            lambda: TestCaseReviewAgent(model_client),
        )

        # 注册结果收集器 - 使用ClosureAgent
        async def collect_result(
            _agent: ClosureContext, message: ResponseMessage, ctx: MessageContext
        ) -> None:
            """收集智能体结果"""
            if conversation_id not in self.collected_messages:
                self.collected_messages[conversation_id] = []

            # 转换为字典格式
            result_dict = {
                "content": message.content,
                "agent_type": "unknown",
                "agent_name": message.source,
                "conversation_id": conversation_id,
                "round_number": 1,
                "timestamp": datetime.now().isoformat(),
                "is_complete": message.is_final,
            }

            self.collected_messages[conversation_id].append(result_dict)
            logger.debug(
                f"[结果收集] 消息已收集 | 智能体: {message.source} | 对话ID: {conversation_id}"
            )

        await ClosureAgent.register_closure(
            runtime,
            "collect_result",
            collect_result,
            subscriptions=lambda: [
                TypeSubscription(
                    topic_type=task_result_topic_type, agent_type="collect_result"
                )
            ],
        )

        logger.success(f"[智能体注册] 所有智能体注册完成 | 对话ID: {conversation_id}")

    def _prepare_files_info(self, files: List[FileUpload]) -> List[dict]:
        """准备文件信息"""
        if not files:
            return []

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

    async def _prepare_task_content(self, request: TestCaseRequest) -> str:
        """
        准备任务内容，包括文本内容和文件解析
        """
        conversation_id = request.conversation_id or "unknown"
        logger.info(
            f"开始准备任务内容 | 对话ID: {conversation_id} | 轮次: {request.round_number}"
        )
        content_parts = []

        # 处理文本内容
        if request.text_content:
            content_parts.append(f"用户需求描述：\n{request.text_content}")
            logger.debug(
                f"添加文本内容 | 对话ID: {conversation_id} | 长度: {len(request.text_content)}"
            )

        # 处理上传的文件
        if request.files:
            logger.info(
                f"开始处理上传文件 | 对话ID: {conversation_id} | 文件数量: {len(request.files)}"
            )

            # 保存文件到临时位置并解析
            file_paths = []
            for file in request.files:
                try:
                    # 解码文件内容
                    file_content = base64.b64decode(file.content)

                    # 创建临时文件
                    temp_filename = f"temp_{uuid.uuid4()}_{file.filename}"
                    with open(temp_filename, "wb") as f:
                        f.write(file_content)

                    file_paths.append(temp_filename)
                    logger.debug(
                        f"文件保存成功 | 对话ID: {conversation_id} | {file.filename} -> {temp_filename}"
                    )

                except Exception as e:
                    logger.error(
                        f"文件处理失败 | 对话ID: {conversation_id} | {file.filename} | 错误: {e}"
                    )
                    content_parts.append(f"文件 {file.filename} 处理失败: {str(e)}")

            # 解析文件内容
            if file_paths:
                try:
                    # 尝试使用 llama_index 解析
                    file_content = await self.get_document_from_files(file_paths)
                    content_parts.append(f"文件内容：\n{file_content}")
                    logger.success(
                        f"文件解析完成 | 对话ID: {conversation_id} | 内容长度: {len(file_content)}"
                    )
                except Exception as e:
                    logger.warning(
                        f"llama_index 解析失败，尝试使用 LLM 解析 | 对话ID: {conversation_id} | 错误: {e}"
                    )
                    try:
                        # 使用 LLM 解析
                        file_content = await self.get_document_from_llm_files(
                            file_paths
                        )
                        content_parts.append(f"文件内容（LLM解析）：\n{file_content}")
                        logger.success(
                            f"LLM文件解析完成 | 对话ID: {conversation_id} | 内容长度: {len(file_content)}"
                        )
                    except Exception as e2:
                        logger.error(
                            f"文件解析完全失败 | 对话ID: {conversation_id} | 错误: {e2}"
                        )
                        content_parts.append(f"文件解析失败: {str(e2)}")

                # 清理临时文件
                for temp_file in file_paths:
                    try:
                        import os

                        os.remove(temp_file)
                        logger.debug(
                            f"临时文件清理完成 | 对话ID: {conversation_id} | 文件: {temp_file}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"临时文件清理失败 | 对话ID: {conversation_id} | 文件: {temp_file} | 错误: {e}"
                        )

        # 处理用户反馈（后续轮次）
        if request.round_number > 1 and request.user_feedback:
            content_parts.append(f"用户反馈：\n{request.user_feedback}")
            logger.debug(
                f"添加用户反馈 | 对话ID: {conversation_id} | 长度: {len(request.user_feedback)}"
            )

        task_content = "\n\n".join(content_parts)
        logger.success(
            f"任务内容准备完成 | 对话ID: {conversation_id} | 总长度: {len(task_content)}"
        )
        return task_content

    def _get_testcase_generator_prompt(self) -> str:
        """
        获取测试用例生成智能体的系统提示词
        """
        return """
你是一名拥有超过10年经验的资深软件测试架构师，精通各种测试方法论（如：等价类划分、边界值分析、因果图、场景法等），并且对用户体验和系统性能有深刻的理解。

你的任务是为接收到的功能需求，设计一份专业、全面、且易于执行的高质量测试用例。

测试要求：
1. 全面性：覆盖功能测试、UI/UX测试、兼容性测试、异常/边界测试、场景组合测试
2. 专业性：每个测试用例都应遵循标准格式，步骤清晰，预期结果明确
3. 输出格式：使用Markdown表格格式，包含用例ID、模块、优先级、测试类型、用例标题、前置条件、测试步骤、预期结果

请基于提供的需求，生成高质量的测试用例。如果用户提出修改意见，请根据反馈进行优化。

当用户对测试用例满意时，请等待用户回复"同意"或"APPROVE"来确认。
        """


# 智能体实现 - 仿照examples/agent/testcase_agents.py


@type_subscription(topic_type=requirement_analysis_topic_type)
class RequirementAnalysisAgent(RoutedAgent):
    """需求分析智能体 - 仿照examples"""

    def __init__(self, model_client) -> None:
        super().__init__(description="需求分析智能体")
        self._model_client = model_client
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
        self, message: RequirementMessage, ctx: MessageContext
    ) -> None:
        """处理需求分析"""
        logger.info(f"[需求分析] 开始需求分析 | 对话ID: {message.conversation_id}")

        if not self._model_client:
            logger.error("模型客户端未初始化")
            return

        agent = AssistantAgent(
            name="requirement_analyst",
            model_client=self._model_client,
            system_message=self._prompt,
        )

        # 构建分析任务
        task_content = f"请分析以下内容的功能需求：\n\n{message.text_content}"
        if message.files:
            task_content += f"\n\n文件信息：\n"
            for file_info in message.files:
                task_content += f"- {file_info.filename}: {file_info.content_type}\n"

        try:
            # 执行需求分析
            logger.info(
                f"[需求分析] 开始执行分析任务 | 对话ID: {message.conversation_id}"
            )
            result = await agent.run(task=task_content)
            requirements = str(result)

            logger.success(
                f"[需求分析] 需求分析完成 | 对话ID: {message.conversation_id}"
            )

            # 发送结果到测试用例生成智能体
            await self.publish_message(
                TestCaseMessage(
                    source="requirement_analyst",
                    content=requirements,
                ),
                topic_id=TopicId(
                    type=testcase_generation_topic_type, source=self.id.key
                ),
            )

            # 发送结果到收集器
            await self.publish_message(
                ResponseMessage(
                    source="requirement_analyst",
                    content=requirements,
                    is_final=False,
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

        except Exception as e:
            logger.error(
                f"[需求分析] 需求分析失败 | 对话ID: {message.conversation_id} | 错误: {e}"
            )


@type_subscription(topic_type=testcase_generation_topic_type)
class TestCaseGenerationAgent(RoutedAgent):
    """测试用例生成智能体 - 仿照examples"""

    def __init__(self, model_client, input_func=None):
        super().__init__(description="测试用例生成智能体")
        self._model_client = model_client
        self.input_func = input_func
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
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        """处理测试用例生成"""
        logger.info(f"[测试用例生成] 开始生成测试用例 | 来源: {message.source}")

        if not self._model_client:
            logger.error("模型客户端未初始化")
            return

        # 发送到前端提示
        await self.publish_message(
            ResponseMessage(
                source="testcase_generator",
                content="收到需求分析结果，开始生成测试用例...",
            ),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )

        testcase_generator_agent = AssistantAgent(
            name="testcase_generator_agent",
            model_client=self._model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        # 需要用户对生成的测试用例提出修改建议
        if self.input_func:
            user_proxy = UserProxyAgent(name="user_proxy", input_func=self.input_func)
            from autogen_agentchat.conditions import TextMentionTermination
            from autogen_agentchat.teams import RoundRobinGroupChat

            termination_en = TextMentionTermination("APPROVE")
            termination_zh = TextMentionTermination("同意")
            team = RoundRobinGroupChat(
                [testcase_generator_agent, user_proxy],
                termination_condition=termination_en | termination_zh,
            )

            stream = team.run_stream(
                task=f"基于以下需求生成测试用例：\n\n{message.content}"
            )
            testcase_content = ""

            async for msg in stream:
                # 模拟流式输出
                if isinstance(msg, ModelClientStreamingChunkEvent):
                    await self.publish_message(
                        ResponseMessage(
                            source="testcase_generator", content=msg.content
                        ),
                        topic_id=TopicId(
                            type=task_result_topic_type, source=self.id.key
                        ),
                    )
                    continue

                # 统计测试用例更新次数并保存生成的测试用例
                if isinstance(msg, TextMessage):
                    if msg.source == "testcase_generator_agent":
                        testcase_content = msg.content
                        continue

                # 等待用户输入对测试用例的修改建议
                if (
                    isinstance(msg, UserInputRequestedEvent)
                    and msg.source == "user_proxy"
                ):
                    await self.publish_message(
                        ResponseMessage(
                            source=msg.source, content="请输入修改建议或者直接点击同意"
                        ),
                        topic_id=TopicId(
                            type=task_result_topic_type, source=self.id.key
                        ),
                    )
                    continue

            # 发送给下一个智能体
            await self.publish_message(
                TestCaseMessage(source=self.id.type, content=testcase_content),
                topic_id=TopicId(testcase_review_topic_type, source=self.id.key),
            )
        else:
            # 用户不参与用例修改
            result = await testcase_generator_agent.run(
                task=f"基于以下需求生成测试用例：\n\n{message.content}"
            )
            testcase_content = str(result)

            # 发送到前端提示
            await self.publish_message(
                ResponseMessage(source="testcase_generator", content=testcase_content),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

            # 发送给下一个智能体
            await self.publish_message(
                TestCaseMessage(source=self.id.type, content=testcase_content),
                topic_id=TopicId(testcase_review_topic_type, source=self.id.key),
            )


@type_subscription(topic_type=user_feedback_topic_type)
class UserFeedbackAgent(RoutedAgent):
    """用户反馈处理智能体"""

    def __init__(self, model_client):
        super().__init__(description="用户反馈处理智能体")
        self._model_client = model_client
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
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        """处理用户反馈"""
        logger.info(f"[用户反馈处理] 开始处理用户反馈 | 来源: {message.source}")

        if not self._model_client:
            logger.error("模型客户端未初始化")
            return

        agent = AssistantAgent(
            name="feedback_processor",
            model_client=self._model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        task_content = f"请根据用户反馈，改进和优化以下测试用例：\n\n{message.content}"

        try:
            logger.info(f"[用户反馈处理] 开始执行反馈处理任务 | 来源: {message.source}")
            result = await agent.run(task=task_content)
            improved_testcases = str(result)

            logger.success(f"[用户反馈处理] 反馈处理完成 | 来源: {message.source}")

            # 发送结果到收集器
            await self.publish_message(
                ResponseMessage(
                    source="feedback_processor",
                    content=improved_testcases,
                    is_final=True,
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

        except Exception as e:
            logger.error(
                f"[用户反馈处理] 反馈处理失败 | 来源: {message.source} | 错误: {e}"
            )


# 移除旧的ResultCollectorAgent，因为我们使用ClosureAgent来收集结果


@type_subscription(topic_type=testcase_review_topic_type)
class TestCaseReviewAgent(RoutedAgent):
    """测试用例评审智能体 - 仿照examples"""

    def __init__(self, model_client):
        super().__init__(description="测试用例评审智能体")
        self._model_client = model_client
        self._prompt = """
你是资深测试用例评审专家，关注用例质量与测试覆盖有效性。请根据用户提供的测试用例进行评审，给出评审意见及评审报告，markdown格式输出

## 1. 评审重点
1. 需求覆盖度：确保每个需求点都有对应测试用例
2. 测试深度：正常流/边界/异常流全面覆盖
3. 用例可执行性：步骤清晰、数据明确

## 2. 输出格式
### 测试用例评审报告
#### 1. 概述
- 评审日期: [date]
- 用例总数: [number]
- 覆盖率: [percentage]

#### 2. 问题分类
**🔴 严重问题**
- [问题描述] @[用例编号]
- [改进建议]

**🟡 建议优化**
- [问题描述] @[用例编号]
- [优化方案]

#### 3. 总结建议
- 关键风险点: [风险描述]
- 后续行动计划: [action items]
        """

    @message_handler
    async def handle_testcase_review(
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        """处理测试用例评审"""
        logger.info(f"[测试用例评审] 开始评审测试用例 | 来源: {message.source}")

        if not self._model_client:
            logger.error("模型客户端未初始化")
            return

        agent = AssistantAgent(
            name="testcase_review_agent",
            model_client=self._model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        task = "请对如下测试用例进行评审，并输出规范的评审报告：\n" + message.content
        review_report = ""

        stream = agent.run_stream(task=task)
        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                # 流式输出结果到前端界面
                await self.publish_message(
                    ResponseMessage(source="testcase_reviewer", content=msg.content),
                    topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
                )
                continue
            if isinstance(msg, TaskResult):
                review_report = msg.messages[-1].content
                continue

        # 发送最终结果
        final_content = f"--测试用例开始--\n{message.content}\n--测试用例结束--\n--评审报告开始--\n{review_report}\n--评审报告结束--"
        await self.publish_message(
            ResponseMessage(
                source="testcase_reviewer", content=final_content, is_final=True
            ),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )


# 启动运行时函数 - 仿照examples/agent/testcase_agents.py
async def start_runtime(
    requirement: RequirementMessage, collect_result, user_input_func=None
):
    """启动运行时 - 仿照examples"""
    logger.info(f"[启动运行时] 开始启动运行时 | 对话ID: {requirement.conversation_id}")

    # 创建运行时
    runtime = SingleThreadedAgentRuntime()

    # 获取模型客户端
    model_client = openai_model_client
    if not model_client:
        logger.error("模型客户端未初始化")
        return

    # 注册智能体
    await RequirementAnalysisAgent.register(
        runtime,
        requirement_analysis_topic_type,
        lambda: RequirementAnalysisAgent(model_client),
    )

    await TestCaseGenerationAgent.register(
        runtime,
        testcase_generation_topic_type,
        lambda: TestCaseGenerationAgent(model_client, user_input_func),
    )

    await TestCaseReviewAgent.register(
        runtime, testcase_review_topic_type, lambda: TestCaseReviewAgent(model_client)
    )

    # 注册结果收集器 - 使用ClosureAgent
    await ClosureAgent.register_closure(
        runtime,
        "collect_result",
        collect_result,
        subscriptions=lambda: [
            TypeSubscription(
                topic_type=task_result_topic_type, agent_type="collect_result"
            )
        ],
    )

    # 启动运行时
    runtime.start()

    # 发送初始需求消息
    await runtime.publish_message(
        requirement, topic_id=DefaultTopicId(type=requirement_analysis_topic_type)
    )

    # 等待完成
    await runtime.stop_when_idle()
    await runtime.close()

    logger.success(f"[启动运行时] 运行时完成 | 对话ID: {requirement.conversation_id}")


# 全局服务实例
testcase_service = TestCaseService()
