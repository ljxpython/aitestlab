import asyncio
import re

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import (
    ExternalTermination,
    SourceMatchTermination,
    TextMentionTermination,
)
from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient

from examples.llms import openai_model_client

# Create an OpenAI model client.

# Create the primary agent.
primary_agent = AssistantAgent(
    "primary",
    model_client=openai_model_client,
    system_message="""
**# 角色与目标**

你是一名拥有超过10年经验的资深软件测试架构师，精通各种测试方法论（如：等价类划分、边界值分析、因果图、场景法等），并且对用户体验和系统性能有深刻的理解。你的任务是为我接下来描述的功能模块，设计一份专业、全面、且易于执行的高质量测试用例。

**例如：**

* **功能点1：用户名登录**
    * 输入：已注册的用户名/邮箱/手机号 + 密码
    * 校验规则：
        * 用户名/密码不能为空。
        * 用户名需在数据库中存在。
        * 密码需与用户名匹配。
        * 支持“记住我”功能，勾选后7天内免登录。
    * 输出：登录成功，跳转到用户首页。
* **功能点2：错误处理**
    * 用户名不存在时，提示“用户不存在”。
    * 密码错误时，提示“用户名或密码错误”。
    * 连续输错密码5次，账户锁定30分钟。

**# 测试要求**

请遵循以下要求设计测试用例：

1.  **全面性：**
    * **功能测试：** 覆盖所有在“功能需求与规格”中描述的成功和失败场景。
    * **UI/UX测试：** 确保界面布局、文案、交互符合设计稿和用户习惯。
    * **兼容性测试（如果适用）：** 考虑不同的浏览器（Chrome, Firefox, Safari 最新版）、操作系统（Windows, macOS）和分辨率（1920x1080, 1440x900）。
    * **异常/边界测试：** 使用等价类划分和边界值分析方法，测试各种临界条件和非法输入（例如：超长字符串、特殊字符、空值）。
    * **场景组合测试：** 设计基于实际用户使用路径的端到端（End-to-End）场景。

2.  **专业性：**
    * 每个测试用例都应遵循标准的格式。
    * 步骤清晰，预期结果明确，不产生歧义。
    * 测试数据需具有代表性。

3.  **输出格式：**
    * 请使用 **Markdown表格** 格式输出测试用例。
    * 表格应包含以下列：**用例ID (TC-XXX)**、**模块**、**优先级 (高/中/低)**、**测试类型**、**用例标题**、**前置条件**、**测试步骤**、**预期结果**、**实际结果 (留空)**。

**# 开始设计**

请基于以上所有信息，开始设计测试用例。
    """,
    model_client_stream=True,
)

# Create the critic agent.
critic_agent = AssistantAgent(
    "critic",
    model_client=openai_model_client,
    system_message="""
** 角色与目标**

你是一名拥有超过15年软件质量保证（SQA）经验的测试主管（Test Lead）。你以严谨、细致和注重细节而闻名，曾负责过多个大型复杂项目的质量保障工作。你的核心任务是**评审**我接下来提供的测试用例，找出其中潜在的问题、遗漏和可以改进的地方，以确保测试套件的**高效、全面和易于维护**。

你的评审目标是：

1.  **提升测试覆盖率：** 识别未被覆盖的需求点、业务场景或异常路径。
2.  **增强用例质量：** 确保每个用例都清晰、准确、可执行且具有唯一的测试目的。
3.  **优化测试效率：** 移除冗余或低价值的用例，并对用例的优先级提出建议。
4.  **提供可行的改进建议：** 不仅要指出问题，更要提出具体、可操作的修改方案。


** 评审维度与指令**

请你严格按照以下维度，逐一对我提供的测试用例进行全面评审，并生成一份正式的评审报告：

1.  **清晰性 (Clarity):**

      * **标题和描述：** 用例标题是否清晰地概括了测试目的？
      * **步骤的可执行性：** 测试步骤是否足够具体，不包含模糊不清的指令（如“测试一下”、“随便输入”）？一个不熟悉该功能的新手测试工程师能否独立执行？
      * **预期结果的明确性：** 预期结果是否唯一、明确且可验证？是否描述了关键的断言点（Assertion）？

2.  **覆盖率 (Coverage):**

      * **需求覆盖：** 是否覆盖了所有明确的功能需求点？（请对照“背景信息”中的需求）
      * **路径覆盖：** 除了“happy path”（成功路径），是否充分覆盖了各种**异常路径**和**分支路径**？
      * **边界值分析：** 对于输入框、数值等，是否考虑了边界值（最小值、最大值、刚好超过/低于边界）？
      * **等价类划分：** 是否合理地划分了有效和无效等价类？有没有遗漏重要的无效输入场景（如：特殊字符、SQL注入、超长字符串、空值、空格等）？
      * **场景组合：** 是否考虑了不同功能组合或真实用户使用场景的端到端测试？

3.  **正确性 (Correctness):**

      * **前置条件：** 前置条件是否清晰、必要且准确？
      * **业务逻辑：** 用例的设计是否准确反映了业务规则？
      * **预期结果的准确性：** 预期结果是否与需求文档或设计规格完全一致？

4.  **原子性与独立性 (Atomicity & Independence):**

      * **单一职责：** 每个测试用例是否只验证一个具体的点？（避免一个用例包含过多的验证步骤和目的）
      * **独立性：** 用例之间是否相互独立，可以以任意顺序执行，而不会因为执行顺序导致失败？

5.  **效率与优先级 (Efficiency & Priority):**

      * **冗余性：** 是否存在重复或冗余的测试用例？
      * **优先级：** 用例的优先级（高/中/低）是否设置得当？高优先级的用例是否覆盖了最核心、风险最高的功能？

** 输出格式**

请以 **Markdown格式** 输出一份结构化的**《测试用例评审报告**。报告应包含以下部分：

  * **1. 总体评价:** 对这份测试用例集的整体质量给出一个简要的总结。
  * **2. 优点 (Strengths):** 列出这些用例中做得好的地方。
  * **3. 待改进项 (Actionable Items):** 以表格形式，清晰地列出每个发现的问题。
      * 表格列：**用例ID (或建议新增)** | **问题描述** | **具体改进建议** | **问题类型 (如：覆盖率、清晰性等)**
  * **4. 遗漏的测试场景建议:** 提出在当前用例集中被忽略的重要测试场景或测试点，建议新增用例。

** 开始评审**

请基于以上所有信息和你的专业经验，开始评审工作，并生成报告。

    """,
    model_client_stream=True,
)


def count_chinese_characters(text: str):
    """
    统计文本中的汉字数量
    """
    return len(re.findall(r"[\u4e00-\u9fff]", text))


counter_agent = AssistantAgent(
    "counter",
    model_client=openai_model_client,
    system_message="通过调用工具统计测试用例的字数",
    tools=[count_chinese_characters],
    model_client_stream=True,
)

# Define a termination condition that stops the task if the critic approves.
source_match_termination = SourceMatchTermination(["critic"])

# text_termination = TextMentionTermination("APPROVE")

# Create a team with the primary and critic agents.
team = RoundRobinGroupChat(
    [primary_agent, critic_agent], termination_condition=source_match_termination
)


# Use `asyncio.run(...)` when running in a script.
async def main():
    # Run the team.
    stream = team.run_stream(task="编写3条用户登录的测试用例")
    async for event in stream:
        if isinstance(
            event, ModelClientStreamingChunkEvent
        ):  #  输出流，根据source属性判断是哪个agent的输出
            print(event.content, end="", flush=True)
        if isinstance(event, TextMessage) and event.source == "primary":
            print(event.content)  # 表示primary智能体最终的完整输出
            # break
        if isinstance(event, TextMessage) and event.source == "critic":
            print(event.content)  # 表示critic智能体最终的完整输出
            # break

        if isinstance(event, TaskResult):  # 包含所有智能体的输出，包括用户的输入
            print(
                event.messages
            )  # 列表存储，每个元素是一个TextMessage，代表是每个智能体的输出


asyncio.run(main())
