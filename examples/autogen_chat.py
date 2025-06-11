import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage
from autogen_agentchat.ui import Console
from llms import openai_model_client

agent = AssistantAgent(
    name="reporter_agent",
    model_client=openai_model_client,
    system_message="你擅长编写古诗",
    model_client_stream=True,  # 支持流式输出
)


# await 不能直接写在模块中
# 如果函数中调用了协程函数，那么当前函数必须声明为协程函数
async def main():
    result = await agent.run(task="编写一首4言古诗")  # 等待run方法执行完成后返回结果
    print(result)


async def main_stream():
    # 获取协程对象
    result = agent.run_stream(
        task="编写一首4言古诗"
    )  # 当前代码不会执行run_stream()中的代码,直接返回协程对象
    async for item in result:
        if isinstance(item, ModelClientStreamingChunkEvent):
            print(item.content, end="", flush=True)  ## 流式输出
        if isinstance(item, TextMessage):
            print(item.content)  # 表示primary智能体最终的完整输出
        if isinstance(item, TaskResult):
            print(item.messages[0].content)  # 记录user的输入
            print(item.messages[-1].content)  # 表示primary智能体最终的完整输出


async def main_console():
    await Console(agent.run_stream(task="编写一首4言古诗"))


asyncio.run(main_stream())
