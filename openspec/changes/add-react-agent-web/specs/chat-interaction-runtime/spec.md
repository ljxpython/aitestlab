## MODIFIED Requirements

### Requirement: 正式聊天运行时使用 Protocol v2 网关

正式聊天页面 MUST 通过 `platform-api` 的 `POST /api/langgraph/threads/{thread_id}/commands`
提交 Protocol v2 command，并通过 `POST /api/langgraph/threads/{thread_id}/stream/events` 建立
事件订阅。Protocol v2 MUST 操作或观察 Durable Run；页面 MUST NOT 直连 upstream、手工解析
raw SSE，或在同一聊天会话中回退调用 legacy `/runs/stream` 路由。

#### Scenario: 创建 Durable Run 并订阅事件
- **WHEN** 已授权用户在已选 project 的 thread 提交 `run.start`
- **THEN** 网关返回保留 command id 的 protocol success/error envelope，后台 Run 独立于浏览器继续执行，页面经 v2 event stream 接收该运行的消息、values、tools、lifecycle 和 input 事件

#### Scenario: 协议请求被拒绝
- **WHEN** command envelope 无效、actor 未授权，或 thread 不属于请求 project
- **THEN** 网关拒绝请求且不向 upstream 创建或订阅运行，并返回可归一化的协议或权限错误

### Requirement: Protocol v2 事件流使用受控 Bearer fetch SSE 且可续接

`platform-api` MUST 将 event stream 的 channel/namespace 过滤、客户端断开、`since` replay 与
event `seq` 语义受控传递给 upstream。Agent Web MUST 用带 Bearer `Authorization` 和项目头的
`fetch + ReadableStream` 请求该 POST SSE endpoint，保存最后确认的 `seq`，并在重连 body 中
提交为 `since`。网关 MUST NOT 伪造、重排或跨 project 泄漏事件；除经测试的敏感字段脱敏外，
MUST 保持 Protocol v2 event type、payload 语义和 `seq`。

#### Scenario: 客户端重连
- **WHEN** 客户端以最后成功接收的 event `seq` 作为 `since` 重新订阅同一可读取 thread
- **THEN** 网关先交付序号更高的缓冲事件，再交付实时事件，且页面不会重复处理已确认的事件

#### Scenario: 订阅被取消
- **WHEN** 浏览器取消或关闭 event stream
- **THEN** 网关取消对应 upstream subscription，且不会影响同一 thread 的其他合法订阅或运行

#### Scenario: Bearer token 不进入 URL
- **WHEN** 页面建立或重建事件订阅
- **THEN** access token 只出现在 `Authorization` request header，不出现在 URL、query parameter 或日志化的诊断文本中
