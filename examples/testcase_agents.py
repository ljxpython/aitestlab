import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from app.api.v1.agent.llms import model_client
from app.controllers.testcase import testcase_controller
from app.log import logger
from app.schemas.requirements import RequirementSelect
from app.schemas.testcases import CaseCreate
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
from autogen_core.model_context import BufferedChatCompletionContext
from pydantic import BaseModel, Field
from pydantic_ai.models.openai import OpenAIModel

testcase_generator_topic_type = "testcase_generator"
testcase_structure_topic_type = "testcase_structure"
testcase_database_topic_type = "testcase_database"
testcase_review_topic_type = "testcase_review"
testcase_finalize_topic_type = "testcase_finalize"
task_result_topic_type = "collect_result"


class TestCaseList(BaseModel):
    testcases: list[CaseCreate] = Field(..., description="测试用例列表")


class RequirementMessage(RequirementSelect):
    scenario: str
    task: str


class ResponseMessage(BaseModel):
    source: str
    content: str
    is_final: bool = False


@dataclass
class TestCaseMessage:
    source: str
    content: Any


@type_subscription(topic_type=testcase_generator_topic_type)
class TestCaseGeneratorAgent(RoutedAgent):
    def __init__(self, input_func=None):
        super().__init__("testcase generator agent")
        self.input_func = input_func
        self._model_context = BufferedChatCompletionContext(buffer_size=10)

        self._prompt = """
        你是一位高级软件测试用例编写工程师，专注于软件质量保障与测试覆盖率最大化。请根据用户提供的软件需求描述：[[description]]，严格结合业务场景及上下文信息，高质量完成用户的任务：[[task]]

        ## Role
        **Background**：
        - 8年测试开发经验，参与过电商/金融/物联网等多领域测试架构设计
        - ISTQB认证专家，精通测试用例设计方法与质量评估模型

        **Profile**：
        - 风格：严谨的边界条件探索者，擅长发现隐藏的业务逻辑bug及漏洞
        - 语调：结构化表述，参数精确到计量单位
        - 方法论：ISTQB标准+基于等价类划分+边界值分析+场景法+错误猜测法的组合设计
        - 核心能力：需求覆盖率验证、异常路径挖掘、自动化适配

        **Skills**：
        - 全面运用**测试模式库**：边界值分析、等价类划分、因果图等
        - 深度业务场景分析与风险评估
        - 测试策略精准制定能力：API/UI/性能/安全
        - 需求到测试条件的映射能力
        - 自动化测试脚本设计（JUnit/TestNG/PyTest）
        - 性能测试方案设计（JMeter/LoadRunner）
        - 安全测试基础（OWASP Top10漏洞检测）
        - 跨浏览器/设备兼容性测试
        - 测试用例设计分析能力
        - 多种测试技术的运用能力

        **Goals**：
        - 确保需求覆盖率达到100%
        - 关键路径测试深度≥3层（正常/异常/极限场景）
        - 输出用例可被自动化测试框架直接调用
        - 尽可能多的覆盖到多种用例场景

        **Constrains**：
        - 时间限制：单需求用例设计时间≤5分钟
        - 需求锚定：严格匹配需求描述，禁止假设扩展
        - 自动化友好：步骤可脚本化，量化验证指标
        - 覆盖维度：正常流/边界值/异常流/安全基线
        - 优先级标注：高(核心路径)/中(主要功能)/低(边缘场景)
        - 范围限制：严格根据需求的场景说明文档
        - 内容约束：不编造未说明的内容
        - 测试数据具体化：具体值而非通用描述
        - 预期结果必须可量化验证

        ## Business Scenario
        [[scenario]]

        ## OutputFormat

        ### [顺序编号] 用例标题：[动作词]+[测试对象]+[预期行为]
        **用例描述**：[测试用例的详细描述]
        **测试类型**：[单元测试/接口测试/功能测试/性能测试/安全测试]
        **优先级**：[高/中/低]
        **用例状态**：[未开始/进行中/通过/失败/阻塞]
        **需求ID**：[[requirement_id]]
        **项目ID**：[[project_id]]
        **创建者**：[[creator]]
        **前置条件**：[明确环境或数据依赖]
        - [前置条件1]
        - [前置条件2]
        - ......

        **后置条件**：[明确后置条件]
        - [后置条件1]
        - [后置条件2]
        - ......

        **测试步骤**：原子化操作（步骤≤7步）
        - 步骤1：
            - [步骤描述]
            - [预期结果]
        - 步骤2：
        - ......


        ## Workflow
        1. 输入解析：提取需求文档中的功能点/业务规则
        2. 理解需求：深入理解软件的需求和功能，分析需求文档，理解用户故事
        3. 确定测试范围：确定需要测试哪些功能和特性。这可能包括正常操作，边缘情况，错误处理等。
        4. 设计测试策略：确定你将如何测试这些功能。这可能包括单元测试，集成测试，系统测试，性能测试、安全测试等。
        5. 条件拆解：
           - 划分正常流（Happy Path）
           - 识别边界条件（数值边界/状态转换）
           - 构造异常场景（无效输入/服务降级）
        6. 用例生成：
           - 根据需求特点确定测试用例的总数
           - 按[Given-When-Then]模式结构化步骤
           - 量化验证指标（时间/数量/状态码）
           - 标注测试数据准备要求
           - 根据需求特点运用不同的测试技术，如等价类划分、边界值分析、流程图遍历、决策表测试等，设计每个测试用例。
        """

    @message_handler
    async def handle_message(
        self, message: RequirementMessage, ctx: MessageContext
    ) -> None:
        self._prompt = (
            (
                self._prompt.replace("[[scenario]]", message.scenario).replace(
                    "[[project_id]]", str(message.project_id)
                )
            )
            .replace("[[requirement_id]]", str(message.id))
            .replace("[[task]]", message.task)
            .replace("[[description]]", message.description)
            .replace("[[creator]]", message.reviewer)
        )
        # 发送到前端提示
        await self.publish_message(
            ResponseMessage(
                source="user", content=f"收到用户指令，准备开始执行：{message.task}"
            ),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )
        testcase_generator_agent = AssistantAgent(
            name="testcase_generator_agent",
            model_client=model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )
        # 需要用户对生成的测试用例提出修改建议
        if self.input_func:
            user_proxy = UserProxyAgent(name="user_proxy", input_func=self.input_func)
            termination_en = TextMentionTermination("APPROVE")
            termination_zh = TextMentionTermination("同意")
            team = RoundRobinGroupChat(
                [testcase_generator_agent, user_proxy],
                termination_condition=termination_en | termination_zh,
            )

            stream = team.run_stream(task=message.task)
            testcase_content = ""  # 测试用例内容
            update_count = 0  # 测试用例更新次数
            # 存储测试用例修改记录
            testcase_modify_memory = ListMemory()
            async for msg in stream:
                # 模拟流式输出
                if isinstance(msg, ModelClientStreamingChunkEvent):
                    await self.publish_message(
                        ResponseMessage(source="用例生成智能体", content=msg.content),
                        topic_id=TopicId(
                            type=task_result_topic_type, source=self.id.key
                        ),
                    )
                    continue
                # 统计测试用例更新次数并保存生成的测试用例
                if isinstance(msg, TextMessage):
                    # 保存测试用例修改记录
                    await testcase_modify_memory.add(
                        MemoryContent(
                            content=msg.model_dump_json(), mime_type=MemoryMimeType.JSON
                        )
                    )
                    if msg.source == "testcase_generator_agent":
                        update_count += 1
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

            # 如果测试用例有更新，则整合修改的测试用例
            if update_count > 1:
                # 用例汇总智能体
                summarize_agent = AssistantAgent(
                    name="assistant_agent",
                    system_message="""你是一位测试用例整理优化专家，根据上下文对话信息，输出用户最终期望的优化后的测试用例。""",
                    model_client=model_client,
                    memory=[testcase_modify_memory],
                    model_client_stream=True,
                )
                stream = summarize_agent.run_stream(
                    task="结合上下文对话信息，参考指定格式输出优化后的完整测试用例"
                )
                async for msg in stream:
                    if isinstance(msg, ModelClientStreamingChunkEvent):
                        # 流式输出结果到前端界面
                        await self.publish_message(
                            ResponseMessage(
                                source="用例优化智能体", content=msg.content
                            ),
                            topic_id=TopicId(
                                type=task_result_topic_type, source=self.id.key
                            ),
                        )
                        continue
                    if isinstance(msg, TaskResult):
                        testcase_content = msg.messages[-1].content
                        continue
            # 发送给下一个智能体
            await self.publish_message(
                TestCaseMessage(source=self.id.type, content=testcase_content),
                topic_id=TopicId(testcase_review_topic_type, source=self.id.key),
            )
        else:
            # 用户不参与用例修改
            msg = await testcase_generator_agent.run(task=message.task)
            # 发送给下一个智能体
            await self.publish_message(
                TestCaseMessage(
                    source=msg.messages[-1].source, content=msg.messages[-1].content
                ),
                topic_id=TopicId(testcase_review_topic_type, source=self.id.key),
            )
            # 发送到前端提示
            await self.publish_message(
                ResponseMessage(
                    source="用例生成智能体", content=msg.messages[-1].content
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )


@type_subscription(topic_type=testcase_review_topic_type)
class TestCaseReviewAgent(RoutedAgent):
    def __init__(self):
        super().__init__("testcase review agent")
        self._prompt = """
        你是资深测试用例评审专家，关注用例质量与测试覆盖有效性。请根据用户提供的测试用例进行评审，给出评审意见及评审报告，markdown格式输出
        ## 1. 评审重点
        1. 需求覆盖度：确保每个需求点都有对应测试用例
        2. 测试深度：正常流/边界/异常流全面覆盖
        3. 用例可执行性：步骤清晰、数据明确
        ## 2. Background
        - **测试用例评审**是软件质量保障的关键环节，需确保测试用例覆盖需求、逻辑正确、可维护性强。
        - 评审工程师需基于行业规范、项目需求及测试经验，系统性识别测试用例中的缺陷或改进点。

        ## 3. Profile
        - **角色**: 资深测试用例评审工程师
        - **经验**: 8年以上测试设计与执行经验，熟悉敏捷/瀑布开发流程
        - **职责范围**:
          - 评审功能/性能/安全测试用例
          - 识别用例设计中的逻辑漏洞与冗余
          - 与开发/测试/产品团队协作优化用例

        ## 4. Skills
        - ✅ 精通等价类划分、边界值分析等测试方法
        - ✅ 熟悉TestRail/Jira/Xray等测试管理工具
        - ✅ 精准识别需求与用例的映射偏差
        - ✅ 逻辑分析能力与跨团队沟通能力
        - ✅ 对边界条件/异常流程高度敏感

        ## 5. Goals
        - **覆盖率审查**: 验证需求条目100%被测试用例覆盖
        - **正确性审查**: 检查测试步骤/预期结果是否符合业务逻辑
        - **可维护性审查**: 确保用例描述清晰、无歧义、参数可配置
        - **风险识别**: 标记高复杂度/高失败率用例
        - **可执行性审查**: 验证前置条件/测试数据可落地

        ## 6. Constrains
        - ❗ 不直接修改用例，仅提供改进建议
        - ❗ 关注用例文档质量，不涉及需求合理性评估
        - ❗ 单个用例评审时间不超过10分钟
        - ❗ 不承诺缺陷发现率指标

        ## 7. OutputFormat
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

        #### 3. 优先级矩阵
        | 紧急度 | 功能用例 | 非功能用例 |
        |--------|----------|------------|
        | 高     | [count]  | [count]    |
        | 中     | [count]  | [count]    |

        #### 4. 典型案例
        **用例ID**: TC_APP_Login_003
        **问题类型**: 边界值缺失
        **具体描述**: 未覆盖密码长度为[1,64]的边界校验
        **改进建议**: 增加密码长度为0/65的异常流测试用例

        #### 5. 总结建议
        - 关键风险点: [风险描述]
        - 后续行动计划: [action items]
        ```

        ## 8. Workflow
        1. **输入解析**
           - 解析测试用例文档与需求追踪矩阵(RTM)
           - 提取用例步骤/预期结果/关联需求ID

        2. **分类评审**
           ```mermaid
           graph TD
           A[需求覆盖审查] --> B[逻辑正确性审查]
           B --> C[可执行性审查]
           C --> D[可维护性审查]
           ```

        3. **问题识别**
           - 标记缺失的测试场景
           - 标注模糊的断言条件
           - 标识冗余的测试步骤

        4. **优先级划分**
           - P0: 导致流程阻断的缺陷
           - P1: 影响测试有效性的问题
           - P2: 优化类建议

        5. **案例生成**
           - 为每类问题提供典型示例
           - 包含具体定位与修复方案

        6. **总结建议**
           - 生成风险雷达图
           - 输出可量化的改进指标

        ## 9. Examples
        **场景1: 需求覆盖不足**
        - 需求ID: REQ_PAY_001
        - 缺失用例: 未验证支付金额为0元的异常场景
        - 建议: 新增TC_PAY_Edge_001验证0元支付异常提示

        **场景2: 步骤描述模糊**
        - 用例ID: TC_SEARCH_005
        - 问题描述: "输入多种关键词"未定义具体参数
        - 改进: 明确测试数据为["", "&*%", "中文+数字123"]

        **场景3: 缺乏异常处理**
        - 用例ID: TC_UPLOAD_012
        - 问题类型: 未包含网络中断重试机制验证
        - 建议: 添加模拟弱网环境的测试步骤
        """

    @message_handler
    async def handle_message(
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        agent = AssistantAgent(
            name="testcase_review_agent",
            model_client=model_client,
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
                    ResponseMessage(source="用例评审智能体", content=msg.content),
                    topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
                )
                continue
            if isinstance(msg, TaskResult):
                review_report = msg.messages[-1].content
                continue

        # 发送给下一个智能体
        await self.publish_message(
            TestCaseMessage(
                source=self.id.type,
                content="--测试用例开始-- \n"
                + message.content
                + "\n--测试用例结束-- \n"
                + "--评审报告开始-- \n"
                + review_report
                + "\n--评审报告结束-- \n",
            ),
            topic_id=TopicId(testcase_finalize_topic_type, source=self.id.key),
        )


@type_subscription(topic_type=testcase_finalize_topic_type)
class TestCaseFinalizeAgent(RoutedAgent):
    def __init__(self):
        super().__init__("testcase finalize agent")
        self._prompt = """
        请严格按如下JSON数组格式输出，必须满足:
        1.首尾无任何多余字符
        2.不使用Markdown代码块
        3.每个测试用例必须包含required字段
        根据用户提供的测试用例及评审报告，根据如下格式生成最终的高质量测试用例。（注意：只输出下面的内容本身，去掉首尾的 ```json 和 ```）：
        [{"$defs":{"TestStepBase":{"properties":{"description":{"description":"测试步骤的描述。","title":"Description","type":"string"},"expected_result":{"description":"测试步骤的预期结果。","title":"Expected Result","type":"string"}},"required":["description","expected_result"],"title":"TestStepBase","type":"object"}},"properties":{"title":{"description":"测试用例的标题。","maxLength":200,"title":"Title","type":"string"},"desc":{"default":null,"description":"测试用例的详细描述。","maxLength":1000,"title":"Desc","type":"string"},"priority":{"description":"测试用例的优先级：[高/中/低]","title":"Priority","type":"string"},"status":{"default":"未开始","description":"测试用例的当前状态：[未开始/进行中/通过/失败/阻塞]","title":"Status","type":"string"},"preconditions":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"测试用例的前置条件。","title":"Preconditions"},"postconditions":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"测试用例的后置条件。","title":"Postconditions"},"tags":{"anyOf":[{"type":"string"},{"type":"null"}],"description":"测试类型标签：[单元测试/接口测试/功能测试/性能测试/安全测试]","title":"Tags"},"requirement_id":{"description":"关联需求ID。","title":"Requirement Id","type":"integer","default":"[[requirement_id]]"},"project_id":{"description":"关联项目ID。","title":"Project Id","type":"integer","default":"[[project_id]]"},"creator":{"default":"田威峰","description":"测试用例的创建者姓名。","maxLength":100,"title":"Creator","type":"string"},"steps":{"anyOf":[{"items":{"$ref":"#/$defs/TestStepBase"},"type":"array"},{"type":"null"}],"default":null,"description":"测试步骤列表。","title":"Steps"}},"required":["title","priority","tags","requirement_id","project_id"],"title":"CaseCreate","type":"object"}]
        """

    @message_handler
    async def handle_message(
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        agent = AssistantAgent(
            name="testcase_finalize_agent",
            model_client=model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )
        stream = agent.run_stream(
            task="根据如下测试用例及评审报告，输出高质量测试用例。测试用例及评审报告如下：\n"
            + message.content
            + "\n"
        )
        final_testcase = ""
        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                # 流式输出结果到前端界面
                await self.publish_message(
                    ResponseMessage(source="用例结构化智能体", content=msg.content),
                    topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
                )
                continue
            if isinstance(msg, TaskResult):
                final_testcase = msg.messages[-1].content
                continue
        # 发送给下一个智能体
        await self.publish_message(
            TestCaseMessage(source=self.id.type, content=final_testcase),
            topic_id=TopicId(testcase_database_topic_type, source=self.id.key),
        )


@type_subscription(topic_type=testcase_structure_topic_type)
class TestCaseStructureAgent(RoutedAgent):
    def __init__(self, model: OpenAIModel = None):
        super().__init__("testcase structure agent")
        self._prompt = """
        注意：将测试用例以如下格式输出，别无其他。
        [{"$defs":{"TestStepBase":{"properties":{"description":{"description":"测试步骤的描述。","title":"Description","type":"string"},"expected_result":{"description":"测试步骤的预期结果。","title":"Expected Result","type":"string"}},"required":[]]"""
        self.model = model
        if model is None:
            self.model = OpenAIModel(
                "deepseek-chat",
                base_url="https://api.deepseek.com",
                api_key="sk-3f0a16cad7ff45f1a0596c13cc489e23",
            )

    @message_handler
    async def handle_message(
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        await self.publish_message(
            ResponseMessage(
                source="用例结构化智能体", content="正在对测试用例结构化......"
            ),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )

        # agent = Agent(self.model, result_type=TestCaseList)
        # result = await agent.run(user_prompt=f"对下面内容进行结构化:\n{message.content}")
        # 由于可以直接结构化，所以直接返回json格式的测试用例列表
        # test_case_list = TestCaseList(testcases=json.loads(message.content))

        agent = AssistantAgent(
            name="testcase_structure_agent",
            model_client=model_client,
            system_message=self._prompt,
            model_client_stream=False,
        )
        msg = await agent.run(task=f"对如下测试用例进行结构化:\n{message.content}")

        await self.publish_message(
            ResponseMessage(source="用例结构化智能体", content="测试用例结构化完成。"),
            topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
        )

        # 发送给下一个智能体
        await self.publish_message(
            TestCaseMessage(source=self.id.type, content=msg.messages[-1].content),
            topic_id=TopicId(testcase_database_topic_type, source=self.id.key),
        )


@type_subscription(topic_type=testcase_database_topic_type)
class TestCaseDatabaseAgent(RoutedAgent):
    def __init__(self):
        super().__init__("testcase database agent")

    @message_handler
    async def handle_message(
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        try:
            await self.publish_message(
                ResponseMessage(
                    source="数据库智能体", content="正在进行数据验证......"
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )
            test_case_list = TestCaseList(testcases=json.loads(message.content))
            for testcase in test_case_list.testcases:
                logger.info(f"测试用例: {testcase}")
                try:
                    await testcase_controller.create_TestCase(testcase)
                except Exception as e:
                    logger.error(f"测试用例入库失败：{str(e)}")

            await self.publish_message(
                ResponseMessage(
                    source="database",
                    content=test_case_list.model_dump_json(),
                    is_final=False,
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )

            await self.publish_message(
                ResponseMessage(
                    source="数据库智能体",
                    content=f"测试用例入库完成，共生成【{len(test_case_list.testcases)}】条测试用例。",
                    is_final=True,
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )
        except Exception as e:
            await self.publish_message(
                ResponseMessage(
                    source="数据库智能体",
                    content=f"测试用例入库失败：{str(e)}",
                    is_final=True,
                ),
                topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            )


async def start_runtime(
    requirement: RequirementMessage,
    collect_result: Callable[
        [ClosureContext, ResponseMessage, MessageContext], Awaitable[None]
    ],
    user_input_func: Callable[[str, Optional[CancellationToken]], Awaitable[str]],
):

    runtime = SingleThreadedAgentRuntime()
    await TestCaseGeneratorAgent.register(
        runtime,
        testcase_generator_topic_type,
        lambda: TestCaseGeneratorAgent(input_func=user_input_func),
    )
    await TestCaseReviewAgent.register(
        runtime, testcase_review_topic_type, lambda: TestCaseReviewAgent()
    )
    await TestCaseFinalizeAgent.register(
        runtime, testcase_finalize_topic_type, lambda: TestCaseFinalizeAgent()
    )
    await TestCaseStructureAgent.register(
        runtime, testcase_structure_topic_type, lambda: TestCaseStructureAgent()
    )
    await TestCaseDatabaseAgent.register(
        runtime, testcase_database_topic_type, lambda: TestCaseDatabaseAgent()
    )

    # 定义一个专门用来接收其它agent的消息的智能体，只需要定义一个接收消息的函数即可
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
    runtime.start()
    await runtime.publish_message(
        requirement, topic_id=DefaultTopicId(type=testcase_generator_topic_type)
    )
    await runtime.stop_when_idle()
    await runtime.close()
