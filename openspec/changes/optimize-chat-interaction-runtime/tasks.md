## 1. B3 基线与协议护栏

- [x] 1.1 恢复 SDK 试装遗留的 `apps/platform-web/pnpm-lock.yaml` 差异，并验证当前 legacy chat 基线
- [x] 1.2 为现有 `usePlatformChatStream`、actions、thread 切换和 interrupt 建立 characterization tests
- [x] 1.3 补齐 tool lifecycle、checkpoint metadata、legacy snapshot 与 viewport/composer 的最小 fixture
- [x] 1.4 将 `verification.md` 更新为 B3 review、证据、残余风险和 docs/runbook 决策的唯一记录

## 2. Runtime Service 可信运行契约

- [x] 2.1 修订 runtime-service current standard 与 harness：可信身份/项目只来自 Agent Server `Auth`，业务运行参数只来自类型化 `platform_runtime` config
- [x] 2.2 在 `langgraph.json` 启用 Agent Server `Auth`，验证 platform-api delegation credential，并对 thread/run 建立 project-scoped resource auth
- [x] 2.3 拆分可信身份/项目上下文与 `RuntimeOptions`，在单一 resolver 中从 `runtime.server_info.user` 和 `RunnableConfig` 生成 `ResolvedRuntimeRequest`
- [x] 2.4 让现有 `RuntimeRequestMiddleware`、model/tool resolver 和直接读取 `runtime.context` 的业务工具统一消费解析结果，删除正式链路 legacy context fallback
- [x] 2.5 覆盖 credential 缺失/过期/签名/audience/project mismatch、config 身份夹带、模型/工具越权和本地显式调试入口的 contract tests

## 3. Platform API Protocol v2 Gateway

- [x] 3.1 定义并测试 `POST /api/langgraph/threads/{thread_id}/commands` 的授权、项目作用域、标准 command envelope、`input.respond`、fork、错误与取消语义
- [x] 3.2 定义并测试 `POST /api/langgraph/threads/{thread_id}/stream/events` 的订阅过滤、SSE abort、`since` replay、单调 `seq`、tasks 与 values checkpoint 语义
- [x] 3.3 确认 static breakpoint 不属于 Protocol v2；将它限定为独立 legacy debug 工作台，而非正式聊天 fallback
- [x] 3.4 复用现有 `ActorContext` 与 project runtime policy 签发短期 delegation credential，并将模型、工具、prompt 与生成参数归一化到 `config.configurable.platform_runtime`
- [x] 3.5 将 credential、actor/project scope、审计和 runtime error normalization 接入 v2 upstream adapter，不增加私有 v2 字段或普通身份 headers

## 4. 前端 SDK 与实时状态收敛

- [x] 4.1 升级 `@langchain/vue`、`@langchain/core` 和 `@langchain/langgraph-sdk` 到经过 v2 gateway 验证的兼容版本，并更新 lockfile
- [x] 4.2 在现有 `usePlatformChatStream` 使用 v2-native SDK 投影与 command actions；不新增 custom transport、第二套 adapter 或 legacy/v2 页面分支
- [x] 4.3 以 SDK loading 与短暂 command pending 派生 busy，删除剩余 live messages/history/interrupt/branch 双写
- [x] 4.4 使用 SDK message metadata、tool calls 与动态 HITL interrupts 完成 retry/edit/fork、tool card 和单/多 interrupt 展示；保留仅有 fixture 证明的 snapshot normalization
- [x] 4.5 缩减 `BaseChatTemplate.vue` 的编排责任，并将已有消息视口/composer 局部交互归位到现有组件；正式聊天删除 static debug 开关

## 5. 独立 Debug 工作台

- [x] 5.1 复用既有 legacy runtime gateway run 能力建立显式 debug session/thread 入口，并沿用项目 runtime write 授权与审计
- [x] 5.2 在 debug 工作台承载 static breakpoint、legacy subgraph stream、继续和取消；禁止正式聊天自动跳转或共享协议会话
- [x] 5.3 补充 debug 工作台权限、会话隔离、breakpoint 恢复和正式聊天不 fallback 的测试

## 6. 契约验证、发布与验收

- [x] 6.1 运行 runtime-service Auth/resolver/harness 与 platform-api v2 route/adapter/authorization/runtime-contract tests，记录 credential、config、command、event、cancel、reconnect、fork 和动态 HITL 结果
- [x] 6.2 运行 platform-web chat 与 debug 工作台定向测试、LangGraph client/service specs、typecheck 和 build
- [x] 6.3 完成正式聊天 `platform-web -> platform-api -> runtime-service` 最短链集成验证，覆盖认证拒绝、credential tampering、项目隔离、runtime config、SSE replay、动态 HITL、tool call 与 cancel
- [x] 6.4 在桌面和移动视口人工验收正式聊天与独立 debug 工作台，覆盖发送、取消、interrupt、thread 切换、历史分支、编辑/重试、草稿恢复、自动跟随和会话隔离
- [ ] 6.5 记录 runtime delegation、两条入口的发布/回退步骤、未覆盖边界与 docs/runbook 结论；获得更新后 B3 owner acceptance 再 sync/archive
