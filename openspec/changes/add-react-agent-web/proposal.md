## Why

现有正式聊天前端使用 Vue，且正式运行同时存在 Protocol v2 command/event 与 legacy
`runs.stream` 等状态入口。用户需要一个独立的 React Agent 工作台，并要求 Run 在浏览器
断线后仍可持续、可查询并可恢复订阅，因此必须同时明确新的正式 UI 边界与 Durable Run
治理契约。

Owning locus：`apps/agent-web`、`apps/platform-api`、`apps/runtime-service`。
Affected chain：`agent-web -> platform-api -> runtime-service`。Execution band：B3
Governed，因为正式 gateway contract、迁移和生产发布语义将变化。已加载标准：
`docs/standards/01-ai-execution-system.md`、
`apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`、
`apps/runtime-web/docs/standards/runtime-web-debug-standard.md`。

## What Changes

- 新增 `apps/agent-web`：React Agent 工作台，采用三栏工作区、线程、消息/工具时间线、
  Inspector 与可访问的响应式设计。
- 新增正式 Durable Run resource：创建、查询、事件订阅、取消和 interrupt/approval 恢复
  具有单一受治理入口。
- **BREAKING**：正式 Agent Web 不再调用创建并隐式流式返回的 `runs.stream`；SSE 仅观察
  已创建的 Run，并以 Protocol v2 POST body 的 `since` 恢复。
- **BREAKING**：正式 Agent Web 以 Protocol v2 command/event 操作并观察 Durable Run；legacy
  `runs.stream` 不再是新前端生产 fallback，未批准前不得删除或切流旧路径。
- 保持 `runtime-web` 为内部调试壳，不将其直连 runtime 的模式迁入生产 UI。

## Capabilities

### New Capabilities

- `agent-workbench`: React 正式 Agent 工作台的工作区、可访问性和会话交互。
- `durable-run-stream`: 受治理的 Run 生命周期、幂等创建、可恢复 SSE、取消与恢复。

### Modified Capabilities

- `chat-interaction-runtime`: 正式 chat 的 Protocol v2 明确承载 Durable Run，需补齐 Bearer
  fetch SSE、snapshot 和 legacy `runs.stream` 退役/回退语义。

## Impact

- 新增应用：`apps/agent-web`，将安装独立 React/Vite 依赖并新增构建、测试和部署入口。
- 修改 `platform-api` runtime gateway 的公开 HTTP contract、鉴权/审计与 Run Coordinator。
- 修改 `runtime-service` 的 durable/checkpoint/可恢复 streaming 配置与验证。
- 修改 project operation 与审计记录，使每个 Durable Run 都有受治理的 operation 映射与生命周期证据。
- 修改正式聊天的生产入口；需要旧 `platform-web` 的受控回退计划和人工产品验收。
- 可借鉴 DeepSeek Harness 与 Open SWE 的 MIT 代码模式；实质复制时必须保留许可证。
