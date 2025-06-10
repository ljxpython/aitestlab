# 前端适配新后端接口文档

## 概述

已完成 `frontend/src/pages/TestCasePage.tsx` 的前端代码适配，使其与新的POST流式后端接口完全兼容。

## 🔄 主要适配内容

### 1. API接口更新

#### 配置文件更新 (`frontend/src/config/api.ts`)
```typescript
TESTCASE: {
  GENERATE: '/api/testcase/generate',
  GENERATE_STREAMING: '/api/testcase/generate/streaming',  // 新的流式生成接口
  FEEDBACK_STREAMING: '/api/testcase/feedback/streaming',  // 新的流式反馈接口
  HISTORY: '/api/testcase/history',
  TEST: '/api/testcase/test',
  EXPORT: '/testcase/export',
},
```

#### 类型定义更新 (`frontend/src/api/types.ts`)
```typescript
// 新的流式消息类型
export interface StreamResponse {
  type: 'streaming_chunk' | 'text_message' | 'task_result' | 'error';
  source: string;
  content: string;
  conversation_id: string;
  message_type?: string;
  is_complete?: boolean;
  timestamp: string;
  // 特有字段
  chunk_index?: number;        // streaming_chunk
  messages?: any[];           // task_result
  task_complete?: boolean;    // task_result
  max_rounds_reached?: boolean; // error
}

// 新的请求类型
export interface TestCaseRequest {
  conversation_id?: string;
  text_content?: string;
  files?: FileUpload[];
  round_number?: number;
  enable_streaming?: boolean;  // 新增流式开关
}

export interface FeedbackRequest {
  conversation_id: string;
  feedback: string;
  round_number: number;
  previous_testcases?: string;
}
```

### 2. API服务重写 (`frontend/src/api/testcase.ts`)

#### 新的API类
```typescript
export class TestCaseAPI {
  // 流式生成测试用例（POST + SSE）
  static async generateStreaming(data: TestCaseRequest): Promise<ReadableStreamDefaultReader<Uint8Array>>

  // 流式处理用户反馈（POST + SSE）
  static async feedbackStreaming(data: FeedbackRequest): Promise<ReadableStreamDefaultReader<Uint8Array>>

  // 获取对话历史
  static async getHistory(conversationId: string): Promise<BaseResponse<any>>

  // 测试服务状态
  static async test(): Promise<BaseResponse<any>>
}
```

#### 新的Hook设计
```typescript
export const useTestCaseStreaming = () => {
  // 流式生成
  const startGeneration = async (data: TestCaseRequest, onMessage: (message: StreamResponse) => void): Promise<void>

  // 流式反馈
  const startFeedback = async (data: FeedbackRequest, onMessage: (message: StreamResponse) => void): Promise<void>

  // 停止流式处理
  const stopStreaming = () => void
}

export const useTestCaseGeneration = () => {
  // 状态管理
  const [messages, streamingContent, currentAgent, loading, error, conversationId] = useState(...)

  // 方法
  const generate = async (data: TestCaseRequest) => void
  const submitFeedback = async (feedback: string, previousTestcases: string) => void
  const stop = () => void
  const clear = () => void
}
```

### 3. 前端页面适配 (`frontend/src/pages/TestCasePage.tsx`)

#### Hook使用更新
```typescript
const {
  messages: streamMessages,
  streamingContent,        // 新增：实时流式内容
  currentAgent,           // 新增：当前输出的智能体
  loading,
  error,
  conversationId: hookConversationId,
  generate,
  submitFeedback: hookSubmitFeedback,  // 新的反馈方法
  stop,
  clear
} = useTestCaseGeneration();
```

#### 消息处理逻辑
```typescript
// 处理流式消息
useEffect(() => {
  if (streamMessages.length > 0) {
    const newMessages: AgentMessageData[] = streamMessages
      .filter((msg: StreamResponse) => msg.type === 'text_message') // 只显示完整消息
      .map((msg: StreamResponse) => ({
        id: `${msg.source}_${msg.timestamp}_${Math.random()}`,
        content: msg.content,
        agentType: 'agent',
        agentName: msg.source,
        timestamp: msg.timestamp,
        roundNumber: 1
      }));

    setAgentMessages(newMessages);

    // 检查是否完成
    const lastMessage = streamMessages[streamMessages.length - 1];
    if (lastMessage?.type === 'task_result') {
      setIsComplete(true);
      setCurrentStep(2);
      setAnalysisProgress(100);
      message.success('测试用例生成完成！');
    }
  }
}, [streamMessages, hookConversationId, conversationId]);
```

#### 流式内容显示
```typescript
{/* 流式内容显示 */}
{currentAgent && streamingContent && (
  <div style={{ marginBottom: 24 }}>
    <div style={{
      display: 'flex',
      alignItems: 'center',
      marginBottom: 12,
      padding: '8px 12px',
      background: '#e6f7ff',
      borderRadius: 6,
      border: '1px solid #91d5ff'
    }}>
      <RobotOutlined style={{ color: '#1890ff', marginRight: 8 }} />
      <Text strong style={{ color: '#1890ff' }}>
        {currentAgent}
      </Text>
      <Tag color="processing" style={{ marginLeft: 'auto' }}>
        正在输出...
      </Tag>
    </div>

    <div style={{
      marginLeft: 0,
      padding: 16,
      background: 'white',
      borderRadius: 8,
      border: '1px solid #f0f0f0',
      whiteSpace: 'pre-wrap',
      lineHeight: 1.6,
      minHeight: 60
    }}>
      <MarkdownRenderer content={streamingContent} />
      <span style={{
        display: 'inline-block',
        width: 8,
        height: 16,
        background: '#1890ff',
        animation: 'blink 1s infinite',
        marginLeft: 4
      }} />
    </div>
  </div>
)}
```

#### 生成函数更新
```typescript
const generateTestCase = async () => {
  // 准备请求数据
  const requestData: TestCaseRequest = {
    conversation_id: conversationId || undefined,
    text_content: textContent.trim() || undefined,
    files: fileUploads,
    round_number: roundNumber,
    enable_streaming: true  // 启用流式输出
  };

  console.log('🚀 开始生成测试用例:', requestData);

  // 使用新的Hook生成测试用例
  await generate(requestData);
};
```

#### 反馈函数更新
```typescript
const submitFeedback = async () => {
  // 获取最后的测试用例内容
  const lastTestcases = agentMessages
    .filter(msg => msg.agentName.includes('测试用例') || msg.agentName.includes('优化'))
    .map(msg => msg.content)
    .join('\n\n');

  console.log('🔄 提交反馈:', userFeedback.trim());

  // 使用新的Hook提交反馈
  await hookSubmitFeedback(userFeedback.trim(), lastTestcases);
};
```

## 🎯 新功能特性

### 1. 实时流式显示
- **流式输出块**: 显示智能体的实时输出过程
- **打字机效果**: 模拟ChatGPT的实时打字效果
- **智能体状态**: 显示当前正在输出的智能体名称

### 2. 消息类型处理
- **streaming_chunk**: 实时显示在流式区域
- **text_message**: 显示为完整的智能体消息
- **task_result**: 标记任务完成
- **error**: 显示错误信息

### 3. 用户体验优化
- **实时反馈**: 用户可以看到智能体的处理过程
- **状态指示**: 清晰的智能体状态和进度显示
- **错误处理**: 完善的错误提示和恢复机制

## 🔧 技术实现

### 1. 流式数据处理
```typescript
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value, { stream: true });
  buffer += chunk;

  const lines = buffer.split('\n');
  buffer = lines.pop() || '';

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      onMessage(data);
    }
  }
}
```

### 2. 状态管理
```typescript
// 流式内容状态
const [streamingContent, setStreamingContent] = useState<string>('');
const [currentAgent, setCurrentAgent] = useState<string>('');

// 消息处理
switch (message.type) {
  case 'streaming_chunk':
    setCurrentAgent(message.source);
    setStreamingContent(prev => prev + message.content);
    break;
  case 'text_message':
    setMessages(prev => [...prev, message]);
    setStreamingContent('');
    setCurrentAgent('');
    break;
}
```

### 3. CSS动画
```css
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
```

## ✅ 适配完成状态

1. **✅ API接口适配**: 完全适配新的POST流式接口
2. **✅ 类型定义更新**: 支持新的流式消息类型
3. **✅ Hook重新设计**: 支持流式生成和反馈处理
4. **✅ UI界面更新**: 实时显示流式内容和智能体状态
5. **✅ 用户体验优化**: 打字机效果和状态指示
6. **✅ 错误处理**: 完善的错误提示和恢复机制

## 🚀 使用方式

前端现在可以：

1. **发起流式生成**: 调用新的POST接口，实时显示智能体输出
2. **处理流式反馈**: 提交用户反馈，实时显示优化过程
3. **查看完整过程**: 看到从需求分析到测试用例生成的完整流程
4. **实时交互**: 类似ChatGPT的实时对话体验

前端已完全适配新的后端接口，可以提供流畅的实时交互体验！

---

**相关文档**:
- [流式API接口重新设计](./STREAMING_API_REDESIGN.md)
- [日志优化文档](./LOG_OPTIMIZATION.md)
- [项目开发记录](./MYWORK.md)
