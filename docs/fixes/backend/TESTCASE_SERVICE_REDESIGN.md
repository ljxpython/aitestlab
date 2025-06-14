# 测试用例生成模块后端重新设计文档

## 概述

本文档描述了测试用例生成模块后端的重新设计，基于AutoGen 0.5.7实现多智能体协作，支持历史消息记录和分阶段处理。

## 设计目标

1. **分阶段处理**：使用两个接口来触发运行时的消息发布
2. **历史消息记录**：根据对话ID记录历史消息，实现内存管理
3. **智能体协作**：使用不同的智能体处理不同阶段的任务
4. **实时通信**：通过SSE实现前后端实时消息传递

## 核心架构

### 1. 接口设计

#### `/api/testcase/generate/sse` (GET)
- **功能**：启动需求分析和初步用例生成
- **发布消息类型**：需求分析
- **智能体流程**：需求分析智能体 → 用例生成智能体
- **返回**：SSE流式消息

#### `/api/testcase/feedback` (POST)
- **功能**：处理用户反馈
- **输入意见时**：用户反馈 + 用例评审优化智能体，发布消息：用例优化
- **输入同意时**：返回最终结果，完成数据库落库，发布消息：用例结果

#### `/api/testcase/feedback/sse` (GET)
- **功能**：获取反馈处理结果的实时消息
- **返回**：用例优化或用例结果的SSE流式消息

### 2. 智能体设计

#### 需求分析智能体 (RequirementAnalysisAgent)
- **订阅主题**：`requirement_analysis`
- **功能**：分析用户提供的需求内容
- **输出**：结构化的需求分析结果
- **下游**：发送到测试用例生成智能体

#### 测试用例生成智能体 (TestCaseGenerationAgent)
- **订阅主题**：`testcase_generation`
- **功能**：基于需求分析生成初步测试用例
- **输出**：Markdown格式的测试用例
- **特点**：覆盖功能、UI/UX、兼容性、异常/边界测试

#### 用例评审优化智能体 (TestCaseOptimizationAgent)
- **订阅主题**：`testcase_optimization`
- **功能**：根据用户反馈优化测试用例
- **输入**：用户反馈 + 原测试用例
- **输出**：优化后的测试用例

#### 结构化入库智能体 (TestCaseFinalizationAgent)
- **订阅主题**：`testcase_finalization`
- **功能**：将测试用例转换为JSON格式并验证
- **输出**：结构化的JSON测试用例数据
- **特点**：数据验证和格式标准化

#### 结果收集智能体 (ClosureAgent)
- **订阅主题**：`collect_result`
- **功能**：收集所有智能体的输出消息
- **特点**：实时收集，支持SSE流式传输

### 3. 运行时管理

#### TestCaseGenerationRuntime 类
```python
class TestCaseGenerationRuntime:
    def __init__(self):
        self.runtimes: Dict[str, SingleThreadedAgentRuntime] = {}  # 按对话ID存储运行时
        self.memories: Dict[str, ListMemory] = {}  # 按对话ID存储历史消息
        self.collected_messages: Dict[str, List[Dict]] = {}  # 收集的消息
        self.conversation_states: Dict[str, Dict] = {}  # 对话状态
```

**核心方法**：
- `start_requirement_analysis()`: 启动需求分析阶段
- `process_user_feedback()`: 处理用户反馈
- `_init_runtime()`: 初始化运行时和智能体
- `_save_to_memory()`: 保存历史消息
- `get_conversation_history()`: 获取对话历史
- `cleanup_runtime()`: 清理运行时资源

### 4. 消息类型

#### RequirementMessage
```python
class RequirementMessage(BaseModel):
    text_content: Optional[str] = ""
    files: Optional[List[FileUpload]] = None
    conversation_id: str
    round_number: int = 1
```

#### FeedbackMessage
```python
class FeedbackMessage(BaseModel):
    feedback: str
    conversation_id: str
    round_number: int
    previous_testcases: Optional[str] = ""
```

#### ResponseMessage
```python
class ResponseMessage(BaseModel):
    source: str
    content: str
    message_type: str = "info"  # 需求分析、用例优化、用例结果
    is_final: bool = False
```

## 工作流程

### 1. 需求分析阶段
```
用户请求 → /generate/sse → RequirementAnalysisAgent → TestCaseGenerationAgent → SSE返回
```

1. 用户通过 `/generate/sse` 提交需求
2. 创建 `RequirementMessage` 并发布到 `requirement_analysis` 主题
3. `RequirementAnalysisAgent` 处理需求分析
4. 分析结果发送到 `TestCaseGenerationAgent`
5. 生成初步测试用例
6. 通过SSE实时返回消息给前端

### 2. 用例优化阶段
```
用户反馈 → /feedback → TestCaseOptimizationAgent → /feedback/sse → SSE返回
```

1. 用户通过 `/feedback` 提交反馈意见
2. 创建 `FeedbackMessage` 并发布到 `testcase_optimization` 主题
3. `TestCaseOptimizationAgent` 根据反馈优化用例
4. 前端通过 `/feedback/sse` 获取优化结果

### 3. 用例结果阶段
```
用户同意 → /feedback → TestCaseFinalizationAgent → /feedback/sse → SSE返回
```

1. 用户通过 `/feedback` 提交"同意"
2. 创建 `FeedbackMessage` 并发布到 `testcase_finalization` 主题
3. `TestCaseFinalizationAgent` 进行结构化处理
4. 生成最终JSON格式的测试用例
5. 前端通过 `/feedback/sse` 获取最终结果

## 内存管理

### 历史消息记录
- 使用 `ListMemory` 存储对话历史
- 按对话ID分组管理
- 支持异步读写操作

### 对话状态管理
```python
conversation_state = {
    "stage": "requirement_analysis",  # 当前阶段
    "round_number": 1,               # 轮次
    "last_testcases": "...",         # 最后的测试用例
    "last_update": "2025-06-10T..."  # 最后更新时间
}
```

## 技术特点

### 1. 多智能体协作
- 基于AutoGen 0.5.7的 `RoutedAgent` 和 `SingleThreadedAgentRuntime`
- 支持消息订阅和发布机制
- 智能体间松耦合通信

### 2. 实时通信
- 使用SSE (Server-Sent Events) 实现实时消息推送
- 支持流式数据传输
- 前端可实时显示智能体处理进度

### 3. 状态管理
- 按对话ID隔离不同用户的会话
- 支持多轮对话和状态持久化
- 自动清理过期资源

### 4. 错误处理
- 完善的异常捕获和日志记录
- 优雅的错误恢复机制
- 详细的调试信息

## 部署和使用

### 1. 依赖要求
- AutoGen 0.5.7
- FastAPI
- SSE支持
- OpenAI API (或兼容接口)

### 2. 配置要求
- 正确配置OpenAI API密钥和基础URL
- 确保examples/llms.py中的模型客户端正常工作

### 3. 测试验证
```bash
# 运行结构测试
poetry run python test_service_structure.py

# 运行API测试
poetry run python -c "from backend.api.testcase import router; print('API导入成功')"
```

## 后续优化

1. **性能优化**：实现连接池和资源复用
2. **扩展性**：支持更多智能体类型和自定义工作流
3. **监控**：添加详细的性能监控和指标收集
4. **安全性**：增强输入验证和访问控制
5. **数据库集成**：完善测试用例的持久化存储

---

**相关文档**:
- [AutoGen官方文档](https://microsoft.github.io/autogen/stable/)
- [FastAPI SSE文档](https://fastapi.tiangolo.com/advanced/server-sent-events/)
- [项目开发记录](./MYWORK.md)
