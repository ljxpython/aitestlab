## Why

当前聊天工作区使用的 `@langchain/vue` legacy transport 依赖 `/runs/stream`，而 LangGraph 已提供 Protocol v2 的 command/event 模型。Protocol v2 当前没有调用级 `context`，仓库现有契约却把可信身份、项目作用域和模型/工具/prompt 配置都放在 `RuntimeContext`；若直接迁移会迫使平台发明私有协议或污染 `metadata/configurable`。本 change 必须先按 Agent Server `Auth` 和标准 `config` 收拢运行契约，再迁移正式聊天并拆出 debug 工作台。

## What Changes

- 将聊天运行的正式传输面迁移为 LangGraph Protocol v2：`POST /api/langgraph/threads/{thread_id}/commands` 和 `POST /api/langgraph/threads/{thread_id}/stream/events`。
- 由 `platform-api` 在 v2 网关处完成 actor、项目、runtime policy 与审计校验，并向 `runtime-service` 签发短期、受众受限的 runtime delegation credential。
- 在 `runtime-service` 启用 Agent Server 原生 `Auth`；可信身份与项目上下文只由认证结果生成，客户端 command/config/metadata 不得覆盖。
- 将原 `RuntimeContext` 的职责拆为可信身份/项目上下文与类型化 `RuntimeOptions`；模型、工具、prompt 和生成参数通过标准 `run.start.params.config.configurable.platform_runtime` 传递，并在单一 resolver 边界装配。
- 将 `platform-web` 升级到 v2-native `@langchain/vue` runtime；实时消息、tool calls、interrupts、loading 和 thread id 仅来自 SDK 投影。
- 将现有静态 breakpoint debug 移至独立的开发调试工作台：它使用受控 legacy run 面，不作为正式聊天页面的 fallback，也不与正式聊天共享一次会话调用链。
- 不增加私有 Protocol v2 method/field，不用 assistant static context 绑定动态用户/项目，也不把可信身份字段放入 `input`、`metadata` 或普通 configurable headers。
- 保留现有 `/runs/*` 路由作为回滚和独立 debug 工作台的受控兼容面；正式聊天页面切换后不得同时维护 legacy 与 v2 两条调用链。
- **BREAKING（运行时契约）**：正式 Agent Server 调用不再接收顶层 legacy `context`；可信身份/项目由 Agent Server `Auth` 生成，业务运行参数只认类型化 `platform_runtime` config。
- **BREAKING（正式前端运行时）**：正式聊天页面不再提供静态 breakpoint debug，也不依赖 legacy `runs/stream` 语义；发布前必须通过 v2、动态 HITL interrupt 和回滚验证。

## Capabilities

### New Capabilities

- `chat-interaction-runtime`: 规定聊天运行的 Protocol v2 网关契约、SDK 实时状态所有权，以及发送、取消、中断、历史与分支的可验证行为。

### Modified Capabilities

无。

## Impact

- Owning locus：`apps/runtime-service`（Agent Server Auth 与运行上下文装配）、`apps/platform-api`（协议网关与 delegation 签发）和 `apps/platform-web`（SDK 消费方）。
- Affected chain：正式聊天 `BaseChatTemplate.vue -> usePlatformChatStream -> platform-api v2 gateway -> runtime-service Auth/context resolver -> LangGraph Protocol v2`；独立 debug 工作台 `platform-web -> platform-api legacy debug run -> LangGraph`。
- Execution band：`B3 Governed`。
- Standards loaded：
  - `docs/standards/01-ai-execution-system.md`
  - `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`
  - `apps/platform-api/docs/standards/permission-standard.md`
  - `apps/platform-api/docs/standards/audit-standard.md`
  - `apps/runtime-service/runtime_service/docs/standards/06-runtime-service-p2-contract-tightening.md`
  - `apps/platform-web/docs/control-plane-page-standard.md`
- 影响 `runtime-service` 的 current standard、Agent Server 配置、认证、runtime resolver、middleware/tools 与 harness；影响 `platform-api` runtime contract、upstream credential、授权/项目隔离与 SSE 行为；影响 `platform-web` 正式聊天 client、独立 debug 工作台、聊天状态和依赖。
- 发布采用受控切换与可回退的 legacy 路由保留策略；不迁移 thread 数据，不允许前端直连 upstream，不引入第二套正式聊天 adapter。
