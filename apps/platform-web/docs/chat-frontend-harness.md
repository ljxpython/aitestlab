# Chat 前端文字 Harness

- 文档类型：Current Delivery Harness
- Owning locus：`apps/platform-web`
- 证据深度：`chain-complete`
- 状态：`implemented; textual procedure is the source of truth`

## 1. 目的和边界

这是一张由人或 AI 按步骤执行的验收卡，用来防止以下误判：

- 修改后仍由旧 Worker 执行；
- 复用了旧 Thread，误把历史回复当成当前结果；
- Run 显示完成，但页面没有 Agent 回复；
- 第二轮消息仍处理第一轮内容；
- SSE 断开被错误当成取消；
- 页面、Thread state、history 和 Run 状态互相不一致；
- 模型配置接口返回 `503`，却继续消耗真实模型调用。

本 Harness 不维护第二套聊天状态机，不修改 GraphHarbor，不使用 fake/mock model。GraphHarbor、Runtime 和 Platform API 的日志、API 响应与持久化 state 是证据来源；页面只是其中一个观察面。

## 2. Harness Intake

| 字段       | 结论                                                                                            |
| ---------- | ----------------------------------------------------------------------------------------------- |
| Goal       | 真实浏览器 Chat 完成新 Thread、双轮 send/stream、reopen，并证明页面与服务端事实一致             |
| Locus      | `apps/platform-web`；相邻链路为 Platform API、GraphHarbor API/Worker、Runtime graph             |
| Chain      | Web -> `/api/langgraph` -> GraphHarbor API -> Redis -> Worker -> Runtime -> PostgreSQL          |
| Authority  | `docs/harness/README.md`、Platform Web leaf standards、Runtime contracts、Compatibility Profile |
| Band       | B3 Governed                                                                                     |
| Acceptance | 证据表完整，失败按 `blocked/not-executed` 记录；不能用单测或旧 Run 代替                         |

## 3. 执行前置条件

按顺序检查，任何一项失败都停止，结果记为 `blocked / not-executed`：

1. Platform Web、Platform API、Runtime API、Runtime Worker、PostgreSQL、Redis 均已启动；API 与 Worker 是本次源码修改之后新启动的进程。
2. `scripts/local-stack.sh status` 显示五个受管进程运行，Runtime 和 Platform API readiness 为 `yes`。
3. Platform 模型目录内部接口返回 `2xx`。若日志出现 `runtime.model.initialization_failed`、`model-config 503` 或连接字段不完整，禁止继续发送消息。
4. 使用真实登录浏览器；不把 cookie、token、API key 写入文档或截图。浏览器 console/page error 计入失败。
5. 目标 Agent 来自当前 `langgraph.json`/GraphHarbor catalog。默认使用 `workflow_demo` 验证多轮和可选 HITL；`reference_agent` 只验证普通模型对话。
6. 记录本次批次号、源码版本、API/Worker PID、开始时间和目标项目；不要复用上一次批次的 Thread ID。

## 4. 标准执行步骤

### 4.1 新对话门禁

从 `/workspace/assistants` 进入目标 Agent，或打开带 `startNew=1` 的 Chat URL：

```text
/workspace/chat?targetType=assistant&assistantId=workflow_demo&assistantName=Workflow%20Demo%20HITL&startNew=1
```

通过标准：

- URL 含 `startNew=1`，首次发送前没有 `threadId`；
- 页面显示空白对话/`Thread 未创建`；
- 没有读取某个历史 Thread 的 state/history；
- 输入框和发送按钮可用。

不满足即停止。不能通过手工删除 URL 参数、继续发送或选择历史 Thread“修复”门禁。

### 4.2 第一轮 send/stream

发送带唯一批次标识的消息，例如：

```text
请只原样输出：HARNESS_FIRST_<batch-id>
```

记录：

- 浏览器产生的 `threadId` 和 `runId`；
- `runs/stream` 首次响应状态；
- 页面最新 Agent 消息全文；
- Thread state/history 中最新 human 与 ai 消息；
- Worker 日志中对应 Run 的开始、模型解析和终态。

通过标准：

- `runs/stream` 成功建立并收到终态；
- 页面最新 Agent 回复包含当前 `HARNESS_FIRST_<batch-id>`；
- state、history 和页面都包含同一轮 human/ai 消息；
- Run 为 `success/succeeded/completed`，且没有 `409`、`5xx` 或模型初始化错误。

只看到“Run completed”而没有 Agent 消息，判定失败，不得继续第二轮。

### 4.3 第二轮多轮一致性

在同一个 Thread 发送：

```text
请只原样输出：HARNESS_SECOND_<batch-id>
```

通过标准：

- 第二个 Run 使用同一个 Thread，但产生新的 Run ID；
- 最新 Agent 回复包含 `HARNESS_SECOND_<batch-id>`，不能只返回第一轮标识或第一轮内容；
- `prepare`/Runtime state 的当前消息是第二轮 human 输入；
- 两轮消息顺序在 state、history 和页面一致；
- Thread 没有错误的 active-run 409。

第二轮仍返回第一轮内容，直接归类为 `product failure`，不要重复发送相同输入。

### 4.4 reopen 持久化一致性

保留当前 URL 中的 `threadId`，刷新页面或关闭后重新打开同一 URL。

通过标准：

- 页面恢复同一个 Thread，而不是创建新 Thread；
- 最新 Agent 回复仍包含 `HARNESS_SECOND_<batch-id>`；
- Thread detail、state、history 请求成功；
- 页面展示与 state/history 的最后一条消息一致；
- 无 console/page error。

页面显示完成但刷新后只剩 human 消息，判定 `product failure`，不能记录为通过。

### 4.5 HITL/respond（仅在 Agent 确实暴露中断时执行）

使用能够稳定产生 `workflow_confirmation` interrupt 的 Agent/输入。发送后必须记录：

- Run 状态为 `interrupted` 或等价等待状态；
- 页面显示待确认内容和允许操作；
- Thread state/history 保存 interrupt；
- 未点击确认前，再发新消息得到 active-run 冲突或被页面阻止。

点击批准或拒绝后，记录 `input.respond` 请求、恢复后的 Run ID/终态、最终 state/history 和页面结果。

当前 Agent 没有稳定 HITL 触发条件时，结果只能写 `not-executed`，不能用普通成功对话冒充 HITL 通过。

### 4.6 显式 cancel 与 SSE 断开

仅在有可观察的持续运行时执行：

- 点击“停止生成”前记录 Run 为 active；
- 点击后确认发出显式 cancel 请求，Run 终态为 `cancelled/canceled`；
- 仅关闭浏览器或断开 SSE 时，不应产生 cancel 请求，Run 仍由服务端继续收敛；
- 重新打开 Thread 后，页面显示服务端最终结果或明确 active 状态。

无法制造持续运行时写 `not-executed`，不得用点击停止后看到的 SDK `stopped` 标签推断服务端已取消。

## 5. 证据记录模板

每次只记录一份批次证据，禁止没有新根因就重复执行：

```text
batch=<唯一批次号>
source=<源码版本/工作树时间>
project=<项目 ID，非秘密>
agent=<graph_id>
api_pid=<PID>
worker_pid=<PID>
readiness=<Runtime API/Worker/Platform API/PG/Redis>
model_config_probe=<2xx 或 blocked 原因，不记录 URL/key>
entry_url=<脱敏后的 startNew=1 URL>
thread_id=<Thread ID>
run_ids=<Run ID 列表>
first_turn=<pass/fail + 页面/state/history 摘要>
second_turn=<pass/fail + 页面/state/history 摘要>
reopen=<pass/fail>
hitl=<pass/not-executed/blocked>
cancel=<pass/not-executed/blocked>
browser_console=<0 errors 或错误摘要>
worker_log=<对应 Run 的脱敏终态>
classification=<chain-complete | product failure | environment blocked | not-executed>
first_root_cause=<失败时只写第一处根因>
next_action=<修复根因/补充输入/结束批次>
```

## 6. 停止和结论规则

- readiness、模型配置、登录态或权限失败：`environment blocked / tests not executed`。
- API/Worker 版本或 PID 不确定：`blocked`，先重启并重新登记批次。
- 预检通过后出现消息、state、history 或 Run 断言失败：`product failure`。
- 没有真实 HITL 或持续运行条件：`not-executed`，不能写通过。
- 任何 `409`、`5xx`、`runtime.model.initialization_failed` 或旧回复复现，立即停止；先查第一处根因，禁止继续烧真实模型请求。
- 单测、typecheck、历史 Run、源码浏览和脚本输出只能作为辅助证据，不能替代本 Harness。

## 7. 代码落点与验证状态

| 功能点                       | 代码落点                                                      | 状态                                                  |
| ---------------------------- | ------------------------------------------------------------- | ----------------------------------------------------- |
| 新 Thread 入口               | `ChatPage.vue`、`useChatWorkspace.ts`、Agent 页面路由         | 已实现，需按 4.1 验收                                 |
| SDK live stream              | `usePlatformChatStream.ts`、`platform-chat-stream/actions.ts` | 已实现，需按 4.2 验收                                 |
| persisted state/history 投影 | `useChatThreadWorkspace.ts`、`workspace.service.ts`           | 已实现，需按 4.3/4.4 验收                             |
| HITL/respond                 | `ChatInterruptPanel.vue`、`actions.ts`                        | 服务端合同已有；浏览器条件未满足时保持 `not-executed` |
| explicit cancel              | `usePlatformChatStream.ts`、Runtime Gateway service           | 合同已有；持续运行浏览器证据待执行                    |
| 文字 Harness                 | 本文档                                                        | 已完成                                                |

## 8. 辅助脚本说明

`apps/platform-web/scripts/chat-harness.*` 仅作为可选自动化辅助，不是验收真源。正式结论必须按本文文字步骤填写证据；没有文字证据就没有 `chain-complete`。
