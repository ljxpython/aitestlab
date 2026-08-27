# React Agent Web 重设计

状态：Draft。本文档组描述将新建的 `apps/agent-web` 设计为 React Agent
工作台的方案；它不授权实施，也不替代 OpenSpec 中的受治理要求。

## 已确认的方向

- 新应用使用 React，不继续采用 Vue。
- 视觉语言参考 DeepSeek Harness 的克制三栏工作台、密度和亮暗主题，而非复制其
  Cordis 插件框架。
- AI 交互参考 Open SWE 的线程流、状态投影、工具生命周期和恢复体验。
- 正式生产路径固定为 `agent-web -> platform-api -> runtime-service`。
- Run 必须独立于浏览器存活；SSE 只观察和恢复，不是状态事实源。
- Durable Run 是执行与状态模型；Protocol v2 是正式命令与事件协议。新 Agent Web 用
  `fetch + ReadableStream` 携带 Bearer header 订阅 POST SSE，并以 `since` 主动重连。

## 文档地图

1. [参考项目与技术栈](./01-reference-and-stack.md)：可借鉴能力、依赖选择和明确排除项。
2. [产品与 UI 设计](./02-product-and-ui.md)：信息架构、三栏工作台、视觉令牌和响应式规则。
3. [Durable Run 架构](./03-durable-run-architecture.md)：正式 Run API、鉴权、SSE 恢复和迁移缺口。
4. [实施与验收计划](./04-delivery-and-acceptance.md)：分期、依赖顺序、验证矩阵和上线门禁。
5. [目标架构图](../diagrams/agent-web-target-architecture.drawio)：可编辑的跨服务架构与前端状态图。
   预览：[生产架构](../diagrams/agent-web-target-architecture.png)、[Run 生命周期](../diagrams/agent-web-durable-run-lifecycle.png)。

## 权威关系

| 内容 | 权威来源 |
| --- | --- |
| 正式需求、API 行为、实施任务、审批与验证 | `openspec/changes/add-react-agent-web/` |
| 当前 gateway 管理接口边界 | `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md` |
| `runtime-web` 调试入口边界 | `apps/runtime-web/docs/standards/runtime-web-debug-standard.md` |
| 产品、视觉和参考实现分析 | 本文档组（Draft supporting material） |

任何 API 或权限语义与 OpenSpec/leaf standard 冲突时，以后两者为准。
