# 前后端API统一规范

## 1. 响应格式规范

### 1.1 标准响应格式

所有API响应都应遵循以下格式：

```typescript
interface BaseResponse<T = any> {
  code: number;        // 业务状态码
  message: string;     // 响应消息
  data: T;            // 响应数据
  timestamp?: string; // 时间戳
}
```

### 1.2 成功响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "123",
    "name": "测试用例"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 1.3 错误响应示例

```json
{
  "code": 1001,
  "message": "参数错误",
  "data": null,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 2. 状态码规范

### 2.1 HTTP状态码

- `200`: 请求成功
- `201`: 创建成功
- `400`: 请求参数错误
- `401`: 未授权
- `403`: 禁止访问
- `404`: 资源不存在
- `500`: 服务器内部错误

### 2.2 业务状态码

- `0`: 成功
- `1001`: 参数错误
- `1002`: 未授权
- `1003`: 禁止访问
- `1004`: 资源不存在
- `1005`: 服务器内部错误
- `1006`: 请求频率限制

## 3. SSE流式响应规范

### 3.1 SSE事件格式

```
data: {"source": "agent_name", "content": "消息内容", "is_final": false}

data: {"source": "agent_name", "content": "最终消息", "is_final": true}
```

### 3.2 SSE消息接口

```typescript
interface StreamResponse {
  source: string;           // 消息来源
  content: string;          // 消息内容
  agent_type: string;       // 智能体类型
  agent_name: string;       // 智能体名称
  conversation_id: string;  // 对话ID
  round_number: number;     // 轮次
  is_complete: boolean;     // 是否完成
  is_final: boolean;        // 是否最终消息
  timestamp: string;        // 时间戳
}
```

### 3.3 SSE连接规范

- **URL格式**: `/api/endpoint/sse`
- **请求方法**: POST（通过查询参数传递数据）
- **Content-Type**: `text/event-stream`
- **连接保持**: 支持自动重连
- **错误处理**: 连接断开时自动重试

## 4. 请求规范

### 4.1 请求头规范

```
Content-Type: application/json
Authorization: Bearer <token>
X-Request-ID: <unique_request_id>
```

### 4.2 分页请求规范

```typescript
interface PageRequest {
  page: number;      // 页码，从1开始
  pageSize: number;  // 每页大小，默认20
}

interface PageResponse<T> {
  code: number;
  message: string;
  data: T[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}
```

### 4.3 文件上传规范

```typescript
interface FileUpload {
  filename: string;    // 文件名
  content: string;     // base64编码内容
  content_type: string; // MIME类型
  size: number;        // 文件大小（字节）
}
```

## 5. API端点规范

### 5.1 RESTful规范

- **GET**: 获取资源
- **POST**: 创建资源
- **PUT**: 更新资源
- **DELETE**: 删除资源

### 5.2 URL命名规范

- 使用小写字母和下划线
- 资源名使用复数形式
- 版本号放在URL中：`/api/v1/`

### 5.3 端点示例

```
GET    /api/v1/testcases          # 获取测试用例列表
POST   /api/v1/testcases          # 创建测试用例
GET    /api/v1/testcases/{id}     # 获取单个测试用例
PUT    /api/v1/testcases/{id}     # 更新测试用例
DELETE /api/v1/testcases/{id}     # 删除测试用例

POST   /api/v1/testcases/generate/sse  # SSE流式生成
```

## 6. 错误处理规范

### 6.1 前端错误处理

```typescript
try {
  const response = await request.post('/api/endpoint', data);
  // 处理成功响应
} catch (error) {
  // 统一错误处理
  console.error('请求失败:', error);
  message.error(error.message);
}
```

### 6.2 后端错误响应

```python
# 成功响应
return {
    "code": 0,
    "message": "success",
    "data": result,
    "timestamp": datetime.now().isoformat()
}

# 错误响应
return {
    "code": 1001,
    "message": "参数错误",
    "data": None,
    "timestamp": datetime.now().isoformat()
}
```

## 7. 认证授权规范

### 7.1 Token格式

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 7.2 Token刷新

```typescript
// 自动刷新Token
if (response.status === 401) {
  await refreshToken();
  // 重试原请求
}
```

## 8. 日志规范

### 8.1 前端日志

```typescript
console.log('发送请求:', {
  url: config.url,
  method: config.method,
  data: config.data,
  headers: config.headers,
});

console.log('收到响应:', {
  url: response.config.url,
  status: response.status,
  data: response.data,
});
```

### 8.2 后端日志

```python
logger.info(f"收到请求 | URL: {request.url} | 方法: {request.method}")
logger.info(f"响应结果 | 状态码: {response.status_code} | 耗时: {duration}ms")
```

## 9. 性能优化规范

### 9.1 请求优化

- 使用请求拦截器添加通用参数
- 实现请求去重机制
- 设置合理的超时时间
- 支持请求取消

### 9.2 SSE优化

- 实现自动重连机制
- 限制最大重连次数
- 支持连接池管理
- 及时清理无用连接

## 10. 测试规范

### 10.1 单元测试

```typescript
describe('RequestManager', () => {
  it('should send GET request correctly', async () => {
    const response = await request.get('/api/test');
    expect(response.code).toBe(0);
  });

  it('should handle SSE connection', () => {
    const sse = request.createSSEConnection('test', {
      url: '/api/sse',
      onMessage: (event) => {
        expect(event.data).toBeDefined();
      }
    });
    expect(sse).toBeInstanceOf(EventSource);
  });
});
```

### 10.2 集成测试

```typescript
describe('TestCase API', () => {
  it('should generate testcase via SSE', async () => {
    const { startGeneration } = useTestCaseSSE();
    const messages: StreamResponse[] = [];

    await startGeneration({
      text_content: 'test',
      round_number: 1
    }, (message) => {
      messages.push(message);
    });

    expect(messages.length).toBeGreaterThan(0);
  });
});
```

## 11. 部署配置

### 11.1 环境变量

```bash
# 前端环境变量
REACT_APP_API_BASE_URL=http://localhost:8000/api
REACT_APP_SSE_TIMEOUT=30000

# 后端环境变量
API_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000
```

### 11.2 代理配置

```javascript
// package.json
{
  "proxy": "http://localhost:8000"
}

// 或使用 setupProxy.js
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:8000',
      changeOrigin: true,
    })
  );
};
```

这个规范确保了前后端API的一致性和可维护性，提供了完整的开发指导。
