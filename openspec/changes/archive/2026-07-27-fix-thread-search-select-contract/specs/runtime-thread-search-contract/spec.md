## ADDED Requirements

### Requirement: 线程搜索请求必须使用受支持的字段
platform-web SHALL 仅向 `/api/langgraph/threads/search` 发送当前 LangGraph 支持的 `select` 字段。正常聊天入口不得依赖 `422` fallback 才能取得线程列表。

#### Scenario: 从 Graphs 打开 Chat
- **WHEN** 已登录用户从 Graphs 选择 graph 并打开 Chat
- **THEN** 首个线程搜索请求不包含不受支持的 `error` 字段，且返回不为 `422`

#### Scenario: 线程搜索上游兼容失败
- **WHEN** LangGraph 因其他可选查询字段拒绝线程搜索请求
- **THEN** 前端可以使用现有兼容 fallback 重试，但必须保留可观测错误信息
