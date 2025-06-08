import asyncio
import re

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import (
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
    ToolCallSummaryMessage,
)

from examples.llms import openai_model_client


async def count_chinese_characters(text: str):
    """统计中文字符个数"""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


counter_agent = AssistantAgent(
    "counter",
    model_client=openai_model_client,
    system_message="通过调用工具统计测试用例的字数",
    tools=[count_chinese_characters],
    reflect_on_tool_use=False,  # 对函数调用的结果进行二次推理（大模型），使工具调用的结果输出更人性化（表达更有意义）例如：True--测试用例中的中文字符总数为：235字
    model_client_stream=True,
)


async def main():
    async for event in counter_agent.run_stream(
        task="""统计下面文字的字数
    用户登录   | 高     | 功能测试   | 验证有效用户名密码登录成功   | 1. 系统运行正常<br>2. 测试用户已注册(用户名:testuser,密码:Test@123) | 1. 打开登录页面<br>2. 输入已注册用户名"testuser"<br>3. 输入正确密码"Test@123"<br>4. 点击"登录"按钮 | 1. 登录成功<br>2. 跳转至用户首页<br>3. 显示欢迎信息"欢迎回来,testuser" |          |\n| TC-LOGIN-002    | 用户登录   | 高     | 边界测试   | 验证密码错误处理机制         | 1. 系统运行正常<br>2. 测试用户已注册(用户名:testuser,密码:Test@123) | 1. 打开登录页面<br>2. 输入已注册用户名"testuser"<br>3. 输入错误密码"Wrong@123"<br>4. 点击"登录"按钮 | 1. 登录失败<br>2. 显示错误提示"用户名或密码错误"<br>3. 密码输入框清空并获取焦点<br>4. 错误计数器+1 |          |\n| TC-LOGIN-003    | 用户登录   | 中     | 异常测试   | 验证连续5次错误密码账户锁定  | 1. 系统运行正常<br>2. 测试账户未锁定<br>3. 错误计数器初始为0 | 1. 重复执行TC-LOGIN-002操作5次<
    """
    ):

        if isinstance(event, ToolCallRequestEvent):  # 发起函数调用
            pass
        if isinstance(event, ToolCallExecutionEvent):  # 函数调用完成
            pass
        if isinstance(event, ToolCallSummaryMessage):  # 函数调用结果
            pass

        if isinstance(event, TaskResult):  # 获取对话的所有内容
            print(event.messages[-1].content)
        print(event)


asyncio.run(main())
