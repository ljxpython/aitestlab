import asyncio
from dataclasses import dataclass
from typing import Any, Optional

import aiofiles
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
from sympy import content

from examples.llms import openai_model_client

"""
编写一首七言绝句诗（智能体1），
有一个智能体进行评价（智能体2），
评价后发送给用户，用户提出意见（user_proxy），
根据意见优化古诗(智能体3)
，直到同意（终止条件）

过程中将每次的结果进行收集，写入到一个data.txt的文本中（收集结果智能体）

"""

# 定义topic_type
write_story_topic_type = "write_story"
review_story_topic_type = "review_story"
change_story_topic_type = "change_story"


# 定义消息数据类型
class WriteStory(BaseModel):
    user_req: str = Field(..., description="用户编写古诗的需求")


class ReviewStory(BaseModel):
    # task:str = Field(...,description="评审古诗的标准")
    content: str = Field(..., description="古诗的内容")


class ChangeStory(BaseModel):
    task: str = Field(..., description="修改古诗的要求")


# 定义智能体及标注其订阅的消息类型


@type_subscription(topic_type=write_story_topic_type)
class WriteStoryAgent(RoutedAgent):

    def __init__(self, description):
        super().__init__(description=description)
        self._prompt = """
        你是一位非常闷骚的诗人，写的古诗非常通俗易懂且幽默风趣
        """

    @message_handler
    async def message(self, message: WriteStory, ctx: MessageContext) -> None:
        agent = AssistantAgent(
            name="write_story",
            model_client=openai_model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )
        # 等到用户输入需求
        print("请输入你需要生成的古诗")
        # req = UserProxyAgent(
        #     name='story_content',
        #     input_func=input
        # )
        req = input("你想要生成什么样的古诗:")
        message = WriteStory(user_req=req)

        user_req = message.user_req
        result = ""
        stream = agent.run_stream(task=user_req)
        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                # 记录到消息收集体中
                pass
            if isinstance(msg, TextMessage):
                # 发送给消息智能体
                await self.publish_message(
                    message=TaskResponse(content=str(msg), agent="write_agent"),
                    topic_id=TopicId(type=TASK_RESULTS_TOPIC_TYPE, source=self.id.key),
                )
            if isinstance(msg, TaskResult):
                result = msg.messages[-1].content
        logger.info(result)

        # 发送给下一个智能体
        await self.publish_message(
            message=ReviewStory(content=result),
            topic_id=TopicId(type=review_story_topic_type, source=self.id.key),
        )


@type_subscription(topic_type=review_story_topic_type)
class ReviewAgent(RoutedAgent):

    def __init__(self, description):
        super().__init__(description=description)
        self._prompt = """
        你是一位古诗鉴赏大师，具有批判性思维，可以给古诗提出建设性的修改意见,当收到用户的古诗活，先点评古诗之后给出修改后的古诗
        """

    @message_handler
    async def handle_message(self, message: ReviewStory, ctx: MessageContext) -> None:
        agent = AssistantAgent(
            name="review_story",
            model_client=openai_model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )
        user_app = UserProxyAgent(name="user_approve", input_func=input)
        content = message.content
        result = ""
        team = RoundRobinGroupChat(
            [agent, user_app], termination_condition=TextMentionTermination("同意")
        )
        stream = team.run_stream(task=content)
        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                logger.info(msg)
            if isinstance(msg, TextMessage):
                logger.info(msg)
                # 发送给消息智能体
                await self.publish_message(
                    message=TaskResponse(content=str(msg), agent="write_agent"),
                    topic_id=TopicId(type=TASK_RESULTS_TOPIC_TYPE, source=self.id.key),
                )
            if isinstance(msg, TaskResult):
                result = msg.messages[-1].content
                logger.info(result)
            if isinstance(msg, UserInputRequestedEvent):
                # continue
                logger.info(msg)


# 消息收集中的智能体
CLOSURE_AGENT_TYPE = "collect_result_agent"
TASK_RESULTS_TOPIC_TYPE = "task-results"


class TaskResponse(BaseModel):
    content: str = Field(..., description="智能体返回的内容")
    agent: str = Field(..., description="智能体名称")


async def collect_result(
    _agent: ClosureContext, message: TaskResponse, ctx: MessageContext
) -> None:
    async with aiofiles.open(file="data.txt", mode="a+", encoding="utf-8") as f:
        await f.write(f"agent:{message.agent}\n")
        await f.write(f"content:{message.content}\n")


# 编写运行体
async def start_runtime():
    # 实例化运行时
    runtime = SingleThreadedAgentRuntime()
    # 智能体（topic）注册到运行时中
    await WriteStoryAgent.register(
        runtime,
        write_story_topic_type,
        lambda: WriteStoryAgent(description="诗歌智能体"),
    )
    await ReviewAgent.register(
        runtime,
        review_story_topic_type,
        lambda: ReviewAgent(description="诗歌评审智能体"),
    )
    # 收集消息智能体
    await ClosureAgent.register_closure(
        runtime,
        CLOSURE_AGENT_TYPE,
        collect_result,
        subscriptions=lambda: [
            TypeSubscription(
                topic_type=TASK_RESULTS_TOPIC_TYPE, agent_type=CLOSURE_AGENT_TYPE
            )
        ],
    )
    # 开启运行时
    runtime.start()
    # 发布消息
    await runtime.publish_message(
        WriteStory(user_req=""), topic_id=DefaultTopicId(type=write_story_topic_type)
    )
    # 等待完成
    await runtime.stop_when_idle()
    # 关闭运行时
    await runtime.close()


if __name__ == "__main__":
    asyncio.run(start_runtime())
