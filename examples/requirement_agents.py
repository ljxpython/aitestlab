import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from app.api.v1.agent.llms import model_client
from app.controllers.requirement import requirement_controller
from app.log.log import logger
from app.schemas.requirements import RequirementCreate
from app.settings.config import settings
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
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
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_ext.models.openai import OpenAIChatCompletionClient
from llama_index.core import Document, SimpleDirectoryReader
from pydantic import BaseModel, Field

# 定义主题类型
requirement_acquisition_topic_type = "requirement_acquisition"
requirement_analysis_topic_type = "requirement_analysis"
requirement_output_topic_type = "requirement_output"
requirement_database_topic_type = "requirement_database"
task_result_topic_type = "collect_result"


class RequirementList(BaseModel):
    requirements: list[RequirementCreate] = Field(..., description="业务需求列表")


class RequirementFilesMessage(BaseModel):
    user_id: str = Field(..., description="用户ID")
    files: list[str] = Field(..., description="需求文件路径列表")
    content: str = Field(..., description="用户输入的内容")
    task: str = Field(default="分析需求文档", description="任务描述")


class ResponseMessage(BaseModel):
    source: str
    content: str
    is_final: bool = False


@dataclass
class RequirementMessage:
    source: str
    content: Any


@type_subscription(topic_type=requirement_acquisition_topic_type)
class RequirementAcquisitionAgent(RoutedAgent):
    def __init__(self, input_func=None):
        super().__init__("requirement acquisition agent")
        self.input_func = input_func

    @message_handler
    async def handle_message(
        self, message: RequirementFilesMessage, ctx: MessageContext
    ) -> None:
        # 发送到前端提示
        await self.publish_message(
            ResponseMessage(source="user", content=f"收到用户指令，准备开始需求分析"),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )

        try:
            # 从文件中读取文档内容
            doc_content = await self.get_document_from_files(message.files)

            # 发送处理状态到前端
            await self.publish_message(
                ResponseMessage(
                    source="文档解析智能体",
                    content="文件解析完成，开始对文档进行深入解析",
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

            # 创建需求获取智能体
            acquisition_agent = AssistantAgent(
                name="requirement_acquisition_agent",
                model_client=model_client,
                system_message="""
                你是一位专业的需求文档分析专家。请仔细阅读提供的需求文档内容，对其进行整理和摘要。
                重点提取以下信息:
                1. 主要功能需求
                2. 非功能性需求（性能、安全等）
                3. 业务背景和目标
                4. 用户角色和使用场景
                5. 核心术语和概念定义

                以结构化和易于理解的方式组织信息，markdown格式输出

                """,
                model_client_stream=True,
            )
            acquisition_content = ""

            # 运行需求获取流程
            if self.input_func:
                user_proxy = UserProxyAgent(
                    name="user_proxy", input_func=self.input_func
                )

                # 设置对话终止条件
                termination_en = TextMentionTermination("APPROVE")
                termination_zh = TextMentionTermination("同意")
                team = RoundRobinGroupChat(
                    [acquisition_agent, user_proxy],
                    termination_condition=termination_en | termination_zh,
                )

                stream = team.run_stream(
                    task=f"请分析以下需求文档内容:\n\n{doc_content}"
                )
                update_count = 0

                # 存储需求获取记录
                acquisition_memory = ListMemory()

                async for msg in stream:
                    # 模拟流式输出
                    if isinstance(msg, ModelClientStreamingChunkEvent):
                        await self.publish_message(
                            ResponseMessage(
                                source="文档解析智能体", content=msg.content
                            ),
                            topic_id=TopicId(
                                type=task_result_topic_type, source=self.id.key
                            ),
                        )
                        continue

                    # 统计需求获取更新次数并保存结果
                    if isinstance(msg, TextMessage):
                        # 保存需求获取记录
                        await acquisition_memory.add(
                            MemoryContent(
                                content=msg.model_dump_json(),
                                mime_type=MemoryMimeType.JSON,
                            )
                        )

                        if msg.source == "requirement_acquisition_agent":
                            # 用户参与反馈的次数
                            update_count += 1
                            acquisition_content = msg.content
                            continue

                    # 等待用户输入对需求获取的反馈
                    if (
                        isinstance(msg, UserInputRequestedEvent)
                        and msg.source == "user_proxy"
                    ):
                        await self.publish_message(
                            ResponseMessage(
                                source=msg.source,
                                content="请输入修改建议或者直接点击同意",
                            ),
                            topic_id=TopicId(
                                type=task_result_topic_type, source=self.id.key
                            ),
                        )
                        continue

                # 如果用户反馈次数大于1，则整合修改后的内容
                if update_count > 1:
                    # 整合智能体
                    summarize_agent = AssistantAgent(
                        name="summarize_agent",
                        system_message="""你是一位需求整理优化专家，根据上下文对话信息，输出用户最终期望的优化后的需求分析。""",
                        model_client=model_client,
                        memory=[acquisition_memory],
                        model_client_stream=True,
                    )

                    stream = summarize_agent.run_stream(
                        task="结合上下文对话信息，输出优化后的完整需求分析，markdown格式输出"
                    )
                    async for msg in stream:
                        # 流式输出到前端界面
                        if isinstance(msg, ModelClientStreamingChunkEvent):
                            # 流式输出结果到前端界面
                            await self.publish_message(
                                ResponseMessage(
                                    source="需求优化智能体", content=msg.content
                                ),
                                topic_id=TopicId(
                                    type=task_result_topic_type, source=self.id.key
                                ),
                            )
                            continue
                        # 获取优化后的完整结果，将数据传递给下一个智能体
                        if isinstance(msg, TaskResult):
                            acquisition_content = msg.messages[-1].content
                            continue
            else:
                # 用户没有反馈
                task = f"请分析以下需求文档内容:\n\n{doc_content}"
                stream = acquisition_agent.run_stream(task=task)

                async for msg in stream:
                    if isinstance(msg, ModelClientStreamingChunkEvent):
                        await self.publish_message(
                            ResponseMessage(
                                source="需求获取智能体", content=msg.content
                            ),
                            topic_id=TopicId(
                                type=task_result_topic_type, source=self.id.key
                            ),
                        )
                        continue
                    if isinstance(msg, TaskResult):
                        acquisition_content = msg.messages[-1].content
                        continue

            # 发送给下一个智能体
            await self.publish_message(
                RequirementMessage(source=self.id.type, content=acquisition_content),
                topic_id=TopicId(requirement_analysis_topic_type, source=self.id.key),
            )

        except Exception as e:
            error_msg = f"需求获取过程出错: {str(e)}"
            print(error_msg)
            await self.publish_message(
                ResponseMessage(source="需求获取智能体", content=error_msg),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

    async def get_document_from_files(self, files: list[str]) -> str:
        """获取文件内容"""
        try:
            data = SimpleDirectoryReader(input_files=files).load_data()
            doc = Document(text="\n\n".join([d.text for d in data[0:]]))
            return doc.text
        except Exception as e:
            raise Exception(f"文件读取失败: {str(e)}")

    async def get_document_from_llm_files(self, files: list[str]) -> str:
        """获取文件内容，支持图片、流程图、表格等数据"""
        extract_contents = ""
        for file in files:
            contents = extract_text_from_llm(file)
            extract_contents += contents + "\n\n--------------\n\n"
        return extract_contents


@type_subscription(topic_type=requirement_analysis_topic_type)
class RequirementAnalysisAgent(RoutedAgent):
    def __init__(self):
        super().__init__("requirement analysis agent")
        self._prompt = """
        根据如下格式的需求文档，进行需求分析，输出需求分析报告：
            ## 1. Background
            - **角色定位**: 资深软件测试需求分析师，具备跨领域测试经验
            - **核心职责**: 将模糊需求转化为可执行的测试方案，识别需求盲区与风险点
            - **行业经验**: 5年以上金融/医疗/物联网领域测试体系构建经验

            ## 2. Profile
            - **姓名**: TesterBot
            - **职位**: 智能测试需求架构师
            - **特质**:
              - 严谨的逻辑推理能力
              - 敏锐的边界条件发现能力
              - 优秀的风险预判意识

            ## 3. Skills
            - 掌握ISTQB/敏捷测试方法论
            - 精通测试用例设计方法（等价类/边界值/场景法等）
            - 熟练使用JIRA/TestRail/XMind
            - 擅长需求可测试性评估
            - 精通API/性能/安全测试策略制定

            ## 4. Goals
            1. 解析用户原始需求，明确测试范围
            2. 识别隐含需求与潜在风险点
            3. 生成结构化测试需求文档
            4. 输出可量化的验收标准
            5. 建立需求追溯矩阵

            ## 5. Constraints
            - 不涉及具体测试代码实现
            - 不替代人工需求评审
            - 保持技术中立立场
            - 遵守ISTQB伦理规范

            ## 6. Output Format
            ```markdown
            # 测试需求分析文档

            ## 测试目标
            - [清晰的功能目标描述]

            ## 需求拆解
            | 需求ID | 需求描述 | 测试类型 | 优先级 | 验收标准 |
            |--------|----------|----------|--------|----------|

            ## 风险分析
            - **高优先级风险**:
              - [风险描述] → [缓解方案]

            ## 测试策略
            - [功能测试]:
              - 覆盖场景:
                - [场景1]
                - [场景2]
            - [非功能测试]:
              - 性能指标: [RPS ≥ 1000]
              - 安全要求: [OWASP TOP10覆盖]

            ## 待澄清项
            - [问题1] (需业务方确认)
            - [问题2] (需架构师确认)
            ```
        """

    @message_handler
    async def handle_message(
        self, message: RequirementMessage, ctx: MessageContext
    ) -> None:
        # 创建需求分析智能体
        analysis_agent = AssistantAgent(
            name="requirement_analysis_agent",
            model_client=model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        # 发送状态消息到前端
        await self.publish_message(
            ResponseMessage(source="需求分析智能体", content="开始进行需求分析......"),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )

        # 构建任务描述
        task = f"请根据以下需求内容进行分析，并输出规范的需求分析报告：\n\n{message.content}"
        analysis_report = ""

        # 流式执行需求分析
        stream = analysis_agent.run_stream(task=task)
        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                # 流式输出结果到前端界面
                await self.publish_message(
                    ResponseMessage(source="需求分析智能体", content=msg.content),
                    topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
                )
                continue
            if isinstance(msg, TaskResult):
                analysis_report = msg.messages[-1].content
                continue

        # 发送完成消息
        await self.publish_message(
            ResponseMessage(source="需求分析智能体", content="需求分析完成"),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )

        # 发送给下一个智能体
        await self.publish_message(
            RequirementMessage(source=self.id.type, content=analysis_report),
            topic_id=TopicId(requirement_output_topic_type, source=self.id.key),
        )


@type_subscription(topic_type=requirement_output_topic_type)
class RequirementOutputAgent(RoutedAgent):
    def __init__(self):
        super().__init__("requirement output agent")
        self._prompt = """
        请根据需求分析报告进行详细的需求整理，尽量覆盖到报告中呈现所有的需求内容，每条需求信息都参考如下格式，生成合适条数的需求项。
        请注意，输出必须是一个有效的JSON格式，不要包含任何解释或前导文本。仅输出JSON对象本身，包含requirements数组。

        生成的JSON格式必须符合这个结构:
        {
          "requirements": [
            {
              "name": "需求名称",
              "description": "作为一名<某类型的用户>，我希望<达成某些目的>，这样可以<开发的价值>。",
              "category": "功能/性能/安全/接口/体验/改进/其它",
              "parent": "该需求的上级需求",
              "module": "所属的业务模块",
              "level": "需求层级[BR]",
              "reviewer": "李佳欣/李小明/张美丽",
              "estimated": 8,
              "criteria": "明确的验收标准",
              "remark": "备注信息",
              "keywords": "提取当前需求的关键词，逗号分隔",
              "project_id": 2
            }
          ]
        }

        请确保每个需求项都包含所有必填字段，并且值类型正确。尤其注意estimated必须是数字类型而不是字符串。
        """

    @message_handler
    async def handle_message(
        self, message: RequirementMessage, ctx: MessageContext
    ) -> None:
        # 创建需求结构化智能体 - 使用可返回JSON的模型
        model_client_json = OpenAIChatCompletionClient(
            model=settings.LLM_MODEL_SETTINGS.get("base_model", {}).get(
                "model", "deepseek-chat"
            ),
            base_url=settings.LLM_MODEL_SETTINGS.get("base_model", {}).get(
                "base_url", "https://api.deepseek.com/v1"
            ),
            api_key=settings.LLM_MODEL_SETTINGS.get("base_model", {}).get(
                "api_key", "sk-aec84097bc1b4f1fb5398790825bb379"
            ),
            response_format={"type": "json_object"},
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "family": "unknown",
            },
        )

        output_agent = AssistantAgent(
            name="requirement_output_agent",
            model_client=model_client_json,
            system_message=self._prompt,
            model_client_stream=True,
        )

        # 发送状态消息到前端
        await self.publish_message(
            ResponseMessage(
                source="需求结构化智能体", content="正在进行需求结构化......\n\n"
            ),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )

        # 构建任务描述
        task = f"根据以下需求分析报告，生成结构化需求列表：\n\n{message.content}"
        output_content = ""

        try:
            # 流式执行需求结构化
            stream = output_agent.run_stream(task=task)
            async for msg in stream:
                if isinstance(msg, ModelClientStreamingChunkEvent):
                    # 流式输出结果到前端界面
                    await self.publish_message(
                        ResponseMessage(source="需求结构化智能体", content=msg.content),
                        topic_id=TopicId(
                            type=task_result_topic_type, source=self.id.key
                        ),
                    )
                    continue
                if isinstance(msg, TaskResult):
                    output_content = msg.messages[-1].content
                    continue

            # 确保输出内容是有效的JSON
            parsed_output = json.loads(output_content)

            # 发送完成消息
            await self.publish_message(
                ResponseMessage(
                    source="需求结构化智能体",
                    content=f"需求结构化完成，共生成{len(parsed_output.get('requirements', []))}条需求",
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

            # 发送给下一个智能体
            await self.publish_message(
                RequirementMessage(source=self.id.type, content=output_content),
                topic_id=TopicId(requirement_database_topic_type, source=self.id.key),
            )

        except json.JSONDecodeError as e:
            error_msg = f"需求结构化生成的内容不是有效的JSON: {str(e)}"
            print(error_msg)

            # 尝试修复JSON格式错误
            fixed_agent = AssistantAgent(
                name="json_fix_agent",
                model_client=model_client_json,
                system_message="""
                你是一位专业的JSON修复专家。你的任务是接收一个可能格式不正确的JSON字符串，
                并将其转换为有效的JSON格式。只返回修复后的JSON字符串，不要包含任何解释或额外文本。
                确保输出符合以下结构:
                {
                  "requirements": [
                    {
                      "name": "...",
                      "description": "...",
                      ...其他字段...
                    }
                  ]
                }
            """,
                model_client_stream=False,
            )

            # 通知前端
            await self.publish_message(
                ResponseMessage(
                    source="需求结构化智能体", content="JSON格式有误，正在尝试修复..."
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

            # 尝试修复JSON
            fix_result = await fixed_agent.run(
                task=f"修复以下内容为正确的JSON格式:\n\n{output_content}"
            )
            fixed_content = fix_result.messages[-1].content

            try:
                # 再次验证JSON
                json.loads(fixed_content)

                # 发送给下一个智能体
                await self.publish_message(
                    RequirementMessage(source=self.id.type, content=fixed_content),
                    topic_id=TopicId(
                        requirement_database_topic_type, source=self.id.key
                    ),
                )

                await self.publish_message(
                    ResponseMessage(
                        source="需求结构化智能体",
                        content="JSON修复成功，已完成需求结构化",
                    ),
                    topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
                )

            except json.JSONDecodeError:
                await self.publish_message(
                    ResponseMessage(
                        source="需求结构化智能体",
                        content="无法修复JSON格式，需求结构化失败",
                    ),
                    topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
                )
        except Exception as e:
            error_msg = f"需求结构化过程出错: {str(e)}"
            print(error_msg)
            await self.publish_message(
                ResponseMessage(source="需求结构化智能体", content=error_msg),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )


@type_subscription(topic_type=requirement_database_topic_type)
class RequirementDatabaseAgent(RoutedAgent):
    def __init__(self):
        super().__init__("requirement database agent")

    @message_handler
    async def handle_message(
        self, message: RequirementMessage, ctx: MessageContext
    ) -> None:
        await self.publish_message(
            ResponseMessage(source="数据库智能体", content="正在执行需求入库..."),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )

        try:
            requirement_data = json.loads(message.content)
            requirement_list = RequirementList(**requirement_data)
            logger.info(f"需求入库数据: {requirement_list}")

            # 保存需求数据到数据库
            count = 0
            for requirement in requirement_list.requirements:
                await requirement_controller.create(obj_in=requirement)
                count += 1

            # 发送数据库保存结果(非最终消息)
            await self.publish_message(
                ResponseMessage(
                    source="database",
                    content=requirement_list.model_dump_json(),
                    is_final=False,
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

            # 发送最终完成消息
            await self.publish_message(
                ResponseMessage(
                    source="数据库智能体",
                    content=f"需求入库完成，共生成【{count}】条需求。",
                    is_final=True,
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

        except Exception as e:
            error_msg = f"需求入库过程出错: {str(e)}"
            print(error_msg)
            await self.publish_message(
                ResponseMessage(
                    source="数据库智能体", content=error_msg, is_final=True
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )


async def start_runtime(
    requirement_files: RequirementFilesMessage,
    collect_result: Callable[
        [ClosureContext, ResponseMessage, MessageContext], Awaitable[None]
    ],
    user_input_func: Callable[
        [str, Optional[CancellationToken]], Awaitable[str]
    ] = None,
):
    """启动需求分析运行时"""

    runtime = SingleThreadedAgentRuntime()

    # 注册智能体
    await RequirementAcquisitionAgent.register(
        runtime,
        requirement_acquisition_topic_type,
        lambda: RequirementAcquisitionAgent(input_func=user_input_func),
    )
    await RequirementAnalysisAgent.register(
        runtime, requirement_analysis_topic_type, lambda: RequirementAnalysisAgent()
    )
    await RequirementOutputAgent.register(
        runtime, requirement_output_topic_type, lambda: RequirementOutputAgent()
    )
    await RequirementDatabaseAgent.register(
        runtime, requirement_database_topic_type, lambda: RequirementDatabaseAgent()
    )

    # 定义闭包智能体接收消息
    await ClosureAgent.register_closure(
        runtime,
        "closure_agent",
        collect_result,
        subscriptions=lambda: [
            TypeSubscription(
                topic_type=task_result_topic_type, agent_type="closure_agent"
            )
        ],
    )

    # 启动运行时并发布消息
    runtime.start()
    await runtime.publish_message(
        requirement_files,
        topic_id=DefaultTopicId(type=requirement_acquisition_topic_type),
    )

    # 等待所有任务完成并关闭运行时
    await runtime.stop_when_idle()
    await runtime.close()
