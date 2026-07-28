# Verification

- Status: Complete
- Disposition: Accepted
- Pre-apply review: Approved
- Owner/reviewer: User
- Review basis: 2026-07-27 用户已审阅包含 runtime-service Agent Server Auth、标准 `platform_runtime` config、正式聊天 Protocol v2 与独立 debug 工作台的完整更新 artifacts，并明确批准实施。
- Final owner acceptance: 2026-07-28 用户明确接受最终验证结果、发布/回退方案与未覆盖边界，并批准完成任务 6.5；已验收实现提交为远端分支上的 `a5ab7bd`。

## Scope And Route

- Owning locus: `apps/runtime-service`（Agent Server Auth/context resolver）+ `apps/platform-api`（runtime gateway/delegation issuer）+ `apps/platform-web`（SDK consumer）
- Affected chain: 正式聊天 `BaseChatTemplate.vue -> usePlatformChatStream -> platform-api v2 gateway -> runtime-service Auth/context resolver -> LangGraph Protocol v2`；独立 debug 工作台 `platform-web -> platform-api legacy debug run -> LangGraph`
- Band: `B3 Governed`
- Governed surface: runtime-service 认证与运行上下文 current standard、platform-api 正式 runtime gateway/delegation 契约、项目作用域、SSE cancellation/replay 与外部协议兼容

## Planned Inputs

- Protocol v2 command envelopes：`run.start`、`input.respond`、cancel、fork/edit/retry 与 protocol success/error；不扩展私有 v2 字段
- Runtime trust：Agent Server `Auth`、短期 delegation credential、`runtime.server_info.user`、thread/run project resource auth 与拒绝客户端身份覆盖
- Runtime config：类型化 `config.configurable.platform_runtime`、model/tool/prompt allowlist、单一 resolver 与 legacy context 正式链路删除
- Event subscription：channels、namespaces、`since`、abort、reconnect、单调 `seq`、tasks 和 values checkpoint
- Debug workbench：独立 debug thread/session、legacy static breakpoint、subgraph stream、权限、审计和正式聊天不 fallback
- Governance：authenticated/unauthenticated actors、不同 project/thread scope、审计触发与 upstream error
- Chat fixtures：messages、tool calls、单/多 interrupts、checkpoint metadata、legacy snapshots、thread race、draft/viewport
- Dependency target：经 platform-api v2 contract 验证后选择的 `@langchain/vue`、`@langchain/core` 和 `@langchain/langgraph-sdk` 兼容组合

## Existing Evidence

### Runtime Trust Contract Harness

- Command: `cd apps/runtime-service && uv run pytest runtime_service/tests/harness/test_runtime_context_contract.py runtime_service/tests/harness/test_runtime_contract_tightening.py runtime_service/tests/harness/test_static_runtime_graph_contract.py -q`
- Input: `RuntimeContext`/`RuntimeOptions` 字段边界、`platform_runtime` 唯一业务参数来源、Agent Server user 唯一可信身份来源与静态 graph 契约。
- Result: 25 tests passed on 2026-07-27。
- Limitation: 本证据只固定 contract harness；delegation JWT、resource auth 与 gateway 证据见下节，真实部署最短链仍待任务 6.3。

### Runtime Auth And Resolver Implementation

- Commands:
  - `cd apps/runtime-service && uv run pytest runtime_service/tests -q`
  - `cd apps/runtime-service && uv run python -m compileall -q runtime_service`
  - `cd apps/runtime-service && uv lock --check`
- Input: Agent Server `Auth`、短期 delegation JWT、management service credential、thread project filter、可信 `server_info.user`、`platform_runtime` resolver、middleware/tools 和显式 local debug。
- Result: 207 tests passed on 2026-07-27；compileall 与 lock check 通过。此前完成的更宽 runtime-service 相关测试集合为 229 passed。
- Security matrix: 缺失、过期、错误签名、错误 audience、短 secret、project mismatch、management credential 访问 thread、config 身份夹带、未知 model/tool 均 fail closed；非 thread catalog/assistant 管理只接受独立 service API key。
- Limitation: 尚未启动带真实 Postgres/Redis 的 Agent Server 验证 auth propagation 和 event replay。

### Platform API Delegation And V2 Gateway

- Commands:
  - `cd apps/platform-api && uv run python -m unittest discover -s tests -p 'test_*.py'`
  - `cd apps/platform-api && uv run python -m compileall -q app`
  - `cd apps/platform-api && uv lock --check`
  - `docker compose -f deploy/docker-compose.stack.yml config --quiet`
  - `docker compose -f deploy/docker-compose.stack.nginx.yml config --quiet`
- Input: 独立 issuer settings、HS256 claims、ActorContext/project role、project model/tool policy、v2 command/event 标准路径、`platform_runtime` normalization、SSE byte proxy、审计 action 和普通身份 header 拒绝。
- Result: 104 tests passed on 2026-07-27；compileall、lock check、两份 compose config 均通过。
- Contract result: `POST /threads/{thread_id}/commands` 与 `POST /threads/{thread_id}/stream/events` 仅转发标准 envelope/body；浏览器 Authorization、`x-project-id` 和 tenant header 不进入 upstream。run delegation 与 management API key 使用独立 secrets。
- Limitation: 单元/adapter 证据不能替代动态 HITL 与完整浏览器最短链，因此任务 6.3 仍保持未完成。

### Protocol v2 Live Agent Server

- Command: 在公开测试 secret、独立 in-memory Agent Server `127.0.0.1:8124` 与故意不存在的 `platform_runtime.model_id` 下执行一次性 `httpx` 断言脚本；未使用真实模型、外部 API 或生产数据。
- Input: Agent Server 0.11.1；delegation Bearer、management `x-api-key`、两个 project、`run.start`、`input.respond`、checkpoint run、cancel、channels/namespaces、双订阅 abort 与 `since` replay。
- Auth result: 受保护 thread 无凭据返回 401；management credential 访问 thread 返回 403；delegation 创建 thread 时服务端写入认证 project；另一 project 读取返回 404。`/info` 按官方 Agent Server 行为保持公开。
- Command result: 非整数 id 返回标准 protocol error envelope；缺少 `interrupt_id` 的 `input.respond` 返回 `invalid_argument`；`run.start` 返回保留 command id 的 success envelope 和 run id；以持久 checkpoint id 再启动运行成功；标准 run cancel 返回 200，最终状态为 `interrupted`。
- Event result: 真流产生 `lifecycle(seq=1) -> values(seq=2) -> lifecycle(seq=3)`，序号严格单调；`since=2` 只回放 `seq=3`；关闭一个订阅不影响同 thread 的另一个订阅；channel 过滤只交付 lifecycle，根 namespace 事件不会泄漏给 `[["worker"]]` 订阅。
- Checkpoint result: `values` 事件携带当前消息状态，持久 thread state 返回 checkpoint id，后续 checkpoint run 可执行。网关单元测试同时固定 `tasks`/`values` channel、namespace、depth 和 since 请求不被改写。
- Limitation: 仓库没有无需模型即可产生 task 子任务事件的现成 graph，因此本次无费用 live probe 未产生 `tasks` 样本；tool/task 与动态 HITL 的浏览器最短链仍由任务 6.3 验收。

### Legacy Characterization Baseline

- Command: `cd apps/platform-web && pnpm vitest run src/modules/chat`
- Input: submit、cancel、finish/error、thread race、history single-writer、interrupt normalization fixtures
- Result: 19 files / 46 tests passed on 2026-07-27；同时确认 SDK 试装遗留的 `pnpm-lock.yaml` 已恢复到 `package.json` 的 legacy 依赖解析。
- Limitation: 仅证明 legacy/B2 前端行为，不能证明 Protocol v2 gateway 或正式发布兼容。

### Platform Web Protocol v2 SDK Migration

- Commands:
  - `cd apps/platform-web && pnpm typecheck`
  - `cd apps/platform-web && pnpm vitest run src/modules/chat src/services/langgraph/client.spec.ts src/services/runtime/runtime-contract.spec.ts`
  - `cd apps/platform-web && pnpm list @langchain/vue @langchain/core @langchain/langgraph-sdk --depth 0`
- Input: 官方 hosted Agent Server 形态 `useStream({ apiUrl, assistantId, threadId, fetch, callerOptions })`、reactive thread id、动态 project header、显式 project-scoped thread 创建、`platform_runtime` config、SDK messages/tool calls/interrupts/loading/error、message metadata `parentCheckpointId`、`forkFrom`、`respond/respondAll`、`stop`、持久 history 分支视图和 legacy snapshot fixture。
- Result: typecheck 通过；21 个测试文件、61 个测试通过；依赖解析为 `@langchain/vue 1.0.29`、`@langchain/core 1.2.3`、`@langchain/langgraph-sdk 1.9.28` 和 Vue `3.5.40`。npm registry 与 `@langchain/vue` peer contract 复核确认：三项 LangChain 依赖均为当前兼容最新版，`@langchain/vue 1.0.29` 要求 `@langchain/core ^1.1.48`、Vue `^3.0.0`，当前解析组合满足约束且无重复版本。
- Contract result: 正式聊天不再发送 `interruptBefore`、`interruptAfter`、`streamSubgraphs` 或顶层 runtime `context`；不再维护 `switchThread`、`setBranch`、live history 或 interrupt 镜像；首次发送在 control plane 显式创建 thread；正式页面已删除 static debug 开关。
- Limitation: 本节证明前端 SDK 适配与局部行为；真实 tool/task/HITL 浏览器最短链、构建和视口人工验收仍由任务 6.2-6.4 完成。

### Full Regression And Build

- Commands:
  - `cd apps/runtime-service && uv run pytest runtime_service/tests -q`
  - `cd apps/platform-api && uv run python -m unittest discover -s tests -p 'test_*.py'`
  - `cd apps/platform-web && pnpm exec vitest run src/modules/chat src/services/runtime-gateway/debug.service.spec.ts src/services/runtime-gateway/workspace.service.spec.ts src/services/langgraph/client.spec.ts src/services/runtime/runtime-contract.spec.ts src/router/routes.spec.ts`
  - `cd apps/platform-web && pnpm run build`
- Result: runtime-service 207 tests passed；platform-api 104 tests passed；platform-web 24 个文件、72 个测试通过；`vue-tsc --noEmit` 与 Vite production build 通过，生成独立 `ChatDebugPage` chunk。
- Warnings: Python 测试仍报告既有依赖 deprecation、测试用短 HMAC key 与 SQLite resource warning；均未导致失败，生产 secret 长度由现有启动校验约束。
- Limitation: production build 不替代真实浏览器视口和完整服务最短链，继续由任务 6.3-6.4 覆盖。

### Final Frontend Regression

- Commands:
  - `cd apps/platform-web && pnpm exec vitest run src/modules/chat src/services/runtime-gateway/debug.service.spec.ts src/services/runtime-gateway/workspace.service.spec.ts src/services/langgraph/client.spec.ts src/services/runtime/runtime-contract.spec.ts src/router/routes.spec.ts`
  - `cd apps/platform-web && pnpm exec vue-tsc --noEmit --pretty false`
  - `cd apps/platform-web && pnpm run build`
  - 对本 change 的 chat/debug/runtime gateway/router 文件运行定向 ESLint
  - `git diff --check`
  - `openspec validate optimize-chat-interaction-runtime --type change --strict --no-interactive`
- Result: 2026-07-28 依赖升级后的最终回归 24 个测试文件、77 个测试通过；Vue `3.5.40` 下 `vue-tsc --noEmit` 与 Vite production build 通过，1223 个模块完成转换并继续生成独立 `ChatDebugPage` chunk；diff check 通过。

### Independent Legacy Debug Workbench

- Commands:
  - `cd apps/platform-web && pnpm exec vue-tsc --noEmit --pretty false`
  - `cd apps/platform-web && pnpm exec vitest run src/services/runtime-gateway/debug.service.spec.ts src/router/routes.spec.ts src/modules/chat/composables/platform-chat-stream/helpers.test.ts src/modules/chat/composables/usePlatformChatStream.test.ts`
  - `cd apps/platform-web && pnpm exec eslint src/modules/chat/pages/ChatDebugPage.vue src/modules/chat/composables/platform-chat-stream/helpers.ts src/modules/chat/composables/platform-chat-stream/helpers.test.ts src/modules/chat/composables/usePlatformChatStream.test.ts src/router/routes.spec.ts src/services/runtime-gateway/debug.service.ts src/services/runtime-gateway/debug.service.spec.ts`
  - 在正式聊天 `BaseChatTemplate.vue`、`ChatPage.vue`、`usePlatformChatStream.ts` 和 actions 中检索 `runs.stream`、static breakpoint、subgraph stream 与 debug route 引用。
- Input: `/workspace/chat/debug` 路由、`project.runtime.write`、`session_kind: legacy_debug`、legacy run stream、tool static breakpoint、pending task 恢复、subgraph stream、cancel 和 legacy model/tool/system prompt context。
- Result: typecheck 通过；4 个测试文件、19 个测试通过；定向 ESLint 零问题；正式聊天静态边界检索零命中。
- Contract result: Debug 首次运行使用 `interruptBefore: ['tools']`，pending `task` 恢复使用 `interruptAfter: ['tools']`，`streamSubgraphs` 原样传递；debug thread 显式标记且不复用正式会话。正式聊天继续只使用官方 hosted `useStream`，不 fallback 到 legacy run，也不自动跳转 debug；debug route 未加入正式导航。
- Limitation: 本节是前端/service 契约证据；真实 Agent Server static breakpoint、浏览器取消和桌面/移动布局仍由任务 6.3-6.4 验收。

### Official Hosted useStream And Browser Shortest Chain

- Official basis: 2026-07-28 通过 LangChain Docs MCP 与 LangChain Reference MCP 复核 `@langchain/vue useStream`。官方 Vue 范式以 hosted Agent Server 的 `apiUrl`/`assistantId` 为入口，以 `messages`、`toolCalls`、`interrupts` 和 `isLoading` 为运行时投影，并通过标准 `respond`/`command.resume` 恢复动态 interrupt；static breakpoint 不属于正式聊天表面。
- Implementation result: 正式聊天删除手工 `HttpAgentServerAdapter`，`fetch` 与 `callerOptions.fetch` 共用动态 `scopedFetch`，统一注入浏览器 Authorization 与当前 `x-project-id`。hydration/state、command 及 SDK 按职责建立的两条 event SSE 订阅均返回 200；两条订阅是 SDK 的独立投影订阅，不是重复运行。
- Live result: 新 thread 创建、state hydration、Protocol v2 command/events 与取消真链通过，浏览器控制台零错误。取消证据包括 thread `019fa675-5092-7ec1-9c3c-dbbdca9d9b68` / run `019fa675-51b6-7720-846b-8d2ed3a4d93c`，thread `019fa67b-2cb4-7a70-a7ce-51990cb89cf9` / run `019fa67b-2d91-7243-b41b-beb2fd7dfea6`，以及受控配置探针 thread `019fa684-b523-71f3-90f4-03480b376e81` / run `019fa684-b60b-7122-b162-1acda903176b`；三次 SDK `stop()` 均触发标准 `/runs/{run_id}/cancel?wait=0&action=interrupt` 并返回 200。
- Actual port-3000 delegation result: 先前独立 `3003` 验收实例没有覆盖用户实际 `3000` 启动链，因而漏掉两端本地服务配置未注入同一 delegation secret 的问题。修复被 Git 忽略的 `platform-api` 与 `runtime-service` 本地 `.env` 后重启两端服务，真实 `3000 -> 2142 -> 8123` 链路在 thread `019fa72d-398f-7f80-a615-3d9a22f3caeb` / run `019fa72d-3b9e-77a2-b424-bc35451d95b8` 上完成 `run.start`；command、两条 `/stream/events` 均返回 200，模型请求返回 200，后台运行成功。持久 state/history 含用户消息及最终回复 `delegation E2E passed`，页面使用自带“重新同步”后显示两条消息，控制台零错误。验证记录不包含 delegation secret、登录密码或浏览器 token。
- DeepSeek browser HITL result: 重启正式 `runtime-service 8123`、`platform-api 2142` 和独立验收前端 `3003` 后，在同一浏览器正式聊天 thread `019fa6c4-ef39-7a22-8793-413d98693846` 完成 `platform-web -> platform-api -> runtime-service -> DeepSeek` 全链。run `019fa6c4-f053-71f2-949a-d8c624f95684` 生成 `submit_high_impact_action(action=deploy, details=browser deepseek protocol v2 acceptance)` 与动态 interrupt `270fe0a634e9907c8f5dcf976ab13277`；重新挂载同一 thread 后 SDK 水合消息、tool call 和审批卡，两条 `/stream/events` 均为 200。点击审批后 `POST /api/langgraph/threads/019fa6c4-ef39-7a22-8793-413d98693846/commands` 返回 200，interrupt 清空，9 个 history snapshots 包含获批工具结果，页面展示最终 DeepSeek 回复且控制台零应用错误。
- UX result: `onCompleted({ reason: 'stopped' })` 现在准确提示输入框恢复可编辑，不再声称已提交消息会回填为草稿；回归测试固定 `preserveInfo: true`。
- New-thread flicker result: 官方文档规定将响应式 `threadId` 设为 `null` 即清除当前 thread 绑定；实际 `@langchain/vue 1.0.29` 首次 threadId 变更存在短暂保留上一投影的窗口。修复前真实 `3000` DOM 时序捕获到新对话头部显示“未创建”时仍展示上一 thread 消息，首次发送后又闪出约 480ms 的“正在恢复聊天上下文”。展示边界现在只消费 `stream.threadId` 与 active thread 一致的 messages/values/tool calls/interrupts；首次提交先让 SDK 建立新 thread 投影，再公开 active thread id；聊天路由同步 threadId 时同时保留已知 target，避免工作区卸载重挂。修复后 thread `019fa77a-10d9-7cc1-b3dc-1ad22d435cd8` 的 6 次 MutationObserver 采样均为 `anyStale=false`、`anyRestoring=false`，页面持续展示 optimistic human message并最终显示 `DOM_CLEAN_PASS_20260728`，控制台零错误。

### Dynamic HITL Compatibility Boundary

- Runtime contract: `submit_high_impact_action` 是 assistant graph 的 required tool；`enable_tools` 仅决定 public optional tools，关闭它也不会移除 required HITL tool。因此把正式聊天 Tools 开关设为 true 只是诊断变量，不是架构修复。
- Debug control: 独立 debug thread `019fa678-7a38-7fa3-a113-af8ea392a3b2` 使用 `session_kind=legacy_debug` 和 legacy `/runs/stream`。同一运行环境下，精确提示成功生成名称为 `submit_high_impact_action` 的调用及 `action=deploy`、`details=legacy debug acceptance` 参数，并在 static breakpoint 暂停；动态 HITL payload 包含 `approve`、`edit`、`reject`。
- Failed proxy control: 正式 v2 在 Tools 关闭与开启两种配置下，原 OpenAI-compatible 代理都连续返回空 `function.name`；持久状态因而出现多条无名称 tool call，runtime 将其判定为无效工具并继续模型循环。第三次 `enable_tools=true` 探针复现后已立即取消。页面只投影 SDK/持久状态，不负责生成或重复这些调用。
- DeepSeek native tool-call result: `deepseek_chat` 解析为 DeepSeek 官方 endpoint 上的 `deepseek-v4-flash`。thinking mode 不支持强制 `tool_choice=submit_high_impact_action`，返回预期 400；移除非正式链所需的强制选择后，模型返回 1 个合法 `submit_high_impact_action` tool call，参数为 `action=deploy`、`details=deepseek v2 compatibility probe`，且 `invalid_tool_calls=0`。
- DeepSeek Protocol v2 HITL result: 隔离 Agent Server `127.0.0.1:8124` 上的 thread `019fa6a7-b165-7dd2-adfc-2994d8c7fdc9`、run `019fa6a7-b16e-7a00-a84a-e97d80ae3e88` 成功产生动态 `submit_high_impact_action` interrupt，参数为 `action=deploy`、`details=deepseek protocol v2 acceptance`，允许 `approve/edit/reject`；使用标准 `input.respond` 与 `decisions: [{ type: \"approve\" }]` 恢复成功，最终 thread 状态为 `idle`，9 个 history snapshots 包含获批后的工具执行结果。
- Disposition: DeepSeek 已解除模型/runtime 侧的正式 v2 tool-call 与动态 HITL 兼容性阻塞，并已通过同一次浏览器正式聊天的 `platform-web -> platform-api -> runtime-service -> DeepSeek -> approve/resume` 全链；原代理仅保留为失败对照。禁止前端猜测工具名、增加私有 transport 或恢复正式聊天 legacy fallback。

### Desktop And Mobile Human Acceptance

- Viewports: 正式聊天桌面截图 `.playwright-cli/chat-v2-desktop.png`、移动截图 `.playwright-cli/chat-v2-mobile.png`；debug 移动修复后截图 `.playwright-cli/chat-debug-mobile-fixed.png`。390x844 下正式聊天与 debug 均满足 document `scrollWidth === clientWidth === 390`，控制台零错误。
- Mobile fix: debug 的 CSS Grid 子项原先受 UUID 与事件内容的 min-content 宽度撑到 469px；仅在 `aside` 与 `main` 增加 `min-w-0` 后恢复为 390px，没有用页面级裁切掩盖内容。
- Interaction result: 正式聊天发送、三次取消、自动跟随/暂停提示、会话列表、thread 切换、编辑与重试入口均可操作；在探针 thread 输入 `draft isolation acceptance` 后切换到另一 thread 输入框为空，切回后草稿恢复。历史编辑入口成功进入并可取消，未触发额外运行。
- Debug result: 独立 debug 页面真实创建 legacy session、产生 events/tasks/values/state、成功停在 tool static breakpoint，并展示 Continue；正式 chat 与 debug thread/session 完全隔离，debug 未进入 v2 command/events。

### Failed SDK Compatibility Probe

- Command: 安装目标 `@langchain/vue` 与配套依赖后，检查公开类型、transport 与现有 runtime gateway 路由
- Result: Blocked on 2026-07-27；目标 SDK 使用 Protocol v2 command/event 面，当前 gateway 仅有 legacy `/runs/*`。现有 submit debug 参数也未出现在新版前端 submit surface。
- Disposition: 试装依赖必须在任务 1.1 恢复；不得以 custom transport、类型断言或前端直连绕过网关。

### Protocol v2 Debug Compatibility Gate

- Command: `cd apps/platform-api && uv run python -c "from langchain_protocol.protocol import EventStreamRequest, RunStartParams; ..."`
- Input: 锁定的 `langchain-protocol 0.0.18` Python TypedDict CDDL 产物，以及现有 `LangGraphRunsSdkAdapter._CREATE_FIELDS`。
- Result: `RunStartParams` 仅定义 `assistant_id`、`input`、`config`、`metadata`；不定义现有运行链使用的 `interrupt_before`、`interrupt_after`、`stream_subgraphs` 或 `context`。`EventStreamRequest` 确认支持 `channels`、`namespaces`、`depth` 和 `since`。
- Disposition: Static breakpoint 阻断已由 owner 决策解除：正式聊天不使用 static breakpoint，独立 debug 工作台保留它。运行上下文协议缺口由后续 Runtime Context Gate 与更新后的 Auth/config 设计处理。

### Protocol v2 Runtime Context Gate

- Commands:
  - LangChain Docs MCP：读取 Protocol v2 command、Agent Server changelog、assistant context 与 configurable headers 文档。
  - LangChain Reference MCP：检查 `@langchain/langgraph-sdk` 的 `RunsInvokePayload` 与 Protocol v2 `RunStartParams` 可见类型。
  - `cd apps/runtime-service && uv run python -c "from langchain_protocol.protocol import RunStartParams; print(RunStartParams.__annotations__)"`
- Input: 当前 `RuntimeContext` 契约、锁定的 `langchain-protocol 0.0.18`、当前 Agent Server 配置与截至 2026-07-27 的官方 Protocol v2 文档/changelog。
- Result: Blocked on 2026-07-27。Protocol v2 `run.start.params` 仍只定义 `assistant_id`、`input`、`config`、`metadata`，没有调用级 `context`。官方 assistant `context` 是静态 assistant 配置；configurable headers 只进入 `config.configurable`。两者都不能等价承载每次运行变化的 `RuntimeContext`，尤其不能在不违反 runtime-service current standard 的情况下传递 `project_id`。
- Contract conflict: `apps/runtime-service/runtime_service/docs/standards/06-runtime-service-p2-contract-tightening.md` 要求 `project_id` 只能来自 `RuntimeContext.project_id`，并明确禁止从 `metadata`、`config.configurable`、state 或 prompt 推断。
- Disposition: Owner 已选择跨 locus 方案 B。更新设计采用 Agent Server `Auth` 生成可信身份/项目，并仅用标准 v2 `config` 承载无身份字段的运行配置；完成更新后 B3 review 前不恢复 apply。

## Planned Evidence

### Local

- `runtime-service` Agent Server Auth、credential、runtime resolver、middleware/tool 与 harness tests
- `platform-api` delegation、v2 route、adapter、authorization、normalization 与 runtime-contract tests
- `platform-web` chat/client/service tests、`pnpm typecheck`、`pnpm build`

### Shortest Chain

- 正式聊天的认证 `platform-web -> platform-api -> upstream` command/event 集成：start/respond、tool calls、动态 HITL、cancel、fork、context 映射、disconnect 和 `since` replay；独立 debug 工作台验证 static breakpoint 与会话隔离。

### Formal And Human

- B3 owner 对更新后的 proposal、design、specs、tasks 和本文件的整体批准。
- 桌面/移动真实页面验收，以及正式聊天 release 回滚和 debug 工作台独立关闭验证。

## Uncovered Boundaries

- 生产网络代理和长期断线行为需要在部署环境补充观察。
- legacy `/runs/*` 的最终退役与其他调用方迁移不在本 change。
- DeepSeek 已通过原生 tool calling、隔离 Agent Server Protocol v2 动态 HITL/approve，以及重启后正式浏览器全链；当前不再存在模型/runtime 或前端动态 HITL 兼容性阻塞。
- delegation credential 的签名、audience、project 绑定和部署注入已由 contract tests 与隔离真链覆盖；生产密钥轮换仍沿用部署 secret 更新与服务滚动重启流程，本 change 不引入在线双 key 轮换。

## Docs And Runbook Impact

- 本 change 的 OpenSpec artifacts 和本文件是唯一规划/验证事实源。
- 发布：先部署 runtime-service Agent Server Auth/context resolver 与 delegation secret，再部署 platform-api v2 gateway/issuer，最后发布 platform-web hosted `useStream`；每一步先检查 health，再用独立 project thread 验证 auth、state、command、events 和 cancel。正式聊天发布前必须换用通过 tool-call 兼容性验证的模型端点，或保持该入口不对生产用户开放。
- 正式聊天回退：回退 platform-web 与 platform-api 到上一已知版本，并同时回退对应 runtime contract；不得让正式页面自动 fallback 到 legacy `/runs/stream`，不得混用 v2 thread 与 debug thread。
- Debug 发布/回退：debug 工作台由独立路由和权限控制，可单独撤下前端路由/入口；legacy gateway 能力继续服务已有显式 debug 调用方，不影响正式 v2 聊天。
- Runtime delegation 回退：撤回新流量后回退 platform-api/runtime-service 配置与版本；轮换或移除本次 delegation secret 前先确认没有活动 v2 run。浏览器永远不持有 delegation credential。
- 文档结论：`apps/runtime-service/runtime_service/docs/standards/06-runtime-service-p2-contract-tightening.md`、部署示例、环境矩阵和 deployment guide 已随实现更新；无需新增第二份 runbook，避免与本 B3 验证记录形成影子标准。
- Acceptance result: Owner 已接受上述真实 `3000` delegation 修复证据、发布/回退步骤与未覆盖边界；任务 6.5 可以完成，change 可以进入 sync/archive。
