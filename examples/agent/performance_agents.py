import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.api.v1.agent.api.llms import model_client
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import ModelClientStreamingChunkEvent
from autogen_core import (
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
from pydantic import BaseModel, Field

# 定义主题类型
performance_analyzer_topic_type = "performance_analyzer"
performance_bottleneck_topic_type = "performance_bottleneck"
performance_recommendation_topic_type = "performance_recommendation"
performance_summary_topic_type = "performance_summary"
performance_result_topic_type = "performance_result"

# 全局消息队列，用于向前端推送消息
result_queue = asyncio.Queue()


class PerformanceMetric(BaseModel):
    """性能指标模型"""

    name: str = Field(..., description="指标名称")
    value: str = Field(..., description="当前值")
    benchmark: str = Field(..., description="基准值")
    status: str = Field(..., description="状态：良好、一般、差")
    percentOfBenchmark: Optional[float] = Field(None, description="与基准值的百分比")


class PerformanceBottleneck(BaseModel):
    """性能瓶颈模型"""

    id: str = Field(..., description="唯一标识")
    type: str = Field(..., description="瓶颈类型")
    description: str = Field(..., description="问题描述")
    impact: str = Field(..., description="影响")
    location: str = Field(..., description="问题位置")
    severity: str = Field(..., description="严重程度：严重、中等、轻微")


class PerformanceRecommendation(BaseModel):
    """性能优化建议模型"""

    id: str = Field(..., description="唯一标识")
    title: str = Field(..., description="建议标题")
    description: str = Field(..., description="建议描述")
    implementation: str = Field(..., description="实施方法")
    impact: str = Field(..., description="预期影响")
    impact_level: str = Field(..., description="影响等级：高、中、低")


class PerformanceAnalysisResult(BaseModel):
    """性能分析结果模型"""

    summary: Dict[str, Any] = Field(..., description="性能概览")
    bottlenecks: List[PerformanceBottleneck] = Field(..., description="性能瓶颈列表")
    recommendations: List[PerformanceRecommendation] = Field(
        ..., description="优化建议列表"
    )
    metrics: Dict[str, Any] = Field(..., description="性能指标数据")
    charts: List[Dict[str, Any]] = Field([], description="可视化图表数据")


class ResponseMessage(BaseModel):
    """响应消息模型"""

    source: str = Field(..., description="消息来源")
    content: str = Field(..., description="消息内容")
    is_final: bool = Field(False, description="是否为最终结果")
    result: Optional[Dict[str, Any]] = Field(None, description="分析结果")


@dataclass
class PerformanceMessage:
    """性能分析消息"""

    source: str
    content: Any


@type_subscription(topic_type=performance_analyzer_topic_type)
class PerformanceAnalyzerAgent(RoutedAgent):
    """性能分析主智能体"""

    def __init__(self):
        super().__init__("performance analyzer agent")

        self._prompt = """
        你是一位资深的性能分析工程师，专注于分析各类性能测试报告并提供专业的性能瓶颈分析。

        ## 角色背景
        - **专业背景**: 拥有10年性能测试和性能优化经验，熟悉各种性能指标和测试工具
        - **技术专长**: 精通JMeter、LoadRunner、Lighthouse、WebPageTest等性能测试工具
        - **行业经验**: 服务过电商、金融、政企等多个领域的大型系统性能优化项目

        ## 核心能力
        - 全面解读性能测试报告中的关键指标
        - 精准定位系统性能瓶颈和根本原因
        - 提供针对性的性能优化建议
        - 评估每个性能问题的业务影响

        ## 分析流程
        1. **报告解析**：理解性能报告格式和包含的指标数据
        2. **指标评估**：对比行业标准评估各项指标的健康程度
        3. **瓶颈识别**：基于指标异常定位主要性能问题
        4. **根因分析**：通过数据关联和模式识别，确定瓶颈根因
        5. **优化建议**：提供有针对性的改进方案

        ## 关注指标
        - **响应时间**：页面加载时间、首次内容绘制、首次交互时间等
        - **资源消耗**：CPU使用率、内存占用、磁盘I/O、网络带宽等
        - **并发能力**：并发用户数、TPS/QPS、错误率等
        - **瓶颈点**：慢SQL、API延迟、资源限制、代码效率等

        ## 输出要求
        根据上传的性能报告，提供详细分析，包括：
        1. 性能总览评估
        2. 关键性能指标解读
        3. 主要瓶颈点列表及严重程度
        4. 每个瓶颈的详细分析
        5. 针对性优化建议

        请对性能报告进行全面分析，重点关注影响用户体验的关键指标，并提供专业的瓶颈诊断和优化建议。
        """

    @message_handler
    async def handle_message(self, message: str, ctx: MessageContext) -> None:
        """处理性能报告分析请求"""
        file_path = message

        # 向前端发送开始分析的消息
        await self.publish_message(
            ResponseMessage(source="性能分析智能体", content="开始分析性能报告文件..."),
            topic_id=TopicId(type=performance_result_topic_type, source=self.id.key),
        )

        # 读取性能报告文件
        try:
            file_content = self._read_performance_file(file_path)

            # 创建性能分析智能体
            analyzer_agent = AssistantAgent(
                name="performance_analyzer",
                model_client=model_client,
                system_message=self._prompt,
                model_client_stream=True,
            )

            # 向前端发送正在分析的消息
            await self.publish_message(
                ResponseMessage(source="性能分析智能体", content="正在解析性能数据..."),
                topic_id=TopicId(
                    type=performance_result_topic_type, source=self.id.key
                ),
            )

            # 执行性能分析
            analysis_task = f"请分析以下性能报告，识别关键性能指标、主要瓶颈点和可能的优化方向:\n\n{file_content}"

            # 流式输出
            stream = analyzer_agent.run_stream(task=analysis_task)
            analysis_content = ""

            async for msg in stream:
                if isinstance(msg, ModelClientStreamingChunkEvent):
                    # 流式输出到前端
                    await self.publish_message(
                        ResponseMessage(source="性能分析智能体", content=msg.content),
                        topic_id=TopicId(
                            type=performance_result_topic_type, source=self.id.key
                        ),
                    )
                    continue

                if isinstance(msg, TaskResult):
                    analysis_content = msg.messages[-1].content

            # 发送分析结果给瓶颈分析智能体
            await self.publish_message(
                PerformanceMessage(source=self.id.type, content=analysis_content),
                topic_id=TopicId(performance_bottleneck_topic_type, source=self.id.key),
            )

        except Exception as e:
            # 发送错误消息
            await self.publish_message(
                ResponseMessage(
                    source="性能分析智能体", content=f"分析过程中出错: {str(e)}"
                ),
                topic_id=TopicId(
                    type=performance_result_topic_type, source=self.id.key
                ),
            )

    def _read_performance_file(self, file_path: str) -> str:
        """读取性能报告文件内容"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == ".json" or file_ext == ".har":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return json.dumps(data, indent=2, ensure_ascii=False)

            elif file_ext == ".html":
                # 对于HTML文件，可以提取关键内容
                from bs4 import BeautifulSoup

                with open(file_path, "r", encoding="utf-8") as f:
                    soup = BeautifulSoup(f.read(), "html.parser")
                    # 尝试提取性能数据（这里是简化的示例）
                    performance_data = soup.find_all(
                        class_=["performance", "metrics", "results"]
                    )
                    if performance_data:
                        return "\n".join([div.get_text() for div in performance_data])
                    else:
                        return soup.get_text()

            else:  # 其他格式文件直接读取文本内容
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()

        except Exception as e:
            return f"文件读取错误: {str(e)}"


@type_subscription(topic_type=performance_bottleneck_topic_type)
class PerformanceBottleneckAgent(RoutedAgent):
    """性能瓶颈分析智能体"""

    def __init__(self):
        super().__init__("performance bottleneck agent")

        self._prompt = """
        你是一位精通性能瓶颈分析的专家，专注于从性能数据中识别和定位系统瓶颈。

        ## 角色定位
        - **专长**：性能瓶颈识别与根因分析
        - **背景**：拥有丰富的分布式系统性能调优和问题排查经验
        - **能力**：能够从复杂的性能数据中精确识别影响系统表现的关键瓶颈

        ## 分析方法
        1. **模式识别**：识别典型的性能瓶颈模式（如I/O阻塞、CPU饱和、内存泄漏等）
        2. **异常检测**：发现偏离正常范围的性能指标
        3. **相关性分析**：关联多个指标找出根本原因
        4. **瓶颈分级**：根据严重程度和业务影响对瓶颈进行分级

        ## 关注维度
        - **前端性能**：页面加载时间、渲染性能、JavaScript执行效率
        - **网络性能**：请求延迟、吞吐量、连接数、数据传输效率
        - **服务器性能**：CPU使用率、内存占用、I/O操作、线程状态
        - **数据库性能**：查询执行时间、锁竞争、索引使用情况

        ## 输出要求
        分析性能报告，识别并详细描述所有性能瓶颈，包括：
        1. 瓶颈类型（前端/网络/服务器/数据库等）
        2. 瓶颈详细描述
        3. 瓶颈发生的位置或组件
        4. 瓶颈的严重程度（严重/中等/轻微）
        5. 瓶颈对系统性能的具体影响

        请确保每个瓶颈描述清晰具体，便于后续优化工作。严重性评级应基于性能偏差幅度和业务影响程度综合考量。
        """

    @message_handler
    async def handle_message(
        self, message: PerformanceMessage, ctx: MessageContext
    ) -> None:
        """处理性能瓶颈分析请求"""
        await self.publish_message(
            ResponseMessage(source="瓶颈分析智能体", content="开始分析性能瓶颈..."),
            topic_id=TopicId(type=performance_result_topic_type, source=self.id.key),
        )

        # 创建瓶颈分析智能体
        bottleneck_agent = AssistantAgent(
            name="performance_bottleneck_analyzer",
            model_client=model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        # 分析任务
        analysis_task = (
            f"根据以下性能分析结果，识别并详细描述主要性能瓶颈:\n\n{message.content}"
        )

        # 流式输出
        stream = bottleneck_agent.run_stream(task=analysis_task)
        bottleneck_content = ""

        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                # 流式输出到前端
                await self.publish_message(
                    ResponseMessage(source="瓶颈分析智能体", content=msg.content),
                    topic_id=TopicId(
                        type=performance_result_topic_type, source=self.id.key
                    ),
                )
                continue

            if isinstance(msg, TaskResult):
                bottleneck_content = msg.messages[-1].content

        # 发送瓶颈分析结果给优化建议智能体
        await self.publish_message(
            PerformanceMessage(
                source=self.id.type,
                content={
                    "analysis": message.content,
                    "bottlenecks": bottleneck_content,
                },
            ),
            topic_id=TopicId(performance_recommendation_topic_type, source=self.id.key),
        )


@type_subscription(topic_type=performance_recommendation_topic_type)
class PerformanceRecommendationAgent(RoutedAgent):
    """性能优化建议智能体"""

    def __init__(self):
        super().__init__("performance recommendation agent")

        self._prompt = """
        你是一位经验丰富的性能优化专家，擅长针对已识别的性能瓶颈提供精准的优化建议。

        ## 角色背景
        - **专业经验**：10年以上全栈性能优化经验，覆盖前端、后端、数据库和基础设施
        - **技术领域**：精通各类性能优化技术和最佳实践
        - **行业洞察**：了解不同场景下的性能优化权衡与投入产出比

        ## 优化方法论
        1. **根因导向**：针对瓶颈根因提供直接解决方案
        2. **分层优化**：从应用架构、代码实现到系统配置的多层次优化
        3. **成本效益**：考虑实施复杂度与性能提升的平衡
        4. **长期规划**：区分快速修复与结构性优化建议

        ## 优化领域
        - **前端优化**：资源加载策略、渲染性能、JavaScript执行效率
        - **后端优化**：服务架构、缓存策略、异步处理、资源管理
        - **数据库优化**：查询优化、索引设计、数据结构调整
        - **网络优化**：CDN应用、协议优化、数据压缩
        - **系统优化**：负载均衡、水平扩展、资源配置调优

        ## 输出要求
        针对每个已识别的性能瓶颈，提供详细的优化建议，包括：
        1. 建议的标题和简要描述
        2. 具体实施方法
        3. 预期性能改善效果
        4. 实施复杂度评估
        5. 优先级建议

        确保建议具有可操作性，提供足够的技术细节以便实施。优先推荐投入产出比高的优化方案。
        """

    @message_handler
    async def handle_message(
        self, message: PerformanceMessage, ctx: MessageContext
    ) -> None:
        """处理性能优化建议请求"""
        await self.publish_message(
            ResponseMessage(source="优化建议智能体", content="正在生成优化建议..."),
            topic_id=TopicId(type=performance_result_topic_type, source=self.id.key),
        )

        # 创建优化建议智能体
        recommendation_agent = AssistantAgent(
            name="performance_recommendation_agent",
            model_client=model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        # 提取内容
        analysis_content = message.content["analysis"]
        bottleneck_content = message.content["bottlenecks"]

        # 分析任务
        recommendation_task = f"""
        根据以下性能分析结果和已识别的性能瓶颈，为每个瓶颈提供具体可行的优化建议:

        ## 性能分析
        {analysis_content}

        ## 已识别的瓶颈
        {bottleneck_content}
        """

        # 流式输出
        stream = recommendation_agent.run_stream(task=recommendation_task)
        recommendation_content = ""

        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                # 流式输出到前端
                await self.publish_message(
                    ResponseMessage(source="优化建议智能体", content=msg.content),
                    topic_id=TopicId(
                        type=performance_result_topic_type, source=self.id.key
                    ),
                )
                continue

            if isinstance(msg, TaskResult):
                recommendation_content = msg.messages[-1].content

        # 发送优化建议结果给总结智能体
        await self.publish_message(
            PerformanceMessage(
                source=self.id.type,
                content={
                    "analysis": analysis_content,
                    "bottlenecks": bottleneck_content,
                    "recommendations": recommendation_content,
                },
            ),
            topic_id=TopicId(performance_summary_topic_type, source=self.id.key),
        )


@type_subscription(topic_type=performance_summary_topic_type)
class PerformanceSummaryAgent(RoutedAgent):
    """性能分析总结智能体"""

    def __init__(self):
        super().__init__("performance summary agent")

        self._prompt = """
        你是一位性能分析结果整合专家，负责将详细的性能分析、瓶颈识别和优化建议整合成结构化的最终报告。

        ## 职责
        - 综合多个分析角度，提炼核心问题和关键建议
        - 将非结构化的分析内容转化为结构化的JSON格式
        - 确保报告内容的一致性和完整性
        - 添加整体性能评估和优先行动建议

        ## 输出格式
        将所有分析整合为以下JSON结构（注意只输出JSON，不要有其他文本）：

        ```json
        {
          "summary": {
            "title": "性能分析总结",
            "timestamp": "YYYY-MM-DD HH:MM:SS",
            "overallScore": 85,
            "content": "整体性能评估文本...",
            "highlights": ["关键发现1", "关键发现2", "..."]
          },
          "metrics": {
            "title": "关键性能指标",
            "data": [
              {
                "name": "指标名称",
                "value": "当前值",
                "benchmark": "基准值",
                "status": "良好/一般/差",
                "percentOfBenchmark": 120
              }
            ]
          },
          "bottlenecks": [
            {
              "id": "B001",
              "type": "瓶颈类型",
              "description": "瓶颈详细描述",
              "impact": "影响描述",
              "location": "问题位置",
              "severity": "严重/中等/轻微"
            }
          ],
          "recommendations": [
            {
              "id": "R001",
              "title": "优化建议标题",
              "description": "建议详细描述",
              "implementation": "实施方法",
              "impact": "预期影响",
              "impact_level": "高/中/低"
            }
          ]
        }
        ```

        ## 注意事项
        1. 确保JSON格式正确无误
        2. 从原始分析中提取关键性能指标填入metrics部分
        3. 将瓶颈分析内容结构化到bottlenecks部分
        4. 将优化建议结构化到recommendations部分
        5. 生成简洁有力的总结到summary部分
        6. 每个部分都要完整填充，不要遗漏关键信息
        """

    @message_handler
    async def handle_message(
        self, message: PerformanceMessage, ctx: MessageContext
    ) -> None:
        """处理性能分析总结请求"""
        await self.publish_message(
            ResponseMessage(source="结果整合智能体", content="正在整合分析结果..."),
            topic_id=TopicId(type=performance_result_topic_type, source=self.id.key),
        )

        # 创建总结智能体
        summary_agent = AssistantAgent(
            name="performance_summary_agent",
            model_client=model_client,
            system_message=self._prompt,
            model_client_stream=True,
        )

        # 提取内容
        analysis_content = message.content["analysis"]
        bottleneck_content = message.content["bottlenecks"]
        recommendation_content = message.content["recommendations"]

        # 总结任务
        summary_task = f"""
        请根据以下性能分析、瓶颈识别和优化建议，生成结构化的最终报告:

        ## 性能分析
        {analysis_content}

        ## 已识别的瓶颈
        {bottleneck_content}

        ## 优化建议
        {recommendation_content}
        """

        # 流式输出
        stream = summary_agent.run_stream(task=summary_task)
        summary_content = ""

        async for msg in stream:
            if isinstance(msg, ModelClientStreamingChunkEvent):
                # 流式输出到前端
                await self.publish_message(
                    ResponseMessage(source="结果整合智能体", content=msg.content),
                    topic_id=TopicId(
                        type=performance_result_topic_type, source=self.id.key
                    ),
                )
                continue

            if isinstance(msg, TaskResult):
                summary_content = msg.messages[-1].content

        # 尝试解析JSON结果
        try:
            # 从文本中提取JSON部分
            import re

            json_match = re.search(r"```json\s*(.*?)\s*```", summary_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = summary_content

            # 解析JSON
            result_data = json.loads(json_str)

            # 保存结果
            results_dir = "results/performance_analysis"
            os.makedirs(results_dir, exist_ok=True)
            result_file = os.path.join(
                results_dir, f"result_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            )

            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)

            # 发送最终结果到前端
            await self.publish_message(
                ResponseMessage(
                    source="性能分析系统",
                    content="性能分析完成！已生成详细报告。",
                    is_final=True,
                    result=result_data,
                ),
                topic_id=TopicId(
                    type=performance_result_topic_type, source=self.id.key
                ),
            )

        except Exception as e:
            # 解析失败，发送原始内容
            await self.publish_message(
                ResponseMessage(
                    source="性能分析系统",
                    content=f"结果整合过程中出现错误: {str(e)}。原始分析结果如下:\n\n{summary_content}",
                    is_final=True,
                ),
                topic_id=TopicId(
                    type=performance_result_topic_type, source=self.id.key
                ),
            )


async def start_performance_analysis(file_path: str):
    """启动性能分析流程"""
    runtime = SingleThreadedAgentRuntime()

    # 注册智能体
    await PerformanceAnalyzerAgent.register(
        runtime, performance_analyzer_topic_type, lambda: PerformanceAnalyzerAgent()
    )
    await PerformanceBottleneckAgent.register(
        runtime, performance_bottleneck_topic_type, lambda: PerformanceBottleneckAgent()
    )
    await PerformanceRecommendationAgent.register(
        runtime,
        performance_recommendation_topic_type,
        lambda: PerformanceRecommendationAgent(),
    )
    await PerformanceSummaryAgent.register(
        runtime, performance_summary_topic_type, lambda: PerformanceSummaryAgent()
    )

    # 注册结果收集智能体
    await ClosureAgent.register_closure(
        runtime,
        "result_collector_agent",
        collect_result,
        subscriptions=lambda: [
            TypeSubscription(
                topic_type=performance_result_topic_type,
                agent_type="result_collector_agent",
            )
        ],
    )

    # 启动运行时
    runtime.start()

    # 发布分析任务消息
    await runtime.publish_message(
        file_path, topic_id=DefaultTopicId(type=performance_analyzer_topic_type)
    )

    # 等待所有智能体处理完成
    await runtime.stop_when_idle()
    await runtime.close()


async def collect_result(
    ctx: ClosureContext, message: ResponseMessage, msg_ctx: MessageContext
) -> None:
    """收集智能体的分析结果消息"""
    # 将消息放入队列
    await result_queue.put(message.model_dump())


async def performance_result_stream():
    """生成用于SSE的事件流"""
    try:
        while True:
            # 从队列中获取消息
            message = await result_queue.get()

            # 格式化为SSE事件
            data = json.dumps(message)
            yield f"data: {data}\n\n"

            # 如果是最终结果，结束流
            if message.get("is_final", False):
                break

    except asyncio.CancelledError:
        # 处理取消请求
        pass
