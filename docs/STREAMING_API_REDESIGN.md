# 流式API接口重新设计文档

## 概述

根据用户需求，已将测试用例生成模块的API接口重新设计为POST请求，并支持AutoGen风格的流式输出。前端可以接收到完整的流式内容，包括中间过程和最终结果。

## 🔄 主要变更

### 1. 接口方法变更
- **原来**: GET请求 + SSE
- **现在**: POST请求 + SSE流式输出
- **优势**: 支持复杂请求体，更好的数据传输

### 2. 流式输出类型
参考AutoGen的流式输出模式，支持三种类型：

```python
# 1. streaming_chunk - 类似 ModelClientStreamingChunkEvent
{
    "type": "streaming_chunk",
    "source": "需求分析智能体",
    "content": "正在分析用户需求...",
    "conversation_id": "abc123",
    "message_type": "需求分析",
    "chunk_index": 0,
    "timestamp": "2025-06-10T17:21:23"
}

# 2. text_message - 类似 TextMessage
{
    "type": "text_message",
    "source": "需求分析智能体",
    "content": "完整的需求分析结果...",
    "conversation_id": "abc123",
    "message_type": "需求分析",
    "is_complete": true,
    "timestamp": "2025-06-10T17:21:23"
}

# 3. task_result - 类似 TaskResult
{
    "type": "task_result",
    "messages": [...],  // 所有智能体的输出消息列表
    "conversation_id": "abc123",
    "task_complete": true,
    "timestamp": "2025-06-10T17:21:23"
}
```

## 📋 新的API接口

### 1. 流式生成接口
```
POST /api/testcase/generate/streaming
```

**请求体**:
```json
{
    "conversation_id": "可选，不提供则自动生成",
    "text_content": "用户需求文本",
    "files": [
        {
            "filename": "文件名",
            "content_type": "文件类型",
            "content": "文件内容",
            "size": 1024
        }
    ],
    "round_number": 1,
    "enable_streaming": true
}
```

**响应**: SSE流式数据，包含上述三种类型的消息

### 2. 流式反馈接口
```
POST /api/testcase/feedback/streaming
```

**请求体**:
```json
{
    "conversation_id": "对话ID",
    "feedback": "用户反馈内容",
    "round_number": 2,
    "previous_testcases": "之前的测试用例内容"
}
```

**响应**: SSE流式数据，根据反馈类型返回优化或最终化结果

## 🔧 后端实现细节

### 1. 流式输出生成器
```python
async def start_streaming_generation(self, requirement: RequirementMessage) -> AsyncGenerator[Dict, None]:
    """启动流式测试用例生成"""
    # 1. 启动智能体流程
    await self.start_requirement_analysis(requirement)

    # 2. 生成流式输出
    async for stream_data in self._generate_streaming_output(conversation_id):
        yield stream_data
```

### 2. 流式输出类型处理
```python
# 流式块输出 - 模拟 ModelClientStreamingChunkEvent
chunk_size = 50
for j in range(0, len(content), chunk_size):
    chunk = content[j:j+chunk_size]
    yield {
        "type": "streaming_chunk",
        "source": agent_name,
        "content": chunk,
        # ...
    }

# 完整消息输出 - 模拟 TextMessage
yield {
    "type": "text_message",
    "source": agent_name,
    "content": complete_content,
    # ...
}

# 任务结果输出 - 模拟 TaskResult
yield {
    "type": "task_result",
    "messages": all_messages,
    # ...
}
```

### 3. 智能体流程
1. **需求分析智能体** → 分析用户需求
2. **测试用例生成智能体** → 生成初步测试用例
3. **用例评审优化智能体** → 根据反馈优化用例
4. **结构化入库智能体** → 生成最终JSON格式

## 🌐 前端集成指南

### 1. 发起流式请求
```typescript
const response = await fetch('/api/testcase/generate/streaming', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        text_content: "用户需求",
        files: [],
        enable_streaming: true
    })
});

const reader = response.body?.getReader();
```

### 2. 处理流式数据
```typescript
while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = new TextDecoder().decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));

            switch (data.type) {
                case 'streaming_chunk':
                    // 处理流式输出块 - 实时显示
                    appendToOutput(data.content);
                    break;

                case 'text_message':
                    // 处理完整消息 - 智能体完成输出
                    displayCompleteMessage(data.source, data.content);
                    break;

                case 'task_result':
                    // 处理任务结果 - 所有智能体完成
                    displayFinalResult(data.messages);
                    break;

                case 'error':
                    // 处理错误
                    displayError(data.content);
                    break;
            }
        }
    }
}
```

### 3. 前端状态管理
```typescript
interface StreamingState {
    isStreaming: boolean;
    currentAgent: string;
    streamingContent: string;
    completeMessages: Message[];
    finalResult: TaskResult | null;
}
```

## 📊 详细日志输出

每个步骤都有详细的日志记录：

```
🚀 [需求分析阶段] 启动需求分析流程
   📋 对话ID: abc123
   🔢 轮次: 1
   📝 文本内容长度: 39
   📎 文件数量: 0

🔍 [需求分析智能体] 收到需求分析任务
   🤖 智能体: 需求分析智能体
   📄 分析结果长度: 1234 字符

📤 [流式输出] 处理消息 1 | 智能体: 需求分析智能体
   🏷️  类型: streaming_chunk
   📡 流式块: 正在分析用户需求...
```

## ✅ 测试验证

通过测试验证，新的流式API具备以下特性：

1. **✅ 接口改为POST请求**: 支持复杂请求体
2. **✅ AutoGen风格流式输出**: 三种消息类型完整支持
3. **✅ 详细日志记录**: 每个步骤都有详细的日志输出
4. **✅ 错误处理**: 完善的异常捕获和错误返回
5. **✅ 前端友好**: 基于type字段的消息类型识别

## 🔮 前端实现建议

1. **实时显示**: 使用streaming_chunk实现打字机效果
2. **状态管理**: 根据text_message更新智能体状态
3. **结果展示**: 使用task_result显示最终完整结果
4. **错误处理**: 统一的错误消息处理机制
5. **用户体验**: 流式输出提供更好的实时反馈

---

**相关文档**:
- [测试用例服务重新设计](./TESTCASE_SERVICE_REDESIGN.md)
- [项目开发记录](./MYWORK.md)
- [AutoGen官方文档](https://microsoft.github.io/autogen/stable/)
