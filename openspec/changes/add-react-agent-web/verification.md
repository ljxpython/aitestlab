# Verification

## Status

Rejected - owner UAT rejected the Agent Web product implementation (2026-08-26)

## Disposition

Do not release, trial, replace `apps/platform-web`, or continue product implementation. The owner rejected
the visual design and functional alignment as completely unacceptable. Local transport/model evidence remains
technical evidence only and does not constitute product acceptance.

## Pre-apply Review

Approved - Phase 0 isolated PoC accepted; Phase 1-3 implementation only (2026-08-26)

本 change 是 B3 governed change。owner 已评审 proposal、specs、design、tasks 和本文档，确认隔离
PoC 的真实 E2E 证据已验收，并批准 Phase 1-3 的 gateway/runtime 合约、React 产品工作台和 Durable
Run transport 实现。该授权不包含共享环境依赖升级、staging/生产切流或 legacy `runs.stream` 退役；
三者均须以新的真实环境证据获得单独批准。

## Planned Evidence

| 层级 | 命令/检查 | 输入 | 预期结果 |
| --- | --- | --- | --- |
| platform-api local | focused pytest/contract tests | authorized/unauthorized Protocol v2 command/get/events/cancel/respond | project scope、幂等与拒绝语义正确 |
| runtime-service local | runtime harness | v2 StreamPart、v3 PoC、durability、checkpoint、worker restart、interrupt | v2 稳定；v3 不越过内部边界；恢复或确定失败 |
| agent-web local | typecheck、lint、unit/component/browser tests | fixture、event 重放、断线、viewport | UI 不串写、不重复、可访问 |
| real E2E PoC | 已部署 `agent-web -> platform-api -> runtime-service -> Agent Server -> 隔离 PostgreSQL/Redis` | 真实 delegation credential、Bearer fetch SSE、真实 graph 的创建、重连、取消、interrupt 恢复 | snapshot 为事实源，SSE 可恢复；无 mock upstream/内存替身 |
| staging/grey E2E | feature flag + 项目白名单的真实部署链 | 真实用户路径、稳定性、恢复率、取消率、权限审计和回退演练 | 可扩大灰度或确定回退 |
| formal/human | owner UAT | 三栏工作台和受控发布环境 | 产品和治理接受 |

## Approved PoC Scope And Exit Criteria

1. 使用隔离 PostgreSQL 数据库、Redis namespace、固定 Agent Server 镜像 digest 与可回收测试数据。
2. 记录并验证 CLI、SDK、Python 锁文件、镜像 digest 的兼容组合，全部 graph、custom routes 和
   `platform_auth` 必须成功启动。
3. `run.start` success result 必须返回 `run_id`；相同 HTTP `Idempotency-Key` 不得创建第二个 Run，
   同 key 不同摘要必须返回冲突。
4. 每个 thread 仅允许一个 active Run；事件必须可关联该 Run；多个 interrupt 必须按 interrupt ID
   精确 `input.respond`。
5. POST SSE 的 `since` 必须先重放更高 `seq` 再转实时；断线不改变 Run 状态。
6. checkpoint、worker restart、Run/operation 映射和审计生命周期通过；token、Authorization header
   与完整输入消息不得进入审计、operation payload 或诊断日志。
7. 在真实部署的完整 E2E 链路上，以隔离 project、数据库、Redis namespace 和真实 delegation
   credential 验证上述行为。mock upstream、in-memory runtime、单模块集成测试只能作辅助证据，
   不得替代 PoC 通过条件。

任何 PoC 硬退出项的后续复验失败都阻止继续进入 staging/生产；本次 Phase 1-3 批准不自动授权共享
环境依赖升级、生产切流或 legacy 退役。

## Current Evidence

- 已完成：只读分析 DeepSeek Harness、Open SWE、现有 platform gateway、runtime-web 边界和
  Durable Run 学习文档。
- 已完成：确认 Durable Run 为执行模型、Protocol v2 为正式远程协议；Bearer SSE 采用
  `fetch + ReadableStream` 与 POST `since` 主动重连。
- 已完成：核对 LangGraph 官方文档、当前 `langgraph==1.2.11`/SDK 与 `langgraph-api:3.13`
  镜像基线；v2 是本地消费者收敛目标，v3 仍只作内部 PoC。
- 已完成：owner 审核并批准 Phase 0 隔离 PoC，确认 HTTP `Idempotency-Key`、单 active Run、
  interrupt ID 恢复、Run/operation 一对一映射和标准 Protocol v2 event 语义。
- 已完成：owner 已验收隔离 PoC 的真实 E2E 证据，并于 2026-08-26 批准实施 Phase 1-3。该证据的
  原始命令、输入、环境标识和输出尚未回填本仓库；它在本记录中仅作为 owner 验收事实，不能替代
  Phase 4 的 staging/灰度可重放证据。
- 已完成：盘点 `apps/platform-web` 的 45 个页面级入口及其复用 chat 基座；确认 Agent Web 首期
  对齐的是通用 Chat、SQL Agent、Testcase Agent 和 Testcase Agent V2 的执行型工作流，而非一次性
  替换平台控制面。未迁移域已记录为旧端所有权，不作为删除或空壳替换依据。
- 已完成：按用户指定资料与当前官方 Agent Server 文档复核技术裁决。生产协议固定为 Protocol v2
  command 与 POST SSE `since`；Open SWE 的 Durable Run/Coordinator/checkpoint 语义被吸收，
  但其 REST URL、GET EventSource/`Last-Event-ID` 与请求体幂等键不作为本项目协议。
- 已完成：创建 `apps/agent-web` 目录、Draft 支持文档与 OpenSpec planning artifacts。
- 已完成：`apps/platform-api` 的 Durable Run Coordinator。`run.start` 必须携带 HTTP
  `Idempotency-Key`；gateway 以 `(project_id, thread_id, idempotency_key)`、规范化请求摘要和数据库
  active-key 唯一约束维护重试、冲突和单 active Run。该 header 不会进入 Protocol payload。
- 已完成：每个受控 Run 创建一个 `runtime.durable_run` operation；成功取得 `run_id` 后进入 running，
  Run snapshot 返回终态时再收敛 operation 与释放 active-key。operation payload 只保存 thread 与 target，
  不保存完整输入、Bearer token 或 Authorization header。
- 已完成：新增 Alembic revision `20260826_0002_add_durable_runtime_runs`，但没有对任何共享或生产
  数据库执行 migration。
- 已完成：`apps/agent-web` 的 React 静态工作台、desktop/mobile 浏览器检查和 `RunEventsController`。
  transport 使用 Bearer header、POST body `since`、thread-scoped `seq` 去重、退避重连、cancel 与
  `input.respond`，没有 legacy `runs.stream` fallback。活跃 Run 由 Query hydrate 并以 Run snapshot
  确认终态；SSE 只触发 timeline 投影与 snapshot refresh。
- 已完成：Agent Web 使用旧端相同的 `pw:auth:token-set`、`pw:workspace:project-id` 存储边界；有
  project context 时通过 TanStack Query 读取/创建 thread，发送 `run.start`，并在 lifecycle 后以
  snapshot 确认终态。无 project context 时保留 fixture，仅供本地设计检查。
- 已完成：gateway cancel 在 upstream 接受请求后只记录 operation `cancel_requested_at` 和
  `runtime.run.cancel_requested` 审计；thread active key 必须等待 Run snapshot 返回 `cancelled` 或
  `interrupted` 才释放。
- 已完成：gateway SSE 将标准 Protocol v2 channel、`seq` 与 replay 顺序原样传递，但对 event payload
  中的 token、Authorization、cookie、password、secret 等明确敏感字段做递归脱敏；非法 channel 在调用
  upstream 前被拒绝。该脱敏不以 SSE 关闭改变 Run 状态。
- 已完成：Agent Web 以 target preset 过滤 thread，空 target 必须先创建对应 thread；草稿按
  `project + target + thread` 隔离，Run/query/state 由 TanStack Query hydrate，SSE 只做稳定 key 的
  timeline 投影并使 snapshot refresh。mobile 默认不覆盖主会话，Inspector 由用户显式打开。
- 已完成：Agent Web 复用既有 gateway 的 thread history 与 checkpoint state，历史选择只切换只读
  snapshot 投影，不重发 Run，并提供返回当前快照的明确操作；Inspector 的任务与文件来自 `state.values`，
  不再使用固定 mock。附件复用旧端已经采用的 JPEG/PNG/GIF/WEBP/PDF message content block，支持文件选择
  与粘贴，选择后才在 `run.start` 输入中发送；历史只投影附件名而不暴露 base64。当前文件可通过现有
  `POST /threads/{thread_id}/state` 更新，历史 checkpoint、运行中和待审批状态均只读。独立二进制 artifact
  store 仍不在本轮范围。
- 已完成：生产 Agent Web 无 project context 时通过 AppBootGate 阻止伪造会话；仅以
  `VITE_AGENT_WEB_FIXTURE=true` 显式开启的设计 fixture 可绕过该门禁，且 README 已标明它不是
  E2E 证据。工作台侧栏新增跳转到既有 control plane 的项目、Assistant/Graph、Knowledge、Runtime、
  Operations、Audit、账号和平台治理入口；链接复用旧 `platform-web` 路由及其鉴权/权限守卫，不复制或
  空壳迁入管理功能。
- 已完成：四个 Agent target 统一为受控 graph 预设。新建 thread 写入旧端同构的
  `target_type=graph`、`assistant_id`、`graph_id` 与显示 metadata；恢复时优先使用 thread 的
  `graph_id`。gateway contract test 确认一个 `test_case_agent` thread 不能提交 `sql_agent` Run，
  防止 target/thread 串写，且没有新增第二套聊天页面。
- 已完成：历史消息仅在其首次出现 checkpoint 及 parent checkpoint 都可从服务端 history 识别时暴露
  Retry/Edit。Retry 使用无新输入的 Protocol v2 `run.start` 加 `config.configurable.checkpoint_id`；
  Edit 将用户文本带回 composer，由用户确认后从 parent checkpoint 创建新分支。没有复制 Vue 的
  `forkFrom` 或 legacy stream 状态机。
- 已完成：本地 `test_case` 三个 debug/live harness 的 `astream` 消费已收敛为
  `version="v2"` 的 `StreamPart(type/ns/data)`；没有改变远程 HTTP event protocol。
- 已完成：最小无外部模型的 local graph harness 实测 v2 `StreamPart` 与 v3 的 awaitable
  `AsyncGraphRunStream` 投影，后者输出有序 `seq/method/params` event。v3 会产生官方 beta warning，
  因此仅用作内部验证，不对浏览器 HTTP contract 发布。
- 已完成：runtime 文档入口与流协议对照已显式以 `09-langgraph-runtime-upgrade-and-event-migration.md`
  为版本、Durable Run 与 Protocol v2 的权威来源。历史 `langgraph-api==0.11.1`/`0.7.58` 表述不再作为
  当前基线，Agent Web 不再被建议使用 `runs.stream` fallback。
- 已完成：新增 `apps/agent-web/scripts/real-durable-run-e2e.mjs`。该 transport harness 只调用正式
  `run.start`、POST SSE `since`、Run snapshot 与显式受保护的 cancel/`input.respond`；它要求隔离环境、
  固定 Agent Server digest、隔离 PostgreSQL/Redis 标识和真实 delegation credential 标识，默认拒绝执行。
  它验证同一 HTTP `Idempotency-Key` 重试返回同一 `run_id`，并拒绝将无事件或无严格递增 replay 误报为
  E2E 通过。单 active Run 冲突在创建后立即验证；HITL 可从受控 thread state 读取服务端声明的 interrupt
  ID 后再提交 `input.respond`。尚未在真实隔离链路运行。
- 已完成：冻结 Durable Run DTO、上游 snapshot 到 operation 的状态映射和最小可归一化错误码。持久记录
  只保存请求摘要，不保存完整输入；本阶段不自动删除 Run、幂等、operation 或审计记录。任何 retention/
  归档/删除策略均留待独立 B3 变更与批准。
- 已完成：Protocol v2 `run.start` 默认注入并校验 `durability="sync"`、`stream_resumable=true`、
  `on_disconnect="continue"`；React command builder、真实 E2E harness 和 gateway 转发保持同一 envelope，
  非法枚举/类型在到达 upstream 前拒绝。
- 已完成：gateway 在每次 `input.respond` 前从受控 thread state 同步活动 interrupt 的 ID 到
  `runtime_run_interrupts`，并以 `(project, thread, run, interrupt)` 精确索引恢复目标。成功提交后仅标记
  该 interrupt 已解决，Run 终态才关闭该 Run 的剩余 interrupt；不保存 interrupt payload、token 或完整输入。
  新增 Alembic revision `20260826_0003_add_runtime_run_interrupts`，未对共享或生产数据库执行 migration。

### Executed Local Checks (2026-08-26)

| Command | Result | Coverage |
| --- | --- | --- |
| `uv run python -m unittest tests/test_runtime_gateway_event_redaction.py tests/test_runtime_gateway_runtime_contract.py tests/test_durable_run_coordinator.py tests/test_runtime_delegation.py -q` | pass, 30 tests | command/query/订阅/取消/恢复；Durable 参数默认值和非法值拒绝；终态状态别名映射；受控 event channel、SSE 敏感字段脱敏、Idempotency-Key 重试/冲突、单 active Run、缺失 run_id 保守锁定、actor 无项目角色前置拒绝、精确 interrupt ID 映射与重复恢复拒绝、完整 Run 审计生命周期与输入脱敏、cancel request 不提前释放、snapshot 终态释放、thread graph target 隔离 |
| `uv run python -m compileall -q app` | pass | platform-api changed modules import/compile |
| `uv run python -m compileall -q tests/services_test_case_service_debug.py tests/services_test_case_service_v2_debug.py tests/services_test_case_service_skills.py` | pass | 三个本地 v2 StreamPart consumer 可编译，旧 v1 tuple consumer 无代码命中 |
| `uv run pytest tests/test_langgraph_stream_contract.py tests/harness/test_runtime_context_contract.py tests/harness/test_runtime_contract_tightening.py -q` | pass, 16 tests | 无模型/无外部存储的 v2 StreamPart、v3 awaitable internal event projection、可信 RuntimeContext/RuntimeOptions 字段边界和运行时静态契约；v3 beta warning 已接受且不外露 HTTP |
| `uv run python -m compileall -q runtime_service` | pass | runtime-service 当前源码与更新后的 harness/documentation 影响路径可编译 |
| `uv run python -c "from importlib.metadata import version; ..."` | pass: `langgraph 1.2.11`、`langgraph-sdk 0.4.3` | 当前隔离开发依赖基线；不代表共享环境升级验收 |
| `npm run test` | pass, 28 tests | controller header isolation、SSE replay dedupe/`since` 恢复、断线重连、确定的 HTTP 订阅错误不无限重试、thread 序号隔离、Run-scoped cancel、server interrupt ID resume、thread/run URL path 编码、状态任务/文件及 checkpoint 历史投影、消息 parent checkpoint、Retry command（含 Durable 参数）、终态状态别名与 active Run 选择、受控 target metadata、JPEG/PNG/GIF/WEBP/PDF 附件白名单、历史附件名投影不暴露 base64、稳定消息/tool timeline 投影、共享登录态与项目 header 隔离、并发 refresh 单飞、未登录请求阻断、control-plane URL 拼接 |
| `npm run typecheck` / `npm run build` | pass | agent-web TypeScript 与 Vite production build |
| `node --check scripts/real-durable-run-e2e.mjs`；无环境变量直接执行 | pass；默认拒绝且未发出网络请求 | 真实 E2E harness 语法与隔离环境防护；严格递增 `seq`、事件 Run 关联、可选单 active/idempotency 冲突断言；不构成真实 E2E 证据 |
| Playwright on local Vite fixture | pass, console errors 0 | 1280px 三栏布局、键盘 `Ctrl+Enter` 发送与取消、Inspector 关闭/重开；390px 主会话、显式 Inspector sheet 且无控件重叠 |
| Playwright on local Vite fixture | pass, console errors 0 | 1024px/768px responsive rail：项目与新建对话为有名称的可访问图标按钮，标题栏可切换 target，Inspector 默认收起且不遮挡会话操作 |
| Playwright on local Vite without fixture | pass, console errors 0 | 无 `project_id`/`pw:workspace:project-id` 时只显示 AppBootGate 与项目入口，不显示伪造会话 |

### Revalidation (2026-08-26)

| Command | Result | Boundary |
| --- | --- | --- |
| `cd apps/platform-api && uv run python -m unittest discover -s tests -q` | pass | 当前 gateway、Durable Run coordinator、迁移与既有平台测试共同通过；测试过程有现存测试密钥长度与资源清理 warning，未掩盖失败。 |
| `cd apps/runtime-service && uv run pytest runtime_service/tests/test_langgraph_stream_contract.py runtime_service/tests/harness/test_runtime_context_contract.py runtime_service/tests/harness/test_runtime_contract_tightening.py -q` | pass, 16 tests | 本地 v2 consumer、可信 runtime contract 与仅内部使用的 v3 投影保持可用；v3 experimental warning 已明确保留在内部边界。 |
| `cd apps/agent-web && npm run test && npm run typecheck && npm run build` | pass, 28 tests | React Durable Run transport、SSE replay、附件与工作台投影通过，且可构建 production bundle。 |
| `cd apps/agent-web && node --check scripts/real-durable-run-e2e.mjs && node scripts/real-durable-run-e2e.mjs` | syntax pass; guarded refusal | 未配置 `E2E_ISOLATED=1` 时脚本拒绝发起请求；这证明防误用门禁，不构成真实 E2E。 |
| Playwright fixture at 1440/1024/768/390 | pass, console errors 0 | 三栏、compact rail 与移动主会话均无横向溢出；390px 冷启动不展示 Inspector，显式打开后可关闭；`Ctrl+Enter` 提交后进入运行中并阻止并发输入。本地人工检查不替代 owner UAT。 |
| local real-model integration: `agent-web -> platform-api SQLite copy -> runtime-service in-memory -> assistant -> configured DeepSeek model` | pass | `run.start` 返回 `run_id`，相同 `Idempotency-Key` 重试返回同一 Run，153 个 Protocol v2 SSE event 的 `seq` 严格递增至 161，snapshot 为 `success`。Playwright 实际 React 工作台也显示模型文本、工具生命周期、服务端 HITL 审阅与完成后的可提交状态；无浏览器 console error。该环境不含 PostgreSQL/Redis，因此仅为真实模型本地集成验证，绝不作为 Durable Run E2E。 |
| local real-model integration: `agent-web -> platform-api isolated local PostgreSQL -> runtime-service in-memory -> assistant -> configured model` | pass | PostgreSQL 专用库 `agent_web_local_e2e` 经本地 bootstrap 初始化并标记为 `20260826_0003`。真实 `assistant` graph 两次 `run.start` 均返回 `run_id`，相同 `Idempotency-Key` 返回同一 Run；SSE `seq` 分别严格递增至 51（47 个事件）和 52（48 个事件），两次 snapshot 均为 `success`。PostgreSQL 查询证明 Run 的 `runtime_runs` 与 `operations` 关联存在且状态为 `succeeded`。runtime 仍为 `langgraph dev` in-memory，因此不构成 Durable Run PostgreSQL/Redis E2E。 |

`alembic upgrade head --sql` was intentionally not accepted as migration evidence: the pre-existing
`20260723_0001` revision calls `inspect(op.get_bind())`, which Alembic offline mode supplies as a
MockConnection, so it fails before the new revision. Isolated SQLite `create_core_tables()` did create
`runtime_runs` 与 `runtime_run_interrupts`；real migration application remains a later isolated-environment gate.

## Uncovered Boundaries and Risks

- token refresh 已通过共享 refresh promise 做并发单飞，并有 local test；SSE parser 已在
  `RunEventsController` 中实现并有 local tests，真实协议帧仍须 E2E 验证。
- 尚未执行本轮变更的可重放真实 E2E；owner 已验收的历史隔离 PoC 也尚未回填原始命令、输入与输出。
  本地 mock-upstream 测试不构成 Protocol v2、checkpoint、interrupt、replay/durability 或审计的真实链路证据。
  `real-durable-run-e2e.mjs` 已提供可复现的执行入口，但在真实隔离环境写入其脱敏报告前，任务
  1.4-1.7、3.1-3.3、5.5 仍不得勾选。
- 当前开发主机的 Docker daemon 不可连接，且尚未提供隔离 `E2E_PLATFORM_API_URL`、Bearer credential、
  project/thread/assistant、固定 Agent Server digest、PostgreSQL/Redis 标识和 delegation credential ID；
  因此不能在本机创建可信替代环境，也不能执行真实 E2E harness。
- gateway 已持久化 active interrupt-to-run ID 映射，但它仍须由真实多 interrupt、worker restart 与重复
  completion webhook E2E 验证。cancel 已记录请求但仍依赖 snapshot polling/event refresh 收敛，不具备
  webhook-driven reconciliation。
- 尚未确定 legacy `runs.stream` 的退役、回退和外部兼容窗口。
- Run/idempotency/operation 表已定义，但 retention、后台 reconciliation 与 production migration 仍待确定。
- 运行选项、thread 删除、target preset、interrupt 按钮、附件 content block、附件粘贴、只读
  history/checkpoint、当前 thread 文件编辑与任务/文件投影均有本地实现，但尚未用真实 delegation credential
  和真实 Agent Server 的实际 graph 完成端到端验收；独立附件二进制 artifact store 与真实历史分支行为仍待验收。
- 空 PostgreSQL 库直接执行 `alembic upgrade head` 会在 revision `20260723_0001` 读取不存在的
  `users` 表时失败。当前本地验证使用 `python -m scripts.init_db` 初始化隔离库后 `alembic stamp head`，
  这验证 PostgreSQL 控制面链路，但不证明正式的空库 Alembic bootstrap；必须以独立 migration 修复处理。
- 尚未对每个旧聊天行为完成新 contract 的真实 E2E 对齐；独立附件二进制持久化、历史分支的
  retry/edit 语义以及当前 thread state 文件编辑的授权/持久化行为必须逐项验证。Retry/Edit 的本地
  checkpoint command shape 已覆盖，但仍须确认实际 Agent Server 对无 input retry 的行为。
- 本地浏览器检查只覆盖 fixture 与无项目门禁，不代表授权后的真实 Agent Server、checkpoint、SSE 或
  control-plane 权限路径 E2E。
- Run snapshot 现在以 1.5 秒轮询作为终态兜底，并在终态刷新 state/history；轮询频率、终态别名和真实
  Agent Server 状态字段仍须由隔离 E2E 校准。

## Docs and Runbook Impact

- 已新增 `docs/agent-web-redesign/` 作为 Draft supporting material。
- 已更新 Agent Web README，记录启动方式、`VITE_PLATFORM_API_URL`、`VITE_PLATFORM_WEB_URL`、受限 fixture
  以及隔离真实 E2E harness 的环境门禁和报告回填要求。
- Agent Web 已补齐空 target thread 的首条消息自动创建、线程状态筛选和终态 snapshot 轮询；这些路径
  只有本地 contract/build 证据，不能替代真实 delegation credential 的验收。
- 本轮补齐的终态 snapshot 轮询、空 thread 自动创建、thread 状态筛选、path segment 编码、未登录请求
  阻断和 E2E harness 冲突断言已通过本地测试/语法检查；它们仍不构成真实隔离链路证据。
- platform-api runtime gateway supporting evidence 与 runtime-service runbook/harness 的真实 E2E 更新仍待后续
  隔离环境证据；不修改 current standard。
