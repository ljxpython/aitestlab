# Platform Runtime Integration 实施状态

- 文档类型：Harness supporting implementation record
- 状态：`L1 local-complete; L2 local-complete; L3 partial`
- 更新时间：2026-09-05
- 权威任务：[`openspec/changes/redesign-platform-runtime-integration/tasks.md`](../../../../../openspec/changes/redesign-platform-runtime-integration/tasks.md)
- 权威证据：[`verification.md`](../../../../../openspec/changes/redesign-platform-runtime-integration/verification.md)

本文按 Harness 的 `功能点 -> 概念 -> 实施 -> 代码落点 -> 验证 -> 状态` 记录当前实现。这里不把
mock、fake 或未执行的人工验收写成完成。

## 0. Workflow Demo 真实模型化与多轮消息修复（2026-09-05）

| 项目 | 记录 |
| --- | --- |
| 功能点 | 同一个 Thread 连续发送多条 Chat 消息时，每一轮都处理当前最新的 user/human 输入。 |
| 概念 | `workflow_demo` 现在是“真实模型 Agent + 外层 Workflow/HITL”的组合；Thread 的 `messages` 会由 LangGraph reducer 累积历史人机消息。 |
| 根因 | `prepare()` 只有在持久化 `state["message"]` 为空时才读取 `messages`。第一轮保存“你好”后，第二轮虽然追加了新 user 消息，却继续使用第一轮的 `message`。 |
| 实施 | `get_agent()` 按 Runtime Context 构造真实 `create_agent` 模型子图；普通 `respond` 节点调用该子图，`requires_confirmation=true` 仍先走 interrupt。`prepare()` 从 `messages` 末尾反向查找最新非空 user/human 消息；Resume 没有新用户消息时继续保留已保存的 `message`。 |
| 代码落点 | `apps/runtime-service/src/runtime_service/services/demo/workflow_demo/agent.py`、`workflow.py`；回归测试 `apps/runtime-service/tests/services/workflow_demo/test_agent.py`；说明 `apps/runtime-service/src/runtime_service/services/demo/workflow_demo/README.md` |
| 验证 | Workflow Demo 定向测试 `7 passed`；Runtime 全量 `200 passed, 21 skipped`；本机真实 Provider 两轮 smoke 通过，第二轮实际使用新输入并得到不同模型回答。 |
| 状态 | `local-complete` |

`workflow_demo` 与 `reference_agent` 都是真实模型 Agent；前者额外保留 Workflow 条件路由和显式 HITL
确认能力，后者是无外层路由的通用参考 Agent。

## 1. Agent 与 Thread 绑定

| 项目 | 记录 |
| --- | --- |
| 概念 | 产品使用 Agent；`agent_key = graph_id`，SDK 的 `assistant_id` 只是协议字段名。Thread 首次 Run 绑定 Agent，后续不可切换。 |
| 实施 | Gateway 按 `(project_id, graph_id)` 校验目标；durable run 保存 `agent_key`；不同 Agent 返回 `agent_thread_mismatch`。Agent CRUD 只改 Platform 数据，不再创建、更新、删除或 resync upstream Assistant；旧列只作读取兼容。 |
| 代码落点 | `apps/platform-api/app/modules/runtime_gateway/application/service.py`；`.../runtime_gateway/infra/sqlalchemy/models.py`；`.../agents/application/service.py`；`.../agents/infra/sqlalchemy/repository.py` |
| 验证 | `tests.test_durable_run_coordinator`、`tests.test_runtime_gateway_runtime_contract`、L2 smoke active/cross-project cases |
| 状态 | `local-complete`；旧 `assistants` 包仅为兼容导出。owner 已确认无需保留旧 `graph_id=assistant` 记录及 profile，物理记录已删除；历史列/兼容代码清理仍单独受 migration 证据约束。 |

## 2. Runtime Context 与 Policy

| 项目 | 记录 |
| --- | --- |
| 概念 | Context 只允许 `model_id`、`temperature`、`max_tokens`、`top_p`、`tools`；优先级为显式 Run > Agent defaults > Project default model。`tools` 的缺失、空列表和服务端子集保持三态语义。 |
| 实施 | Gateway 消费 v2 扩展并通过标准 Runs 顶层 `context` 传递；未知字段、身份字段、越权模型/工具在 upstream 前拒绝。 |
| 代码落点 | `apps/platform-api/app/core/runtime_contract.py`；`apps/platform-api/app/modules/runtime_gateway/application/service.py`；`apps/runtime-service/src/runtime_service/runtime/resolver.py` |
| 验证 | `uv run --frozen python -m unittest tests.test_runtime_gateway_runtime_contract tests.test_runtime_delegation -q`；Runtime resolver tests |
| 状态 | `local-complete`；本机真实链已观察标准 Runs 选项和 `workflow_demo` HITL respond，浏览器完整链与事件去重仍为 `partial`。 |

## 3. Delegation scope

| 项目 | 记录 |
| --- | --- |
| 概念 | delegation 除 project/tenant 外带可选 `scope.operation`，将只读操作与 Run 创建/恢复操作分开。 |
| 实施 | Platform 仅签发 `read` 或 `run-create`；Runtime Auth 对未知 operation fail closed，并透传到 `runtime_scope`。Runtime Tools 管理页路由和可见导航已移除，tools catalog 仅作为执行/策略内部数据。 |
| 代码落点 | `apps/platform-api/app/core/security/tokens.py`；`apps/platform-api/app/modules/runtime_gateway/presentation/http.py`；`apps/runtime-service/src/runtime_service/runtime/auth.py` |
| 验证 | `tests.test_runtime_delegation`；`tests/runtime/test_auth.py`；L2 smoke（重启 runtime-api/worker 后仍可执行） |
| 状态 | `local-complete`；生产 RS256/JWKS 不属于本 change。 |

## 4. Durable Run 一致性

| 项目 | 记录 |
| --- | --- |
| 概念 | 所有正式 Run create 进入统一 `LaunchRuntimeRun`；先写 durable intent，再用 `Idempotency-Key + request digest` 创建上游 Run；超时进入 `run_start_unknown`，reconciliation 只按 marker 查找，不重放 create。 |
| 实施 | 同 key/digest 复用同一 Run；不同 digest 返回 409；active Run（包括 HITL 等待）占用 Thread；终态快照释放占用。 |
| 代码落点 | `apps/platform-api/app/modules/runtime_gateway/application/service.py`；`.../runtime_gateway/application/executor.py`；`.../operations` |
| 验证 | `uv run --frozen python -m unittest tests.test_durable_run_coordinator tests.test_runtime_gateway_runtime_contract -q`；结果 `28 tests OK` |
| 状态 | `local-complete`；当前复用 `operations` 表作为 outbox-like intent，独立 outbox 表和定时扫描不属于本轮必要实现。 |

## 5. SSE、响应与取消

| 项目 | 记录 |
| --- | --- |
| 概念 | SSE 断开只影响订阅，不取消 Run；只有显式 Stop/Cancel 调用 cancel endpoint。事件流在 Gateway 输出前做敏感字段脱敏。 |
| 实施 | Gateway 固定 `cancel_on_disconnect=false`；`input.respond` 只接受 active Run 的未解决 interrupt；协议事件校验和 cancel 错误统一映射。 |
| 代码落点 | `apps/platform-api/app/modules/runtime_gateway/application/service.py`；`.../runtime_gateway/presentation/http.py`；`apps/platform-web/src/modules/chat/composables/usePlatformChatStream.ts` |
| 验证 | `tests.test_runtime_gateway_runtime_contract`、`tests.test_runtime_gateway_event_redaction`、SDK adapter tests、L2 SSE/cancel smoke |
| 状态 | `local-complete`；真实 `workflow_demo` 已进入 `interrupted`，同 Thread 新 Run 返回 `409 thread_active_run_conflict`，`input.respond` 后最终 `success`；浏览器完整 respond/cancel E2E 未执行。 |

## 6. 模型配置

| 项目 | 记录 |
| --- | --- |
| 概念 | 最小七字段：`provider`、`display_name`、`base_url`、`protocol`、`model`、`api_key`、`enabled`。API key 只写不读，服务端使用部署级 Fernet master key 加密。 |
| 实施 | `/workspace/models` 提供七字段录入/编辑；URL/protocol/model 校验；GET/list 仅返回 `credential_configured`；disabled 模型在 Gateway 前置拒绝；错误 master key 或坏密文 fail closed。Gateway 现在签发短期 opaque model reference，Runtime 通过内部端点读取解密连接并构造 Provider；API key 不进入浏览器、Run、GraphHarbor 或日志。 |
| 代码落点 | `apps/platform-api/app/modules/runtime_catalog/application/service.py`；`.../application/credentials.py`；`.../runtime_catalog/presentation/http.py`；`apps/platform-web/src/modules/runtime/pages/RuntimeModelsPage.vue`；`apps/runtime-service/.env` |
| 验证 | `tests.test_runtime_catalog_delegation`；L2 disabled-model negative smoke；Platform Web model page tests；`tests/services/workflow_demo/test_agent.py`（标准 `messages` 输入） |
| 状态 | `local-complete`（目录和凭据闭环）；模型配置到 Runtime 执行的接入及 profile/E2E 移除待实施。当前不引入独立模型代理、Secret Store、execution reference 或 revision。 |

## 7. Agent API 命名迁移

| 项目 | 记录 |
| --- | --- |
| 概念 | 产品公开命名使用 Agent；旧 Assistant URL 只作为有期限的兼容入口，不能形成第二套执行 ID。 |
| 实施 | 新增 `/api/projects/{project_id}/agents`、`/api/agents/{id}` 全套 CRUD/resync 别名；Web service 已切换 Agent URL。 |
| 代码落点 | `apps/platform-api/app/modules/assistants/presentation/http.py`；`apps/platform-web/src/services/assistants/assistants.service.ts` |
| 验证 | Platform API route/import tests；Platform Web typecheck 与 unit tests |
| 状态 | `local-complete`；底层 Python module 名称仍是兼容别名，旧 upstream Assistant mutation 未再被新 Agent CRUD 调用，物理删除另由清理任务处理。 |

## 8. 未完成边界

以下不是代码遗漏，而是没有可信输入或需要额外人工/真实环境证据：

- 真实 HITL graph 的浏览器 respond/retry 链路；服务端 `workflow_demo` respond 已通过；
- 完整浏览器 E2E 与 owner 页面 UAT；
- 浏览器已覆盖登录、切换 `dev`、Agent 目录（`reference_agent`、`workflow_demo`）、Graphs 目录、Chat 页面和 console errors=0；完整浏览器 send/stream/reopen/HITL/respond/cancel/cross-project 流程仍未全部执行。
- 生产 Provider、Secret Store、RS256/JWKS、execution reference 和模型代理治理；这些已被 owner 废弃，未来需另立 change；
- 历史 Thread inventory、legacy upstream Assistant mutation 删除；
- 独立 outbox 表、生产定时扫描、性能 SLO 和灰度回滚。

## 9. 本轮浏览器证据（2026-09-05）

| 场景 | 输入/动作 | 结果 | 状态 |
| --- | --- | --- | --- |
| Chat 空态 | `/workspace/chat`，当前登录会话 | 页面显示 Agent Chat、Thread 未创建、发送按钮按空输入禁用；console Errors=0 | `local-complete` |
| Agent 目录 | `/workspace/assistants`，项目 `dev` | 页面显示 `reference_agent`、`workflow_demo` 两个 Agent，console Errors=0 | `local-complete` |
| Graph 目录 | `/workspace/graphs` | 页面显示 `reference_agent`、`workflow_demo`，console Errors=0 | `local-complete` |
| Chat 页面 | `/workspace/chat` | 页面正常加载，Agent 选择和空态可见，console Errors=0 | `local-complete` |
| 真实 Chat Run | send/stream/reopen/HITL/respond/cancel/cross-project | 服务端真实链已覆盖 `workflow_demo` HITL；浏览器端完整交互尚未逐项执行 | `partial` |

浏览器验收可由本地 Playwright 自主执行；当前已完成页面级验收，完整交互仍需单独执行并保留截图/网络证据。

## 10. 本轮简化方案规划（2026-09-05）

详细方案见 [模型目录与前端信息架构简化方案](./12-simplified-model-and-ui-plan.md)。本轮新增需求不把
环境变量当作产品配置：

| 功能点 | 概念 | 代码落点 | 验证 | 状态 |
| --- | --- | --- | --- | --- |
| 移除 `RUNTIME_MODEL_PROFILE` | 启动不再选择静态兼容目录，模型由 Platform Catalog 管理 | validator、`.env.example` | 配置测试通过；profile 不再参与启动 | `local-complete` |
| 移除 `RUNTIME_E2E` | 全链路 smoke 默认执行；Provider 使用独立测试分类 | Runtime README、`tests/e2e` marker | Runtime 定向测试 8 passed | `local-complete` |
| 模型配置真实执行 | 页面录入的 URL/protocol/model/key 参与 Runtime resolver | `runtime_catalog`、`runtime_gateway`、`runtime_service/runtime/modeling.py`、`reference_agent` | opaque reference 与内部解密读取已通过定向测试；本机真实录入后 Run 待执行 | `in-progress` |
| Chat active Run 409 恢复 | active/HITL Run 仍阻止同 Thread 新建 Run；前端不得显示 `[object Object]`，冲突后应恢复最新 Thread 状态 | `apps/platform-web/src/services/langgraph/client.ts`、`services/runtime-gateway/workspace.service.ts`、`modules/chat/composables/platform-chat-stream/actions.ts`、`apps/platform-api/app/modules/runtime_gateway/application/service.py` | Web 24 项定向测试通过；Gateway 对历史 active ledger 先读取执行事实，仅在明确终态时收敛；durable coordinator 17 tests 通过 | `local-complete` |
| Chat 生命周期语义 | 切换 Thread、SSE/SDK 订阅结束与显式 Stop 必须区分；前两者不得写成取消 | `modules/chat/composables/usePlatformChatStream.ts`、`platform-chat-stream/actions.ts` | Web 124 tests、typecheck、lint（0 error）；真实浏览器新对话无 cancel 请求 | `chain-complete` |
| Agent 产品收敛 | 用户只操作 Agent；Graph 作为内部部署目录 | `AppSidebar.vue`、`routes.ts` | Models 一级入口，Graph/Runtime/Policy 隐藏；Web typecheck 通过 | `local-complete` |
| 策略页面收敛 | 后端 deny-first 保留，模型/Agent 控件并入对应页面 | `RuntimePoliciesPage.vue`、Models/Agents pages | Models 提供项目默认模型操作；策略入口隐藏；typecheck 通过 | `local-complete` |

当前仍保留既有实现和验证记录，直到上述任务完成；不得把本规划误写成已经实现。

### 10.1 Chat 409 active Run 修复记录（2026-09-05）

**现象**：同一 Thread 已存在 active Durable Run（包括等待 HITL 的 `interrupted` Run）时，重复发送会由
Gateway 正确返回 `409 thread_active_run_conflict`，但 LangGraph SDK 读取 Platform 的嵌套错误 envelope
`{error: {code, message}}` 时把对象插值成 `Protocol request failed: 409 Conflict — [object Object]`。

**处理**：同源 SDK fetch 对非 2xx 的嵌套 Platform error 做兼容扁平化；统一错误归一化支持嵌套
`code/message`，并为 active、启动中和幂等冲突提供明确提示；Chat submit/respond/retry/edit 遇到 409 后
刷新当前 Thread snapshot，若存在 interrupt 则恢复 HITL 面板。SSE 断开不取消 Run，后端 active 保护不变。

**验证**：`apps/platform-web` 的 `client.spec.ts`、`workspace.service.spec.ts`、
`platform-chat-stream/actions.test.ts`、`usePlatformChatStream.test.ts` 共 24 tests passed；typecheck 和
eslint 通过。真实浏览器完整 send/stream/reopen/respond/cancel 仍是 5.5/7.4 门禁。

### 10.2 Chat SSE 终态遗漏修复记录（2026-09-05）

**现象**：真实 Run 已为 `success`，但首次浏览器发送仍停在“Agent 正在处理当前回合”，导致后续发送被
active Run 保护正确拒绝。

**根因与处理**：GraphHarbor 生命周期与 SDK 兼容事件在 Gateway 统一为
`running/completed/failed/interrupted`；终态帧同时收敛 durable ledger。对 SDK 首次提交的双 SSE 订阅竞态，
前端只在 Gateway `GET Run` 已明确返回终态时调用 `stop({ cancel: false })` 结束本地订阅并刷新历史，绝不以
断线或超时释放 Run，也不发送 cancel。

**验证**：真实 Thread `0a8a5048-7cbe-4839-88fc-d8499effd443` 的 lifecycle 为根命名空间
`seq=1 running` 与 `seq=32 completed/success`；首次 send、刷新 reopen、同 Thread 第二次 send 均成功进入
后端命令链，未再出现 `thread_active_run_conflict`。Platform API 21 个定向 unittest 与 Platform Web typecheck
通过。HITL/respond/显式 cancel 仍为 `partial`。

### 10.3 历史 active ledger 事实收敛（2026-09-05）

**现象**：用户从 Agent 页面打开历史 `workflow_demo` 对话并发送消息时，Gateway 返回
`thread_active_run_conflict`。该 Thread 的 Platform `runtime_runs` projection 仍是
`running/active_key=1`，但没有待处理的 interrupt，导致本地保护永久阻塞后续 Run。

**根因**：此前收敛只由 SSE 终态帧或显式 `GET Run` 触发。若浏览器未订阅到历史 Run 的终态，新的
`LaunchRuntimeRun` 会直接按 ledger 拒绝，不会向 GraphHarbor 查询执行事实。这个错误不能通过按时间释放
或自动取消解决，因为 `running`、`interrupted`、`run_start_unknown` 和 cancel-requested 都必须继续阻塞。

**处理**：统一 `LaunchRuntimeRun` 在不同 idempotency key 遇到已有 active Run 时，先读取对应的
GraphHarbor Run。只有 `success/succeeded/completed/error/failed/timeout/cancelled/canceled` 才调用既有
terminal sync 清除 active slot；读取失败、无 `run_id`、`running`、`interrupted` 和 cancel-requested 保持
原有冲突语义。相同 idempotency key 不额外读取或创建 Run。

**代码落点**：
`apps/platform-api/app/modules/runtime_gateway/application/service.py` 的
`_reconcile_active_durable_run_before_launch()`；
`apps/platform-api/tests/test_durable_run_coordinator.py`。

**验证**：本机报告 Thread 的执行事实为 `error`，正常 Gateway `GET Run` 后 ledger 从
`running/active=true` 收敛为 `failed/active=false`。定向执行
`python -m unittest tests/test_durable_run_coordinator.py`（17 tests）和
`python -m unittest tests/test_runtime_gateway_runtime_contract.py`（19 tests）均通过，且
`git diff --check` 通过。

**浏览器真实链**：按 `dev -> /workspace/assistants -> Workflow Demo HITL -> 打开聊天` 进入该历史
Thread，发送固定输入“你好”。`/commands`、两条 `/stream/events` 订阅和 Run 查询均为 HTTP 200；浏览器
无 console error，页面已恢复可发送状态。新 Run 为 `succeeded/active=false`，旧失败 Run 也保持
`failed/active=false`，没有再返回 `thread_active_run_conflict`。刷新同一 URL 后历史同时恢复“你好”和
`workflow response: 你好`。

**状态**：该缺陷为 `chain-complete`。浏览器的完整 reopen/HITL/respond/cancel 与 owner UAT 仍属于任务
5.5/7.4/7.6，保持 `partial`。

### 10.4 Chat 生命周期与 Open SWE 通用借鉴（2026-09-05）

**问题**：SDK 的 `onCompleted({ reason: 'stopped' })` 只说明本地订阅已停止，不说明服务端 Run 已取消。
旧实现将该标签统一显示为“本轮运行已取消”。用户在切换到空白对话后若收到旧 Thread 的迟到回调，正确的
“已切换到空白对话”提示会被错误覆盖。

**借鉴边界**：参考 Open SWE 的
`ui/src/features/agents/lib/AgentThreadStreamProvider.tsx` 与
`ui/src/features/agents/components/composer/ComposerPrimaryActions.tsx`，只采用通用原则：SDK 完成回调刷新
服务端事实；取消由显式 Stop 发起且取消失败不能伪装为 stopped。没有复制其 React、TanStack Query、Sandbox、
GitHub/Slack/Linear、消息入队或 Dashboard API 业务逻辑。

**实施**：

1. `usePlatformChatStream` 仅在 SDK 完成的 Thread 仍是页面当前 Thread 时刷新 snapshot 和反馈；已切换
   到空白/其他 Thread 的旧流完成回调直接忽略。
2. `reason='stopped'` 不再产生“已取消”文案。只有终态轮询已确认服务端终态时，才显示“已完成，页面已同步服务端结果”。
3. 显式 Stop 成功后只显示“已请求停止，正在同步运行状态”，不在服务端终态前宣称取消成功。
4. 终态轮询在用户已经切换 Thread 时停止，不再把旧 Thread 刷新回当前视图。

**验证**：

- `pnpm --dir apps/platform-web test:run`：`37 files / 124 tests passed`，其中新增“切换到空白 Thread 后旧流
  stopped 回调不覆盖提示”的回归测试；
- `pnpm --dir apps/platform-web typecheck`：通过；
- `pnpm --dir apps/platform-web lint`：0 error；现存 83 条无关 warning 未修改；
- Playwright：打开 `workflow_demo` Thread `35a6c710-a906-4ffa-b0b0-9238f76ecafb` 后点击“新对话”，页面
  显示空白对话提示，网络记录无 `/cancel` 请求，console errors=0。

**未覆盖边界**：本项证明新对话和订阅生命周期语义；真实浏览器显式 cancel、HITL respond/retry、跨项目
隔离及 owner UAT 仍按任务 5.5/7.4/7.6 保持 `partial`。

### 10.5 Chat 完成后 Agent 回复投影修复（2026-09-05）

**现象**：新 Thread 的 Run 已返回成功，GraphHarbor state 已包含用户消息和 Agent 回复，但页面只显示用户消息。

**根因**：SDK 本地 stream projection 在双 SSE 订阅竞态结束后可能只保留用户消息。旧 `messages` computed 只要
看到任意 live message 就跳过已刷新的 Platform/GraphHarbor persisted snapshot，导致完整 Agent 回复被遮蔽。

**处理**：Run 完成并刷新当前 Thread snapshot 后，Chat 明确优先使用 persisted messages；新 Run 或切换 Thread
时清除该偏好，避免旧快照污染新会话。该处理只修复前端投影，不修改 GraphHarbor 或 Runtime graph。

**验证**：新增 composable 回归覆盖“live 仅用户消息、刷新快照含 Agent 回复”；Platform Web 全套 Vitest
`37 files / 125 tests passed`，typecheck 通过。真实 `workflow_demo` 新 Thread `9dbfaa3d-7693-4704-8197-5685456f8364`
的 state 已确认包含 `workflow response: 你好`，页面完成提示和历史刷新链正常。

### 10.6 Agent 入口新对话与历史 Thread 语义（2026-09-05）

**现象**：从 `/workspace/assistants` 打开 `workflow_demo` 时，页面会自动读取该 Agent 最近的历史 Thread；用户期望
从 Agent 目录进入时得到空白对话。直接带 `threadId` 的历史 URL 则必须继续恢复该 Thread 的持久化消息。

**根因**：Chat 初始化在没有显式 `threadId` 时，为了方便恢复最近会话，会从 Thread 列表中选择第一个可用 Thread；Agent 目录入口没有表达“新建会话”意图。

**处理**：Agent 列表和 Agent 详情的“打开聊天”入口增加 `startNew=1`。Chat 只在没有 `threadId` 且该标记存在时，以空 active Thread 初始化；Thread 列表仍加载供侧栏查看，但不读取或激活历史 Thread。显式 `threadId` 优先恢复指定历史会话。GraphHarbor、Thread/Run 数据和历史消息不修改。

**代码落点**：`AssistantsPage.vue`、`AssistantDetailPage.vue`、`ChatPage.vue`、`BaseChatTemplate.vue`、
`useChatWorkspace.ts`、`useChatThreadWorkspace.ts`；回归测试位于 `useChatThreadWorkspace.test.ts`。

**验证**：定向 Vitest `5 passed`，`npm --prefix apps/platform-web run typecheck` 通过；Playwright 从
`/workspace/assistants -> Workflow Demo HITL -> 打开聊天` 进入后 URL 为 `startNew=1`，页面显示 `Thread 未创建`，
网络只有线程列表/count 和运行时目录请求，没有旧 Thread 的 state/history 请求，console Errors=0。显式历史 URL
仍显示其已持久化的旧消息，这是预期的历史事实，不会被新 Agent 代码重算。

**状态**：新对话入口语义 `chain-complete`；完整浏览器 send/stream/reopen/HITL/respond/cancel/cross-project
和 owner UAT 仍按 5.5/7.4/7.6 保持 `partial`。

## 11. 最小验证命令

```bash
rtk uv run --frozen python -m unittest discover -s apps/platform-api/tests -p 'test*.py' -q
rtk uv run --frozen pytest apps/runtime-service/tests/runtime apps/runtime-service/tests/middlewares apps/runtime-service/tests/services/reference_agent -q
rtk npm run --prefix apps/platform-web test:run -- --reporter=dot
rtk uv run --frozen python scripts/check_docs.py
rtk openspec validate redesign-platform-runtime-integration --strict --no-interactive
rtk git diff --check
```
