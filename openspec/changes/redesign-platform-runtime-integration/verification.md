# Verification: Platform Runtime Integration Redesign

## Status

- Harness verification schema: `v1`
- Status: `Pending`
- Implementation state: `L1 local-complete; L2 local-complete; L3 partial; external production governance out-of-scope`
- Disposition: `Accepted`
- Pre-apply review: `Approved`
- Owner: 用户
- Decision: owner 已完成 pre-apply review，确认 `GATE-13`，并接受七字段最小模型配置基线；旧统一模型代理最佳实践已废弃。本记录不代表实现或验证完成，业务代码、数据库和物理归档仍须按 tasks/verification 证据推进。

## Agent/Thread inventory decision

- `apps/runtime-service/langgraph.json` 当前正式 graph 为 `reference_agent`。
- 删除前本地 Platform SQLite 只读盘点：`agents=1`、`assistant_profiles=1`、`runtime_runs=125`、`runtime_run_interrupts=2`；未发现旧 Agent 对应的治理 Run 引用。
- owner 已明确确认旧 `graph_id=assistant` 记录和 profile 可以删除；删除后 `agents`/`assistant_profiles` 中对应旧记录均为 0。删除不级联 GraphHarbor Thread/Run。
- 统计事实源和保留策略详见 `apps/runtime-service/docs/knowledge/platform-runtime-integration/11-agent-thread-statistics-retention.md`。
- 当前 Agent 来源为 `apps/runtime-service/langgraph.json` 的 `reference_agent`、`workflow_demo`；Platform `agents` 只表示 project 绑定，不生成 graph。`dev` 已完成两个真实绑定。active/HITL/reconciliation Run 均保留并阻止同 Thread 新建 Run，SSE 断开不取消。

## Scope

- Goal：Platform Web 通过官方 LangGraph SDK，经 Platform API 治理后稳定使用 GraphHarbor。
- Locus：`apps/platform-web`、`apps/platform-api`；GraphHarbor 只接受通用兼容修复。
- Chain：`platform-web -> platform-api /api/langgraph -> GraphHarbor API -> Redis -> Worker -> runtime-service graph -> GraphHarbor PostgreSQL`。
- Band：B3 Governed；涉及公开协议、权限、事实源、数据 migration 和跨仓库兼容。
- Authority：Platform Web leaf standards、Platform API handbook/standards、Runtime public contracts、GraphHarbor Compatibility Profile 和本 change 的 specs。

## Pre-apply Decision Gate

| ID | 决策 | 推荐基线 | 状态 |
| --- | --- | --- | --- |
| `GATE-01` | Context transport | Gateway server-side promotion，不 fork 官方 SDK；扩展只在 Gateway 消费 | `Accepted by owner` |
| `GATE-02` | SDK `assistantId` | `assistantId = agent_key = graph_id`；Gateway 只做 Agent/Project 校验 | `Accepted by owner` |
| `GATE-03` | Thread/Run/Checkpoint/Event truth | GraphHarbor PostgreSQL | `Accepted by owner` |
| `GATE-04` | Platform Run record | 只存 immutable governance 与关联 | `Accepted by owner` |
| `GATE-05` | Gateway endpoint | 只开放正式 Chat 所需 allowlist，不增加 Debug surface | `Accepted by owner` |
| `GATE-06` | upstream Assistant mirror | 不再创建或同步，Platform 不保存独立执行 Assistant | `Accepted by owner` |
| `GATE-07` | Run Explorer change | P1 后按新事实源独立设计 | `Deferred by owner` |
| `GATE-08` | canary change | `Abandoned`，不 sync 直接 archive | `Deferred by owner` |
| `GATE-09` | `ChatDebugPage` | 删除，调试使用 Runtime Web/测试工具 | `Accepted by owner` |
| `GATE-10` | legacy Thread support | 只保留有真实 fixture 的读取兼容 | `Pending inventory` |
| `GATE-11` | model configuration delivery | 七字段连接配置；API key 只写不读，服务端加密 | `Accepted by owner` |
| `GATE-12` | Agent/Thread binding | Project-first；第一次 Run 绑定 `agent_key`，之后不可切换 | `Accepted by owner` |
| `GATE-13` | Run consistency | 统一 launch use case、Run intent/outbox、Idempotency-Key 和 reconciliation | `Accepted by owner` |
| `GATE-14` | Auth profile | delegation 按操作绑定 target/scope/context hash；`get_agent({})` 仅限无副作用构图 | `Accepted by owner` |
| `GATE-15` | Context schema/Tools boundary | 使用现有 Runtime 字段；浏览器不提交 Tools；三态和 hash 规则固定 | `Accepted by owner` |
| `GATE-16` | Model proxy owner | 旧统一模型代理方案 | `Superseded/Rejected` |
| `GATE-17` | Secret Store contract | 旧 Secret Store 编排方案 | `Superseded/Rejected` |
| `GATE-18` | Service identity | 旧 RS256/JWKS/workload identity 方案 | `Superseded/Rejected` |
| `GATE-19` | Execution reference capability | 旧 execution reference/capability probe 方案 | `Superseded/Rejected` |
| `GATE-20` | Local compatibility profile | 显式 `RUNTIME_MODEL_PROFILE=local-compat|production`；生产拒绝 env 直连和隐式降级 | `Local-complete; chain verified` |
| `GATE-21` | Provider smoke | 旧生产 Provider 审批 smoke 方案 | `Superseded/Rejected` |

`GATE-13` 已由 owner 确认。该决策只冻结一致性方案；实现、超时恢复和重复创建证据仍为 `not-executed`。
`GATE-10` 是实施期数据盘点，
只决定是否建立读取 fixture，不允许预先保留无证据 fallback。

Owner decision record (2026-09-04)：上述模型代理最佳实践基线随后被 owner 废弃，原因是当前需求只需
七字段模型连接配置和服务端凭据保护。历史记录保留用于追溯，不再作为实现或验收依据。

Owner decision record (2026-09-04)：`GATE-13` 采用统一 Run launch application use case；所有入口先写不可变
Run intent/outbox，再以 `Idempotency-Key` 和 request digest 调用 GraphHarbor；上游超时进入
`run_start_unknown` 并由 reconciliation 收敛；相同 key/digest 返回同一 Run，不同 digest 返回
`409 IdempotencyConflict`。

Owner decision record (2026-09-04)：L2 不启动 Docker daemon，也不使用 fake model；使用本机 PostgreSQL、
临时本地 Redis 和 Git ignored `apps/runtime-service/.env` 的既有模型配置，显式设置
`RUNTIME_MODEL_PROFILE=local-compat RUNTIME_E2E=1`。本授权只覆盖固定非敏感 prompt 的本机链路 smoke；
不得记录 endpoint、credential 或 token，不证明生产模型代理、Secret Store、`execution_model_id`、RS256/JWKS
或 Provider negative smoke。

## Evidence Plan

### Frontend textual Harness

前端浏览器验收以 `apps/platform-web/docs/chat-frontend-harness.md` 为文字执行卡和证据模板。自动化脚本只能辅助操作，不能替代 `chain-complete` 结论；每批次必须记录新 Thread、双轮唯一标识、页面/state/history/Run 一致性、浏览器错误和首个根因。无登录态、readiness、模型配置 `503` 或无稳定 HITL/持续运行条件时，结果分别记为 `blocked` 或 `not-executed`，不得继续发送真实模型请求。

| Boundary | Planned check | Required result | Current status |
| --- | --- | --- | --- |
| Planning coherence | `openspec validate redesign-platform-runtime-integration --strict --no-interactive` | proposal、specs、design、tasks 一致且合法 | `local-complete` |
| Documentation | `uv run --frozen python scripts/check_docs.py` | 导航、链接和 lifecycle metadata 通过 | `local-complete` |
| Platform Web local | `rtk npm run --prefix apps/platform-web test:run`; `typecheck`; `build`; `lint` | 38 files/123 tests、typecheck/build 通过；lint 无 error（既有 warnings） | `local-complete` |
| Platform API local | `cd apps/platform-api && rtk uv run --frozen python -m unittest discover -s tests -p 'test*.py' -q` | 145 tests OK（skipped=3）；migration、HTTP、permission、audit 和 denial 回归通过 | `local-complete` |
| Model management boundary | Platform API 模型录入、基础 URL/protocol 校验、Secret 脱敏和 Runtime resolver contract | 模型配置可安全保存和读取状态；Runtime 动态解析仍待链路验证 | `partial` |
| Model proxy owner/Secret Store | 旧生产治理方案 | 不再执行 | `Superseded/Rejected` |
| Service identity | 旧 RS256/JWKS、`kid` overlap、GraphHarbor audience、Worker `model-proxy` workload identity | 不再执行；未来生产治理另立 change | `Superseded/Rejected` |
| Local runtime configuration | ignored `.env` + validator + full-chain smoke | 服务启动不再依赖 `RUNTIME_MODEL_PROFILE`/`RUNTIME_E2E`；本机模型配置和 production deny rules 通过 | `local-complete` |
| GraphHarbor Profile | `scripts/local_stack_l2_runtime_smoke.py --restart-check` + workflow_demo HITL smoke | API/Worker/PostgreSQL/Redis、Thread create/search/count/get、State/History、Protocol v2 run.start/input.respond、SSE cursor、cancel、独立 API/Worker restart 通过；事件去重和浏览器链仍待 | `partial` |
| Shortest chain | `rtk uv run --project apps/platform-api --frozen python scripts/local_stack_l2_runtime_smoke.py --restart-check` | Run 创建、执行、Protocol v2/标准 Runs stream、负面场景和重启后读取/stream 通过 | `local-complete` |
| Identity/Thread binding | L2 smoke 的 active/cross-project/idempotency cases | active conflict=409、跨 project=404、digest conflict=409；换 Agent/并发专门 fixture 待补 | `partial` |
| Context/Tools boundary | Gateway contract tests + disabled model smoke | v2 promotion、unknown/legacy 字段清理、disabled model=403 和三态局部合同通过；完整矩阵待补 | `partial` |
| Run consistency | durable coordinator tests + `--restart-check` | marker/reconciliation、幂等冲突、API/Worker restart 后 Run 恢复通过；独立 outbox/定时扫描待补 | `partial` |
| SSE/cancel contract | Platform API join-stream 与 SDK adapter 单测 | 断开参数固定为 `false`；显式 `true` 在 upstream 前拒绝；显式 cancel 仍走 cancel endpoint | `local-complete` |
| Auth profile | 现有 delegation 的过期/错 target/scope/hash、`get_agent({})` 边界 | 本地执行 fail closed；生产 RS256/JWKS 另立 change | `partial` |
| Provider smoke | 旧生产审批 smoke 方案 | 不再执行 | `Superseded/Rejected` |
| Browser E2E | Playwright 本机登录、项目切换、Chat、Agent、Graphs、Runtime Models 页面检查 | 页面加载、`dev` 项目两个 Agent、Graphs 目录和 console errors=0 已通过；409 错误归一化和 Thread 刷新有单测；完整 send/stream/reopen/HITL/respond/cancel/cross-project 流程仍待补 | `partial` |
| Human | owner UAT | 页面、交互、对象模型与功能获明确接受 | `not-executed` |

mock、fake、skip 或旧 `langgraph dev` 只能证明其实际层级，不得记录为 GraphHarbor 真实链通过。

## Current Results

- 2026-09-05：完成历史资料处置台账。`platform-runtime-graphharbor-canary-routing` 标记为
  `Abandoned`（不 sync，待 archive）；`runtime-run-event-contract-and-run-explorer` 标记为
  `Deferred`（不作为当前门槛）；`add-react-agent-web` 保持 `Rejected`（未来 archive without sync）。
  当前 change 的 D01-D12 与 owner 决策记录一致，`Proposed` 项不进入 apply contract。任务 1.4/1.5
  达到 `local-complete`。

- 2026-09-05：新增 `scripts/local-stack.sh restart-one <service>`，只操作脚本创建的受管 PID，支持五个应用进程单独重启；修复端口参数引用后，`runtime-api` 与 `runtime-worker` 均可独立重启并恢复 readiness。
- 2026-09-05：建立 Compatibility Profile `apps/runtime-service/docs/knowledge/platform-runtime-integration/09-compatibility-profile.md`，锁定 Platform Web SDK、Protocol、Platform API、GraphHarbor 与 Runtime package 版本，并记录当前 Gateway allowlist；任务 `1.2` local-complete。版本升级仍需按 Profile 命令重跑验证。
- 2026-09-05：新增无秘密 characterization fixture `apps/platform-api/tests/fixtures/runtime_integration_characterization.json` 及 `test_runtime_integration_characterization.py`，固定正式 Chat 的 thread/run/event 请求、Idempotency-Key、Gateway allowlist 与历史 Thread read-only 兼容边界；任务 `1.3` local-complete。
- 2026-09-05：收紧 Platform API Protocol v2 运行 Context：只允许 `model_id`、`temperature`、`max_tokens`、`top_p`、`tools`；`system_prompt`、`enable_tools`、`multimodal_parser_model_id` 和未知 Context 字段在 upstream 前 fail closed；新增数值范围和合同回归。验证：`uv run --frozen python -m unittest tests.test_runtime_delegation tests.test_runtime_gateway_runtime_contract tests.test_graph_parameter_schema_provider -q`，`27 tests OK`。
- 2026-09-05：`RUNTIME_MODEL_PROFILE=local-compat RUNTIME_E2E=1 rtk uv run --project apps/platform-api --frozen python scripts/local_stack_l2_runtime_smoke.py --restart-check` 通过。Protocol v2/标准 Runs、SSE cursor、显式 cancel、active/idempotency/cross-project/disabled-model negative cases 均通过；API 与 Worker 分别重启后同一 Thread/Run 仍可读取，恢复 stream 有 cursor；`since=1` 重连返回更高 cursor 且不重复最后游标。随后使用真实 `workflow_demo` 完成 `interrupted -> input.respond -> success`，同 Thread active 冲突返回 409；完整浏览器 Chat E2E 仍未覆盖。
- 2026-09-05：Platform API 全量 `unittest discover` 145 tests OK（skipped=3）；Platform Web typecheck、38 files/123 tests、build 通过，lint 无 error；`check_docs.py`、OpenSpec strict validate 和 `git diff --check` 通过。
- 2026-09-05：Gateway HTTP surface 收敛为 Chat allowlist：移除 global Runs、Run wait/delete、thread copy 和 checkpoint-specific mutation 等未治理公开入口，保留正式 Chat 所需 thread/state/history/run/protocol/cancel 路由；新增路由 allowlist 回归测试。保留 thread delete/state update，因为当前 Chat/branch 工作流仍实际调用它们。
- 2026-09-05：补充 GraphHarbor 真实集成负面用例 `test_graphharbor_invalid_delegation_has_no_persistence`，使用签名 scope 不匹配 delegation 验证 Thread 创建在认证边界即被拒绝，随后以有效凭据确认该 Thread 不存在；本机运行 `3 passed, 1 deselected`（真实模型用例按约定未执行）。Context hash 和 token 结构的 fail-closed 由 Runtime Auth/Middleware 单测覆盖，但 GraphHarbor Run 持久化前的 hash 负面矩阵尚未证明，因此任务 2.4 保持 partial。
- 2026-09-05：删除 Platform Web `ChatDebugPage`、legacy debug service/spec 和 `buildLegacyDebugRunContext`；Chat workspace 不再加载或暴露 Runtime Tools 管理入口，Agent 创建页也移除工具选择，仅保留模型选择。Platform Web typecheck 与 37 files/119 tests 通过。
- 2026-09-05：Runtime target ownership 优先按 `(project_id, graph_id)` 查询，历史 `langgraph_assistant_id` 仅作读取兼容；新 durable Run 仍以 `agent_key = graph_id` 绑定。owner 确认旧 `graph_id=assistant` 无需保留后，旧 Agent/profile 已删除；旧 Python 兼容模块和历史列仍待独立 migration 清理。
- 2026-09-05：补齐 Runtime Gateway 的 Agent profile Context 白名单与优先级合同；显式 Run context > Agent defaults > Project default model，`system_prompt`、身份字段和未知 profile 字段不会进入 Runtime。验证：`uv run --frozen python -m unittest tests.test_runtime_gateway_runtime_contract -q`，`15 tests OK`。
- 2026-09-05：修复 `input.respond` 误触发模型默认值查询和 durable coordinator 非 UUID 测试回归；默认值注入仅限 `run.start`，策略版本查询对已绕过 project fixture 的单测保持兼容。验证：`uv run --frozen python -m unittest tests.test_runtime_gateway_runtime_contract tests.test_durable_run_coordinator -q`，`28 tests OK`；全量 Platform API `151 tests OK (skipped=3)`。
- 2026-09-05：公开 Agent 目录增加 `/api/projects/{project_id}/agents` 与 `/api/agents/{id}` 同实现入口，Platform Web service 已切换到 Agent 路径；旧 Assistant 路径保留为迁移兼容，新 Agent CRUD 不再触发 upstream Assistant mutation。
- 2026-09-05：Platform Web Chat 的官方 SDK `useStream` 继续作为消息、tools、interrupt、loading、error 和生命周期写入 owner；Thread list/detail 使用独立 workspace controller，并以 token 防止快速切换旧响应串写。`usePlatformChatStream` 7 tests、`useChatThreadWorkspace` 4 tests 与全量 Web 119 tests 通过，任务 5.3/5.4 local-complete。
- 2026-09-05：移除 Runtime Tools 管理页路由及 Runtime/Models/Operations 可见导航，保留内部 tools catalog API；Platform Web typecheck 与 37 files/119 tests 通过。任务 5.6 的 legacy payload/文件物理清理仍待 characterization 和 owner gate。
- 2026-09-05：模型凭据新增坏密文、错误 master key 的 fail-closed 合同测试；模型列表/详情仍只返回 `credential_configured`，API key 不出响应。验证：`uv run --frozen python -m unittest tests.test_runtime_catalog_delegation -q`。

- 2026-09-05：补充 L2 smoke 的 Thread search/count/get 检查，真实本机链返回 search=200、count=200、get=200，且按本次 harness marker 精确命中 1 个 Thread；标准 Runs 快照继续确认 `context`、`durability`、`stream_resumable`、`multitask_strategy` 与 `stream_mode` 均保留。2.1/2.3 达到 local-complete。
- 2026-09-05：在本轮契约收敛后再次运行 `RUNTIME_MODEL_PROFILE=local-compat RUNTIME_E2E=1 uv run --project apps/platform-api --frozen python scripts/local_stack_l2_runtime_smoke.py`；真实链再次通过，协议 Run/标准 Runs、SSE、显式 cancel、active/idempotency/cross-project/disabled-model 负面场景均符合预期。
- 2026-09-05：完成产品命名边界收敛：新 Agent CRUD 只接受 `graph_id`，创建/编辑 payload 不再接受独立 `assistant_id`；SDK 上游需要的 `assistant_id` 仍由 Gateway 以 `agent_key` 填充，旧 URL/响应字段只保留读取兼容。新增 `CreateAssistantCommand` extra-forbid 回归，Platform API 30 项定向测试、Platform Web 37 files/119 tests 与 typecheck 通过。任务 5.7 local-complete。
- 2026-09-05：更新 Platform API architecture、project handbook、runtime gateway interface、permission/audit standards，明确 Agent 公开命名、七字段模型配置、无 upstream Assistant mutation 和兼容字段处置；`check_docs.py` 与 OpenSpec strict validate 通过。任务 8.1 local-complete。
- 2026-09-05：使用本机 `langgraph.r6.json` 临时启用确定性 `workflow_demo`，真实执行 `requires_confirmation=true` 的 Run，观察 `interrupted`，经 Platform Gateway `input.respond` 成功恢复并以 `success` 结束。期间修复 GraphHarbor 当前 `/state` 顶层 `interrupts` 形状未被网关识别的问题，并增加回归测试；任务 2.2 local-complete。配置已恢复为生产默认 graph 配置。
- 2026-09-05：Compatibility Profile 复核未发现需要修改 GraphHarbor 通用协议层的缺口；`input.respond` 已存在且由 GraphHarbor 自身协议实现，未为 Platform 私有字段扩展 handler。任务 2.6 以“无需 patch”完成，真实服务端 HITL 已通过。
- 2026-09-05：operation-scoped delegation 的 `read`/`run-create` 签发与 Runtime Auth fail-closed 合同通过：Platform API delegation 定向 13 tests、Runtime Auth 13 tests。任务 3.5 local-complete；生产 RS256/JWKS 仍属废弃方案。
- 2026-09-05：RuntimeConfigMiddleware 在 graph/model/tool 执行入口强制 delegation `scope.operation=run-create`；只读 delegation、Context hash 不匹配和 scope 不匹配均在 handler 前拒绝，回归命令 `uv run --project apps/runtime-service --frozen python -m pytest apps/runtime-service/tests/middlewares/test_runtime_middleware.py -q`，结果 `10 passed`。随后在本机真实 GraphHarbor 运行 `test_agent_server_auth.py -m integration -k 'not real_model'`，结果 `3 passed, 1 deselected`；匿名、无效 token、scope 不匹配均在 Thread 持久化前拒绝。GraphHarbor Run 持久化前 hash 拒绝仍未证明，任务 2.4 保持 partial。
- 2026-09-05：Playwright 本机浏览器冒烟通过：登录、Overview、项目切换到 `dev`、Chat、Agent、Graphs、Runtime Models 和新增模型表单均可加载；`dev` 页面显示 `reference_agent`、`workflow_demo` 两个 Agent，`playwright-cli console` 报告 Errors=0、Warnings=0。
- 2026-09-05：服务端真实 `workflow_demo` HITL 通过；浏览器页面级验收已通过，但浏览器 send/stream/reopen/interrupt/respond/cancel/cross-project 全链尚未逐项执行，不能把页面冒烟写成完整 E2E。

## 2026-09-05 方案收敛：模型目录与前端信息架构简化

本轮 owner 已确认以下规划，代码已按最小七字段和 Agent-first 方案实施；真实页面录入后 Run 与完整浏览器
交互仍保留对应门禁：

| 需求 | 目标行为 | 当前证据 | 状态 |
| --- | --- | --- | --- |
| 移除 `RUNTIME_MODEL_PROFILE` | 服务启动不依赖 profile；模型由 Platform Catalog 管理 | validator、示例配置和启动文档已移除 profile 门禁 | `local-complete` |
| 移除 `RUNTIME_E2E` | 五个服务默认形成完整链路；Provider smoke 用测试目录/marker 选择 | 测试门禁已移除，Runtime 定向 8 passed | `local-complete` |
| 模型配置进入 Runtime | 页面录入的 URL/protocol/model/key 真实驱动执行 | opaque reference + Platform 内部解密端点已实现；真实页面录入后 Run 待验证 | `in-progress` |
| Agent/Graph 收敛 | 用户只操作 Agent，Graph 保留内部 catalog | Models 一级入口，Graph/Runtime/Policy 普通导航隐藏，兼容路由保留 | `local-complete` |
| Policy 页面收敛 | 后端 deny-first 保留，控制项合并进 Models/Agents | Models 提供项目默认模型操作，策略入口隐藏 | `local-complete` |

详细方案、代码落点、验证命令和迁移顺序见：
`apps/runtime-service/docs/knowledge/platform-runtime-integration/12-simplified-model-and-ui-plan.md`。
9.3 的真实页面录入后 Run、5.5/7.4 的完整浏览器交互和 7.6 owner UAT 仍未完成，不能将总体 change
写成 `chain-complete`。
- 2026-09-05：owner 删除确认已执行：删除前旧 `graph_id=assistant` 对应 Agent/profile 各 1 条，未发现对应 `runtime_runs`；删除后复查对应 Agent/profile 为 0，`dev` 项目保留 `reference_agent`、`workflow_demo` 两个真实绑定。
- 2026-09-05：真实 GraphHarbor hash mismatch 复核：delegation 的错误 `context_hash` 会先拿到 GraphHarbor `run_id`，随后 Run 被持久化并由 Worker/Runtime 置为 error；因此不能声称“hash mismatch 在 GraphHarbor Run 持久化前拒绝”。Thread 创建阶段的匿名、无效 token、scope mismatch 仍在认证边界前置拒绝。任务 2.4 保持 `partial`；若产品必须零 Run 记录，应由 Platform API 在提交前完成 hash 校验，需另立明确契约，不修改 GraphHarbor 业务层。

- 2026-09-04：最小模型配置实现：复用 `runtime_catalog`，新增七字段 DTO、`POST /api/runtime/models`、
  `PATCH /api/runtime/models/{model_id}`、`enabled` 状态、`credential_configured` 脱敏返回和 forward-only
  migration `20260904_0004_add_runtime_model_connection_config.py`。API key 使用已安装的 `cryptography`
  Fernet 以 `PLATFORM_API_MODEL_CONFIG_MASTER_KEY` 加密；master key 缺失、无效或解密失败均 fail closed。
  定向回归通过（16 passed），覆盖密文 round-trip、坏 URL/协议拒绝、读取不含 `api_key`、SQLite repository
  创建/更新/禁用。动态 Runtime 读取保存配置、HTTP 权限测试、日志审计断言和浏览器页面仍为 `in-progress`。
- 2026-09-04：受影响 Platform Gateway/SDK/Run consistency/模型配置回归通过（49 passed）；OpenSpec strict
  validate、`scripts/check_docs.py` 和 `git diff --check` 均通过。仅有现有 Starlette/httpx deprecation warning。

- 2026-09-03：`openspec validate redesign-platform-runtime-integration --strict --no-interactive`
  通过，change valid。
- 2026-09-03：`uv run --frozen python scripts/check_docs.py` 通过，输出
  `Documentation checks passed.`。
- 2026-09-04：owner 完成 pre-apply review，并确认 `GATE-13`；P1 正在实施，Run consistency 已有局部代码和单测证据，完整真实链证据仍未完成。
- 2026-09-04：owner 先接受过模型代理最佳实践基线，随后明确将其整体废弃；相关输入不再收集，最小七字段方案成为现行基线。
- 2026-09-04：owner 将模型录入收敛为 URL、API key、model、protocol 等最小连接信息，并要求凭据存储后不泄漏；已新增 [DeepSeek Harness 模型录入借鉴与最小方案](../../../apps/runtime-service/docs/knowledge/platform-runtime-integration/08-deepseek-harness-model-entry-reference.md)，该方向已替换旧生产治理 contract 并同步到 OpenSpec。
- 2026-09-04：旧 capability probe 曾用于验证复杂代理假设；该脚本随旧方案一并删除，不再作为当前证据。
- 2026-09-04：P0 profile 校验：`validate_runtime_config.py` 保留显式 `RUNTIME_MODEL_PROFILE=local-compat|production`；定向校验测试通过（3 tests），不再要求废弃的 proxy/JWKS 输入。
- 2026-09-04：运行根目录 `bash scripts/local-stack.sh doctor`，当前 Git ignored Runtime `.env` 因缺少显式 `RUNTIME_MODEL_PROFILE` 被拒绝（`CONFIG_ERROR`）；这证明启动门禁生效，但不能替代 local-compat shortest chain。
- 2026-09-04：以进程级临时覆盖 `RUNTIME_MODEL_PROFILE=local-compat` 重跑根目录 `bash scripts/local-stack.sh doctor` 通过；未修改 `.env`。随后执行 `bash scripts/local-stack.sh migrate`，GraphHarbor 升级到 `006_terminal_events`。首次 `start` 在 Runtime API readiness 失败，日志确认原因为本机 Redis `127.0.0.1:6379` 未运行，而非 Provider/模型初始化失败；脚本已清理所启动的 Runtime API/Worker。后续已启动本机依赖并形成 L2 链证据。
- 2026-09-04：owner 明确授权 L2 使用 Git ignored `.env` 的真实模型，固定 `RUNTIME_MODEL_PROFILE=local-compat RUNTIME_E2E=1`，且明确不启动 Docker daemon。该授权只覆盖 local-compat 链路；生产 Provider smoke 不属于当前 change。
- 2026-09-04：Platform API SSE/cancel 合同修复：`RuntimeGatewayService.join_thread_run_stream` 拒绝
  `cancel_on_disconnect=true`，并在所有 join-stream 请求中显式传递 `false`；SDK adapter 同步拒绝绕过
  Service 的 `true`。使用 `uv run --frozen python -m unittest tests.test_runtime_gateway_runtime_contract
  tests.test_runtime_gateway_sdk_adapters tests.test_durable_run_coordinator tests.test_runtime_delegation`
  验证，`Ran 39 tests ... OK`。未覆盖 GraphHarbor 真实 SSE 重连、浏览器 E2E 和进程重启。
- 2026-09-04：Run consistency 局部实施：`runtime.durable_run` 已注册
`RuntimeDurableRunReconciliationExecutor`。`run.start` 上游 timeout 会将 durable run 置为
`run_start_unknown`，并在标准 metadata 写入 `platform_idempotency_key`；executor 仅调用
`list_thread_runs` 按 marker 查找远端 Run，找到后关联 `run_id`，不重放原始 input 或重复 create，
未命中时沿用 operation 的 `_retry_policy.max_attempts=3`，耗尽后将 operation 与 durable run 标记 failed。
Redis queue 模式下 unknown operation 会通过现有 dispatcher 重新入队，DB polling 模式沿用 submitted 认领。
验证命令：
`uv run --frozen python -m unittest tests.test_durable_run_coordinator tests.test_runtime_gateway_runtime_contract tests.test_operations_queue_backend tests.test_operations_streaming_and_retry`
（`Ran 28 tests ... OK`）。该实现复用 `operations` 表作为 outbox-like intent/consumer，尚未建立独立
outbox 表，也未覆盖 API/Worker 重启、定时扫描、GraphHarbor 真实部署和生产一致性，因此 GATE-13 仍为
`partial`，不能宣称 formal-complete。
- 2026-09-04：GraphHarbor 边界复核：其定位为通用 LangGraph-compatible Agent Server，不承载 Platform
  Project、Agent、Policy、模型目录、Secret 或治理记录。曾尝试在 GraphHarbor Protocol v2 handler 透传
  `durability`、`stream_resumable`、`on_disconnect`，确认这些是 Platform normalization/标准 Runs 或
  stream 选项，不能直接扩展已锁定的 v2 `run.start` 契约；该 patch 与对应断言已精确撤回。后续 Context
  由 Gateway server-side promotion 转为标准 Runs API 字段，GraphHarbor 仅在 Compatibility Profile
  证明通用缺口时接受最小兼容修复。
- 2026-09-04：Platform Gateway 完成 Protocol v2 `run.start` 的 server-side promotion：消费
  `config.configurable.platform_runtime`，调用已有标准 Runs create，将模型/生成选项放入顶层
  `context`，仅向 GraphHarbor 发送标准 Agent Server 字段；`input.respond` 和其他协议命令仍走
  `/commands`。使用 `uv run --frozen python -m unittest tests.test_runtime_gateway_runtime_contract
  tests.test_runtime_gateway_sdk_adapters tests.test_durable_run_coordinator tests.test_runtime_delegation`
  验证，`Ran 39 tests ... OK`。该证据只覆盖 Platform API 本地合同，不代表完整 L2、GraphHarbor
  重启恢复或浏览器 E2E 已完成。
- 2026-09-04：重跑 `uv run --project apps/platform-api --frozen python scripts/local_stack_l2_runtime_smoke.py`
  通过。结果：Protocol v2 run/snapshot/event stream HTTP 200，`stream_resumable_persisted=true`，事件
  流存在 cursor；标准 Runs stream HTTP 200 且存在 cursor；显式 cancel HTTP 200，终态为 GraphHarbor
  语义的 `interrupted`。该 smoke 未覆盖 `input.respond`、API/Worker 重启恢复、事件去重和浏览器 E2E，L2
  后续 `--restart-check` 已补上 API/Worker 重启恢复证据，L2 已达到 `local-complete`。
- 当前 L1 模型配置、权限和本地合同闭环已 `local-complete`；GATE-13 采用现有 operations 表的 outbox-like intent，独立 outbox 与定时扫描不属于本轮；L2 本地最短链已 `local-complete`；L3 已完成服务端真实 HITL、部分安全/重启证据，仍缺事件去重、完整浏览器交互和人工 UAT。真实 staging/production
旧生产代理不再属于本 change，不构成阻塞。
- 2026-09-05：修复 Chat active Run 409 的前端错误展示和状态恢复。根因是 SDK 对 Platform 嵌套
  `{error: {code, message}}` envelope 做字符串插值，产生 `[object Object]`；同 Thread active Run 返回 409
  的保护语义保持不变。SDK fetch 兼容扁平化错误响应，统一归一化支持嵌套 code/message，submit/respond/retry/edit
  在 409 后刷新 Thread snapshot 并恢复 persisted HITL。Platform Web 定向 client、workspace service、Chat
  actions、stream tests 共 24 tests passed，typecheck/eslint 通过。

## P0 Delivery Record（旧模型代理方案已废弃）

2026-09-04 owner 决策：统一模型代理、`execution_model_id`/revision、Secret Store 编排、RS256/JWKS、
workload identity、capability probe 和 Provider 审批 smoke 全部 `Superseded/Rejected`，不再作为本 change
的任务或完成门禁。仅保留历史结果用于追溯；当前模型闭环按七字段、write-only、服务端加密重新验证。

| Task | Evidence | Result | Status |
| --- | --- | --- | --- |
| 0.1-0.3 owner/Secret Store/identity | 旧模型代理门禁 | 不再执行 | `Superseded/Rejected` |
| 0.5 profile | `uv run --frozen pytest tests/runtime -q`；`tests/runtime/test_runtime_config_validation.py`；`scripts/local-stack.sh doctor` | local/production profile 规则有合同测试；owner 已选择真实 `.env` local-compat shortest chain，Redis 前置检查待通过后继续 | `partial` |
| 0.6 provider smoke | 旧生产审批 smoke 方案 | 不再执行 | `Superseded/Rejected` |
| 0.7 evidence record | 本表、命令结果、未覆盖边界和 blockers | P0 证据已登记；真实生产代理仍受门禁，owner 已授权的 local-compat smoke 可继续 | `local-complete` |

SSE/cancel 本地合同证据属于任务 4.5/5.5 的组成部分；OpenSpec 中这两个任务还包含错误映射、浏览器
交互和完整链路验收，因而不能仅凭本次 39 个测试勾选为完成。

### P0 Inputs（旧方案已废弃）

旧代理方案所需的 owner/endpoint/Secret Store/JWKS/Provider 授权输入不再收集，也不阻塞当前实现；未来
若重新提出生产治理需求，必须另立 change。

## Deferred Boundaries

- Langfuse/OTLP exporter 故障矩阵。
- 生产灰度、性能 SLO 和运行中自动回滚。
- Sandbox 与远程 MCP；它们由 Runtime/DeepAgent 能力负责，不属于 GraphHarbor 或本 P1 的完成门槛。
- Provider、生产数据库和真实租户数据只有在 owner 明确授权后使用。

## Docs / Runbook Impact

- 新专项位于 `apps/runtime-service/docs/knowledge/platform-runtime-integration/`，只承担讨论导航和实施覆盖面。
- 本 change 的 proposal/specs/design/tasks/verification 是 P1 规划与证据真源。
- `22`、`27` 和旧 Chat 计划先解除权威；owner 批准矩阵且替代内容落入 current standards 后再物理归档。
- `28-runtime-refactor-development-plan.md` 只保留 P1 阶段入口与完成门槛。
- P0 本地脚本：`apps/runtime-service/scripts/validate_runtime_config.py`；组合服务检查使用根目录
  `scripts/local-stack.sh doctor`。

## Residual Risk

- Protocol v2 当前没有顶层 `context`；`GATE-01` 已接受 promotion，但实现和 Profile 证据仍未完成。
- 模型管理七字段闭环已实现基础 CRUD/加密/脱敏并通过定向回归；HTTP 权限、动态 Runtime 读取和完整链路仍待验证。旧统一模型代理、版本执行引用和生产 Provider smoke 不属于本 change。
- Agent/Thread、Context/Tools、生产 Auth profile 和 Run consistency 规则已经接受，但实现与真实链证据未完成；仍不得把批准状态当作 `complete`。
- 旧 Assistant 三 ID、Gateway 多 Run 入口和历史 Thread 数据仍需 characterization，不能盲删或保留无证据 fallback。
- GraphHarbor 路径名称相似不等于 SDK 兼容，必须由锁定版本的 Profile 证明。
## 2026-09-05 简化方案实施证据

- `RUNTIME_MODEL_PROFILE` 已不再参与 Runtime 配置校验；`.env.example` 和服务 README 删除启动门禁说明。
- `RUNTIME_E2E` 不再控制测试执行；Provider smoke 使用 `tests/e2e` marker。验证：
  `uv run --project apps/runtime-service --frozen python -m pytest apps/runtime-service/tests/runtime/test_modeling.py apps/runtime-service/tests/runtime/test_runtime_config_validation.py -q`，`8 passed`。
- Platform 模型目录到 Runtime 的最小闭环代码已实现：Gateway 生成短期 HMAC opaque reference，GraphHarbor 仅转发 `_runtime_model_ref`，Runtime 通过 `PLATFORM_RUNTIME_MODEL_CONFIG_URL` 调用 Platform 内部端点获取解密连接。API key 不进入公开响应、durable snapshot 或日志。验证：
  `PYTHONPATH=apps/platform-api uv run --project apps/platform-api --frozen python -m unittest tests.test_runtime_catalog_delegation tests.test_runtime_gateway_runtime_contract tests.test_runtime_model_reference -q`，`29 tests OK`。
- Platform Web 新增 `/workspace/models` 一级入口，隐藏 Graph/Runtime/Policy 普通导航并保留兼容路由；`npm run typecheck` 通过，Vitest `37 files / 119 tests passed`。
- Models 已加载项目模型策略并提供设为/取消项目默认操作；后端 deny-first 策略保持不变，旧 Policy 路由仅作兼容。
- 未完成：本机真实“页面录入模型后 Run”尚未执行；浏览器真实 send/stream/reopen/HITL/respond/cancel/cross-project 与 owner UAT 仍保持 partial。

## 2026-09-05 Browser SSE Reconciliation Evidence

- Root cause: a completed GraphHarbor Run could leave the browser SDK loading after its initial dual-SSE subscription race. The Platform stream now normalizes lifecycle labels and converges the durable ledger from terminal frames.
- Browser proof: project-scoped `workflow_demo` send created Thread `0a8a5048-7cbe-4839-88fc-d8499effd443`; its only Run reported `success`, and the event endpoint replayed root lifecycle `seq=1 running`, `seq=32 completed/success`.
- The Chat client reconciles only a server-confirmed terminal Run with `stop({ cancel: false })` and refreshes history. It neither cancels a Run nor treats timeout/disconnect as terminal. Reopen and a second same-Thread send were exercised without `thread_active_run_conflict`.
- Verification: Platform API `unittest tests/test_runtime_gateway_runtime_contract.py tests/test_runtime_gateway_event_redaction.py` (`21 OK`); Platform Web `pnpm -C apps/platform-web typecheck` passed; `git diff --check` passed.
- Remaining: browser HITL/respond, explicit cancel, complete stream rendering and owner UAT remain `partial`; tasks 5.5 and 7.4 stay unchecked.

## 2026-09-05 Historical Active Run Reconciliation Evidence

- Root cause: an old Platform `runtime_runs` projection could remain `running/active_key=1` after its GraphHarbor Run had reached a terminal state, because no terminal SSE frame or `GET Run` had reached the Gateway. A new Run was then correctly blocked by the stale projection but incorrectly unavailable to the user.
- Fix: the shared `LaunchRuntimeRun` path checks a different-key active record against GraphHarbor before reserving a new Run. It marks the projection terminal only for an authoritative terminal snapshot. `running`, `interrupted`, `run_start_unknown`, upstream-read failure, and cancel-requested remain active; no timeout release or implicit cancel was introduced.
- Exact local report: the reported `workflow_demo` Thread had an upstream Run status of `error` while its Platform record was `running/active=true`. The standard Gateway Run read reconciled that record to `failed/active=false` without deleting data or dispatching a new Run.
- Verification: `rtk .venv/bin/python -m unittest tests/test_durable_run_coordinator.py` (`17 tests OK`); `rtk .venv/bin/python -m unittest tests/test_runtime_gateway_runtime_contract.py` (`19 tests OK`); `rtk git diff --check` passed.
- Browser proof: followed `dev -> /workspace/assistants -> Workflow Demo HITL -> 打开聊天` to the reported historical Thread and sent the fixed input `你好`. The command, both event subscriptions, and Run reads returned HTTP 200; the browser had no console errors, the new Run reached `succeeded/active=false`, and the old failed Run remained `failed/active=false`. Reloading the same URL restored both the user message and `workflow response: 你好`. No `thread_active_run_conflict` occurred.
- Remaining: this proves the durable-ledger boundary and the reported browser send path. It does not complete browser HITL/respond/cancel UAT; tasks 5.5, 7.4, and 7.6 remain unchecked.

## 2026-09-05 Chat Lifecycle Semantics Evidence

- Root cause: `@langchain/vue` reports `onCompleted({reason: "stopped"})` for a stopped local stream subscription. That label alone is not proof that the server Run was cancelled. The previous UI treated every such callback as a cancellation, including an old Thread callback received after the user had switched to a blank conversation.
- Borrowed boundary from Open SWE only: its stream provider refreshes the Thread cache on completion without assigning cancellation semantics, and its explicit Stop path requests server cancellation before disconnecting. No Open SWE React, Sandbox, OAuth, queued-message, GitHub/Slack/Linear, or Dashboard API behavior was copied.
- Fix: `usePlatformChatStream` now ignores completions whose SDK Thread is no longer the active page Thread; it does not label a generic `stopped` callback as cancelled. Explicit Stop now says only that cancellation was requested while the authoritative Thread/Run snapshot converges. Terminal reconciliation also stops when the user has switched away, so it cannot restore an old Thread into a blank conversation.
- Regression evidence: `pnpm --dir apps/platform-web test:run` completed `37 files / 124 tests`; the new composable test covers a stale `stopped` completion after switching to a blank Thread. `pnpm --dir apps/platform-web typecheck` passed. `pnpm --dir apps/platform-web lint` completed with 0 errors and 83 pre-existing warnings outside this fix.
- Browser evidence: authenticated Playwright opened Thread `35a6c710-a906-4ffa-b0b0-9238f76ecafb`, clicked “新对话”, received the expected blank-conversation message, removed `threadId` from the route, recorded no `/cancel` request, and reported console errors=0.
- Scope: this makes the reported new-conversation lifecycle `chain-complete`; it does not complete browser explicit cancel, HITL respond/retry, cross-project, responsive/accessibility, or owner UAT. Tasks 5.5, 7.4, and 7.6 remain unchecked.

## 2026-09-05 Chat Persisted Message Projection Evidence

- Root cause: a completed real `workflow_demo` Run had both the human input and `workflow response: 你好` in the GraphHarbor Thread state, but the SDK's local stream projection retained only the human message. The previous computed view treated any non-empty live projection as authoritative and hid the refreshed persisted assistant message.
- Fix: after a current-Thread completion callback has refreshed the authoritative Thread snapshot, the Chat view prefers persisted messages. Creating a new Run or changing Thread clears that preference. GraphHarbor and Runtime behavior were not changed.
- Regression evidence: a composable test covers live human-only projection plus persisted human/assistant snapshot; Platform Web suite completed `37 files / 125 tests`, and typecheck passed.
- Browser evidence: the real blank-thread send created `9dbfaa3d-7693-4704-8197-5685456f8364`; authenticated state read returned `workflow response: 你好`, Run completion was reported, and the page refresh path is now wired to show the persisted assistant response.

## 2026-09-05 Workflow Demo Multi-turn Message Evidence

- `workflow_demo` is now a real model-backed `create_agent` composed under the existing Workflow StateGraph.
  `reference_agent` remains the general model Agent; `workflow_demo` adds conditional routing and optional
  explicit HITL confirmation around the model call.
- Root cause: `prepare()` preferred the persisted non-empty `state["message"]` over the current invocation's
  accumulated `messages`. After the first turn saved `你好`, every later turn reused that value even when a new
  user message had been appended to the same Thread.
- Fix: `prepare()` now scans `messages` from newest to oldest, selects the latest non-empty user/human message,
  and only falls back to the saved message when no new user message exists (for HITL resume).
- The normal `respond` node invokes the model subgraph with the current accumulated messages. Model construction
  uses the existing Runtime Context, policy, model catalog opaque reference, provider connection and timeout
  middleware; no fake model is used on the production path.
- Code: `apps/runtime-service/src/runtime_service/services/demo/workflow_demo/agent.py` and `workflow.py`; regression
  `test_workflow_demo_uses_latest_user_message_in_same_thread` in
  `apps/runtime-service/tests/services/workflow_demo/test_agent.py`.
- Verification: Workflow Demo tests `7 passed`; Runtime full suite `200 passed, 21 skipped`; local real Provider
  two-turn smoke passed with different model responses and the second user message persisted as the active turn.
- Nested graph auth propagation was verified separately: the outer Workflow validates the delegation before
  constructing the model Agent, and the inner model graph reuses that trusted binding without requiring a second
  GraphHarbor `server_info` object. Authenticated local smoke returned the injected model response.
- Follow-up verification after the model-backed change: Runtime full suite remained `200 passed, 21 skipped`;
  docs check, OpenSpec strict validation, and `git diff --check` passed. `ruff` was not available as an executable
  in the locked Runtime environment, so no ruff result is claimed.

## 2026-09-05 Agent Entry New-Conversation Evidence

- Root cause: Chat initialization selected the newest available Thread whenever an Agent entry omitted `threadId`.
  The Agent directory therefore reopened history instead of expressing a blank conversation.
- Fix: `/workspace/assistants` and Agent detail “打开聊天” links now include `startNew=1`. Chat keeps the Thread
  list available for manual selection but leaves the active Thread empty when this flag is present. Explicit
  `threadId` links retain historical Thread restoration; no GraphHarbor Thread/Run data is rewritten.
- Regression evidence: `npm --prefix apps/platform-web run test:run -- src/modules/chat/composables/useChatThreadWorkspace.test.ts`
  (`5 passed`); `npm --prefix apps/platform-web run typecheck` passed.
- Browser evidence: authenticated Playwright followed `dev -> /workspace/assistants -> Workflow Demo HITL -> 打开聊天`.
  The resulting URL contained `startNew=1`, the page showed `Thread 未创建`, console errors were zero, and requests
  included Thread search/count but no historical Thread state/history request. Opening the explicit historical URL
  still restored its persisted old messages, as required.
- Scope: this closes the reported Agent-entry/new-conversation behavior at `chain-complete`; full browser
  send/stream/reopen/HITL/respond/cancel/cross-project and owner UAT remain partial, so tasks 5.5, 7.4, and 7.6 stay unchecked.
