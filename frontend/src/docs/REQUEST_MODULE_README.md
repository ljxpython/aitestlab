# 前端请求模块使用指南

## 概述

本模块提供了统一的HTTP请求和SSE流式请求解决方案，支持：

- ✅ 普通HTTP请求（GET、POST、PUT、DELETE）
- ✅ SSE流式请求
- ✅ 文件上传
- ✅ 自动错误处理
- ✅ 请求拦截器
- ✅ 自动重连机制
- ✅ TypeScript类型支持

## 快速开始

### 1. 基本导入

```typescript
import {
  request,           // 请求实例
  TestCaseAPI,       // 测试用例API
  ChatAPI,           // 聊天API
  useSSE,            // SSE Hook
  useTestCaseGeneration, // 测试用例生成Hook
  useChat            // 聊天Hook
} from '../api';
```

### 2. 普通HTTP请求

```typescript
// GET请求
const response = await request.get('/api/users');

// POST请求
const response = await request.post('/api/users', {
  name: 'John',
  email: 'john@example.com'
});

// PUT请求
const response = await request.put('/api/users/1', userData);

// DELETE请求
const response = await request.delete('/api/users/1');
```

### 3. SSE流式请求

```typescript
import { useSSE } from '../api';

const MyComponent = () => {
  const { isConnected, connect, disconnect } = useSSE({
    url: '/api/stream',
    onMessage: (event) => {
      console.log('收到消息:', event.data);
    },
    onError: (error) => {
      console.error('连接错误:', error);
    }
  });

  const handleConnect = () => {
    connect({ param: 'value' });
  };

  return (
    <div>
      <button onClick={handleConnect}>连接</button>
      <button onClick={disconnect}>断开</button>
      <p>状态: {isConnected ? '已连接' : '未连接'}</p>
    </div>
  );
};
```

### 4. 测试用例生成

```typescript
import { useTestCaseGeneration } from '../api';

const TestCaseComponent = () => {
  const {
    messages,
    loading,
    error,
    generate,
    stop,
    clear
  } = useTestCaseGeneration();

  const handleGenerate = () => {
    generate({
      text_content: '用户登录功能',
      round_number: 1
    });
  };

  return (
    <div>
      <button onClick={handleGenerate} disabled={loading}>
        {loading ? '生成中...' : '生成测试用例'}
      </button>
      <button onClick={stop} disabled={!loading}>停止</button>
      <button onClick={clear}>清空</button>

      {error && <div>错误: {error}</div>}

      {messages.map((msg, index) => (
        <div key={index}>
          <strong>{msg.agent_name}:</strong> {msg.content}
        </div>
      ))}
    </div>
  );
};
```

### 5. 聊天功能

```typescript
import { useChat } from '../api';

const ChatComponent = () => {
  const {
    messages,
    loading,
    send,
    clear
  } = useChat();

  const [input, setInput] = useState('');

  const handleSend = () => {
    if (input.trim()) {
      send(input);
      setInput('');
    }
  };

  return (
    <div>
      <div className="messages">
        {messages.map((msg, index) => (
          <div key={index}>
            <strong>{msg.role}:</strong> {msg.content}
          </div>
        ))}
      </div>

      <div className="input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading}>
          发送
        </button>
      </div>
    </div>
  );
};
```

### 6. 文件上传

```typescript
const handleFileUpload = async (file: File) => {
  try {
    const response = await request.upload('/api/upload', file);
    console.log('上传成功:', response);
  } catch (error) {
    console.error('上传失败:', error);
  }
};

// 在组件中使用
<input
  type="file"
  onChange={(e) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
  }}
/>
```

## API参考

### RequestManager

#### 方法

- `get<T>(url, config?)`: GET请求
- `post<T>(url, data?, config?)`: POST请求
- `put<T>(url, data?, config?)`: PUT请求
- `delete<T>(url, config?)`: DELETE请求
- `upload<T>(url, file, config?)`: 文件上传
- `createSSEConnection(id, config)`: 创建SSE连接
- `closeSSEConnection(id)`: 关闭SSE连接
- `closeAllSSEConnections()`: 关闭所有SSE连接

#### 配置选项

```typescript
interface RequestConfig {
  showLoading?: boolean;    // 显示加载状态
  showError?: boolean;      // 显示错误信息
  timeout?: number;         // 超时时间
  headers?: Record<string, string>; // 请求头
}
```

### useSSE Hook

#### 参数

```typescript
interface UseSSEOptions {
  url: string;                    // SSE端点URL
  data?: any;                     // 请求数据
  autoConnect?: boolean;          // 自动连接
  reconnect?: boolean;            // 自动重连
  reconnectInterval?: number;     // 重连间隔
  maxReconnectAttempts?: number;  // 最大重连次数
  onMessage?: (event) => void;    // 消息回调
  onError?: (error) => void;      // 错误回调
  onOpen?: (event) => void;       // 连接打开回调
  onClose?: (event) => void;      // 连接关闭回调
}
```

#### 返回值

```typescript
interface UseSSEReturn {
  isConnected: boolean;     // 连接状态
  isConnecting: boolean;    // 连接中状态
  error: string | null;     // 错误信息
  connect: (data?) => void; // 连接方法
  disconnect: () => void;   // 断开方法
  reconnect: () => void;    // 重连方法
  connectionId: string;     // 连接ID
}
```

### 业务Hook

#### useTestCaseGeneration

```typescript
const {
  messages,      // 消息列表
  loading,       // 加载状态
  error,         // 错误信息
  generate,      // 生成方法
  stop,          // 停止方法
  clear          // 清空方法
} = useTestCaseGeneration();
```

#### useChat

```typescript
const {
  messages,      // 聊天消息
  loading,       // 发送状态
  send,          // 发送消息
  stop,          // 停止发送
  clear,         // 清空聊天
  loadHistory    // 加载历史
} = useChat();
```

## 错误处理

### 全局错误处理

请求模块提供了统一的错误处理机制：

```typescript
// 自动处理的错误类型
- 网络错误
- 超时错误
- HTTP状态码错误
- 业务逻辑错误

// 错误响应格式
interface ErrorResponse {
  code: number;
  message: string;
  data: null;
  timestamp: string;
}
```

### 自定义错误处理

```typescript
try {
  const response = await request.post('/api/endpoint', data);
} catch (error) {
  // error 已经是格式化后的错误对象
  console.error('请求失败:', error.message);

  // 根据错误码进行不同处理
  switch (error.code) {
    case 1001:
      // 参数错误
      break;
    case 1002:
      // 未授权，跳转登录
      break;
    default:
      // 其他错误
  }
}
```

## 配置

### 环境变量

```bash
# .env
REACT_APP_API_BASE_URL=http://localhost:8000/api
REACT_APP_REQUEST_TIMEOUT=30000
```

### 全局配置

```typescript
// 在应用启动时配置
import { request } from './api';

// 设置默认配置
request.axiosInstance.defaults.timeout = 30000;
request.axiosInstance.defaults.headers.common['X-App-Version'] = '1.0.0';
```

## 最佳实践

### 1. 错误边界

```typescript
const MyComponent = () => {
  const [error, setError] = useState(null);

  const handleRequest = async () => {
    try {
      setError(null);
      const response = await request.get('/api/data');
      // 处理成功响应
    } catch (err) {
      setError(err.message);
    }
  };

  if (error) {
    return <div>错误: {error}</div>;
  }

  return <div>正常内容</div>;
};
```

### 2. 加载状态

```typescript
const [loading, setLoading] = useState(false);

const handleRequest = async () => {
  setLoading(true);
  try {
    await request.post('/api/endpoint', data);
  } finally {
    setLoading(false);
  }
};
```

### 3. 请求取消

```typescript
useEffect(() => {
  const controller = new AbortController();

  const fetchData = async () => {
    try {
      await request.get('/api/data', {
        signal: controller.signal
      });
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('请求失败:', error);
      }
    }
  };

  fetchData();

  return () => {
    controller.abort();
  };
}, []);
```

### 4. SSE连接管理

```typescript
useEffect(() => {
  // 组件卸载时自动清理连接
  return () => {
    request.closeAllSSEConnections();
  };
}, []);
```

## 故障排除

### 常见问题

1. **CORS错误**: 检查后端CORS配置
2. **连接超时**: 调整timeout配置
3. **SSE连接失败**: 检查URL和网络状态
4. **Token过期**: 实现自动刷新机制

### 调试技巧

```typescript
// 开启详细日志
localStorage.setItem('debug', 'request:*');

// 查看网络请求
console.log('活跃SSE连接数:', request.getActiveSSEConnectionsCount());
```

## 更新日志

- v1.0.0: 初始版本，支持基本HTTP和SSE请求
- v1.1.0: 添加文件上传功能
- v1.2.0: 优化错误处理和重连机制
- v1.3.0: 添加业务Hook和类型定义

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

MIT License
