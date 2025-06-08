import asyncio

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import ExternalTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat

from examples.llms import openai_model_client

"""
实现一个功能，让AI编写一首诗，你提出见生成，直到你同意为止

"""

story_agent = AssistantAgent(
    "story",
    model_client=openai_model_client,
    system_message="你是一名闷骚的极具才华的诗人，可以为用户编写出脍炙人口的诗句来",
)

user_review = UserProxyAgent("user_proxy", description="评审诗句", input_func=input)

termination = TextMentionTermination("同意")

team = RoundRobinGroupChat(
    [story_agent, user_review], termination_condition=termination
)


async def main():
    async for i in team.run_stream(task="编写一首七言绝句"):
        print(i)


if __name__ == "__main__":
    asyncio.run(main())
