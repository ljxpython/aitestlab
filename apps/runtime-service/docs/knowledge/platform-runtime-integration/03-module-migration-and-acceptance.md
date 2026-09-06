# P1 模块迁移与验收 Harness

- 文档类型：Draft Supporting Delivery Design
- 状态：L1 部分实现；L2 链路进行中
- 任务真源：[`tasks.md`](../../../../../openspec/changes/redesign-platform-runtime-integration/tasks.md)
- 证据真源：[`verification.md`](../../../../../openspec/changes/redesign-platform-runtime-integration/verification.md)

> 方案更新（2026-09-04）：模型管理以本文新版本为准：七字段最小配置、API key write-only、服务端加密、
> 查询脱敏。旧的 revision、execution reference、Secret Store/JWKS 和生产模型代理要求已被当前最小方案
> 取代，统一标记为 `Superseded/Rejected`，不作为当前本地阶段的完成门槛。

本文只提供阶段导航和验收覆盖面。实施勾选只更新 OpenSpec `tasks.md`，命令、输入、结果和未覆盖
边界只更新 `verification.md`，避免三份清单互相打架。

说明：下方 `P1.0-P1.6` 是 OpenSpec 的工作流分解；当前对外报告和实施门禁统一使用
`L1/L2/L3`，其中 `L1` 即当前 P0 的模型配置基础闭环。

## 1. 阶段总览

```text
P1.0 决策与退役清单冻结
  -> P1.1 SDK / GraphHarbor Compatibility Profile
  -> P1.2 Platform domain、Context、delegation、migration
  -> P1.3 Gateway allowlist 与统一 Run governance
  -> P1.4 Platform Web SDK 工作台改造
  -> P1.5 最短真实链 + owner UAT
  -> P1.6 删除 legacy、更新 Current docs、sync/archive
```

| 阶段 | 可观察出口 | 当前状态 | 是否实现 |
| --- | --- | --- | --- |
| P1.0 | owner 批准 architecture、Context transport、ID、事实源、archive matrix | `pre-apply-approved` | ❌ |
| P1.1 | 锁定版本的 Profile 覆盖 v2、Runs、SSE、Context、denial | `not-started` | ❌ |
| P1.2 | Agent 单一执行键、模型配置、不可变 Context/Run ledger、按操作 token | `partial` | 部分 |
| P1.3 | 所有 Run create 入口统一，Gateway surface 收缩 | `not-started` | ❌ |
| P1.4 | 正式 Chat 只以 SDK live state 为事实，旧 payload/重复状态退出 | `not-started` | ❌ |
| P1.5 | 浏览器到 GraphHarbor Worker/Runtime 的真实 success/denial/restart 链 | `not-started` | ❌ |
| P1.6 | 无用代码删除、Current docs 更新、旧资料归档、spec sync/archive | `not-started` | ❌ |

P1.0 的 owner review 已完成；版本锁定、characterization fixture 和处置清单等准备任务仍未完成，不能把本阶段或后续实现标记为 complete。

## 2. P1.0 决策门

开始 apply 前必须一次性确认：

| ID | 问题 | 推荐 | 状态 |
| --- | --- | --- | --- |
| `GATE-01` | Context transport | Gateway server-side promotion，不 fork 官方 SDK；扩展只在 Gateway 消费 | Accepted by owner |
| `GATE-02` | SDK assistantId | `assistantId = agent_key = graph_id`；Gateway 只做 Agent/Project 校验 | Accepted by owner |
| `GATE-03` | Thread/Run truth | GraphHarbor PostgreSQL | Accepted by owner |
| `GATE-04` | Platform Run record | 只存 immutable governance/关联，不存执行 payload | Accepted by owner |
| `GATE-05` | Gateway endpoint | 只开放正式 Chat 所需 allowlist，不增加 Debug surface | Accepted by owner |
| `GATE-06` | upstream Assistant mirror | 不再创建或同步，Platform 不保存独立执行 Assistant | Accepted by owner |
| `GATE-07` | Run Explorer active change | P1 后按新事实源独立设计 | Deferred by owner |
| `GATE-08` | canary change | Abandoned archive without sync | Deferred by owner |
| `GATE-09` | `ChatDebugPage` | 删除，调试使用 Runtime Web/测试工具 | Accepted by owner |
| `GATE-10` | legacy Thread support | 只保留有真实 fixture 的读取兼容 | Pending inventory |
| `GATE-11` | model configuration delivery | Platform 保存七字段连接配置，API key 只写不读，服务端加密；Runtime 使用服务端配置 | Accepted by owner |

Run consistency 决策已由 owner 确认；`verification.md` 的 `Pre-apply review` 已为 `Approved`，但实现和证据仍未执行。
`GATE-10` 是实施期数据盘点，不是保留 legacy fallback 的理由。

## 3. P1.1 Compatibility Profile

| ID | 必须证明 | 最小证据 | 是否实现 |
| --- | --- | --- | --- |
| `COMP-01` | SDK 真实路径为 `/state`、`/commands`、`/stream/events` | 浏览器/transport request capture | ❌ |
| `COMP-02` | Thread create/get/search/state/history | 真实 GraphHarbor PostgreSQL | ❌ |
| `COMP-03` | v2 run.start envelope 与 run_id | SDK -> Gateway -> GraphHarbor | ❌ |
| `COMP-04` | messages/values/tools/lifecycle/input/checkpoint channels | 可重放 SSE 断言 | ❌ |
| `COMP-05` | interrupt respond 与 cancel | 真实 interrupted Run | ❌ |
| `COMP-06` | reconnect/since/duplicate handling | 断线后继续且不重复应用 | ❌ |
| `COMP-07` | Runs API Context、durability、stream options | Worker/Runtime 观察到非默认值 | ❌ |
| `COMP-08` | missing/invalid/mismatched delegation fail closed | upstream 未调度 Run | ❌ |
| `COMP-09` | API restart 与 Worker restart 后恢复 | 同 Thread/Run/Checkpoint | ❌ |

Profile 必须记录 SDK、protocol、GraphHarbor、runtime-service package 的确切版本。缺环境只能标记
`blocked/not-executed`，不能用 mock、skip 或旧 `langgraph dev` 代替。

## 4. P1.2 Platform API domain 与 migration

### Agents

- Platform 产品只保存 `agent_key`、project ownership、展示字段和 policy/default 引用；
- `agent_key` 与 Runtime catalog 的 `graph_id` 使用同一个稳定值；
- 停止 upstream Assistant create/update/delete；
- 对旧 `langgraph_assistant_id` 和 Platform Assistant UUID 做数据审计、迁移和最终删除；
- disabled/missing/cross-project/stale graph 均在 upstream 前拒绝。

### Runtime Catalog / Policy

- Catalog 是已部署能力 snapshot，不是 Runtime truth 替身；
- Policy 有不可变 revision，明确 graph/model/tool allowlist 和默认值；
- per-run model preference 只能在允许范围内选择或收缩；
- 浏览器不提交 Tools；Runtime 内部仍测试 `tools` 的缺失、空列表和非空列表三态。

### Model Registry

- 管理员可录入、编辑、启停模型；连接验证接口暂不属于当前最小闭环；
- Platform PostgreSQL 保存七字段配置，`api_key` 使用服务端密文且只写不回显；
- `base_url` 和 `protocol` 在服务端做基础校验；更严格的网络出口/SSRF 策略另列安全变更；
- Platform 保存 `provider`、`display_name`、`base_url`、`protocol`、`model`、加密后的 `api_key` 和
  `enabled`；API key 只写不读，列表和详情只返回 `credential_configured`。
- Runtime 请求模型时由服务端读取已保存配置；API key 不进入浏览器、Thread、Run、Context、GraphHarbor、
  日志或审计详情。当前不引入 execution reference、revision 或独立模型代理。

### Governance Run record

最小目标字段：

```text
project_id / tenant_id
agent_key / graph_id
thread_id / run_id
actor_id
policy_revision
context_snapshot / context_hash
idempotency_key / request_digest
operation_id / audit correlation
status projection
created_at / updated_at
```

它不保存完整 message、tool input/output、checkpoint 或 Provider secret。

### Delegation

- token 只在 Context 决议后签发；
- Run create 绑定 graph/thread/hash，read token 只给 read scope；
- denial 测试必须断言没有 upstream side effect；
- token/header/context/message 不进入 audit detail 或普通日志。

## 5. P1.3 Gateway 改造

| 表面 | 改造目标 | 是否实现 |
| --- | --- | --- |
| Presentation | 显式 allowlist、标准 envelope/SSE、只做解析 | ❌ |
| Thread scope | Auth/persistent scope 为主，metadata 只二次校验 | ❌ |
| Run launch | Protocol v2 和后续 trigger 共用一个 use case；不保留 Chat Debug 页面 | ❌ |
| Context | 按已接受的 `GATE-01`，upstream 只收标准 Context；实现与真实链仍待完成 | ❌ |
| Delegation | 每个 upstream operation 最小 scope token | ❌ |
| Error | 401/403/404/409/422/502 等稳定映射且不泄密 | ❌ |
| SSE | 建连前授权、断开取消 subscription、日志脱敏 | ❌ |
| Idempotency | 同 key 同摘要返回同 Run，不同摘要冲突 | ❌ |

## 6. P1.4 Platform Web 改造

| 模块 | 改造目标 | 是否实现 |
| --- | --- | --- |
| SDK client | 同源 `/api/langgraph`、Platform auth/project header、锁定版本 | ❌ |
| Agent pages | 页面、路由、API 和权限统一使用 Agent；SDK `assistantId` 只接收 `agent_key` | ❌ |
| Model pages | 七字段模型录入、启停和脱敏 Credential 状态；连接验证暂不属于当前闭环，不展示 Tools 管理 | 部分 |
| Chat stream | `useStream` 是 live messages/tools/interrupt/loading/error 唯一 owner | ❌ |
| Run options | 只发送模型和生成参数；浏览器不发送 Tools，未知字段不静默 | ❌ |
| Thread workspace | list/search 与 active stream 分离，快速切换不串写 | ❌ |
| HITL | 展示所有未解决 interrupt，respond 失败可重试 | ❌ |
| Cancel | SDK stream 停止与服务端 Run cancel 语义分开验证 | ❌ |
| History/branch | 只使用 checkpoint metadata，不猜 checkpoint ID | ❌ |
| UI states | loading/empty/error、草稿恢复、响应式和基本可访问性 | ❌ |
| Legacy cleanup | 无证据 fallback 和重复状态机删除 | ❌ |

## 7. 测试与证据矩阵

| 层级 | 测试点 | 通过定义 |
| --- | --- | --- |
| Platform Web unit | runtime options、禁止浏览器 Tools、view model、thread race | 失败输入可复现且无重复 Runtime state owner |
| Platform Web component | Agent/模型管理、submit/HITL/cancel/error/empty/loading | 使用真实 SDK adapter contract，不手工伪造第二套协议 |
| Platform API unit | Agent key、模型配置/Secret 脱敏、Policy merge、Context hash、token、idempotency | 纯应用层；denial 不调用 upstream |
| Platform API HTTP | endpoint allowlist、permission、scope、error、SSE headers | 未治理 endpoint 不暴露，SSE 建连前拒绝非法 actor |
| Migration | upgrade、重复执行、旧数据审计、约束 | 临时 PostgreSQL 通过；删除列另设 owner gate |
| GraphHarbor Profile | v2 + Runs API + Context + persistence + denial | 真实 API/Worker/PostgreSQL/Redis，无 mock upstream |
| Shortest chain | Platform API -> GraphHarbor -> Runtime | owner 授权 `.env` 的 local-compat 模型链，真实链证据待完成 |
| Browser E2E | Web -> API -> GraphHarbor -> Runtime | send/stream/reopen/respond/cancel 和跨 project denial |
| Restart E2E | API/Worker 分别重启 | 同 Thread/Run 从 durable checkpoint/state 恢复 |
| Security | forged metadata/context/agent_key/assistant_id/project、Base URL、日志脱敏 | fail closed，无 SSRF、跨 project 内容和 secret 泄漏 |
| Human | owner UAT | 产品结构、交互和实际功能获明确接受 |

## 8. 最终确认清单

P1 只有全部必需项成立才能完成：

1. `GATE-01`、`GATE-11`、`GATE-14` 已接受；Run consistency 等 owner 决策已冻结，`GATE-10` 历史数据盘点已完成并写入 OpenSpec verification；
2. Platform Web 不识别 GraphHarbor，不直连 upstream；
3. SDK Compatibility Profile 覆盖实际使用的全部路径和字段；
4. Platform Agent、`agent_key`、`graph_id`、Thread、Run 不再混用；
5. 模型录入可经受信边界被 Runtime 实际使用，Secret 不进入浏览器/Run/GraphHarbor，Context snapshot/hash 与 delegation 实际绑定，Runtime 内部 `tools: []` 不退化；
6. 所有 Run create 入口进入同一 application use case；
7. GraphHarbor 是 Thread/Run/Checkpoint/Event 唯一执行事实源；
8. Gateway allowlist、project isolation、SSE pre-auth 和 denial 真实通过；
9. 浏览器完整链、API restart、Worker restart 和 owner UAT 通过；
10. 未覆盖边界如实标记 `blocked/deferred`，没有用 skip/mock 冒充；
11. 旧代码只有在替代证据存在后删除；
12. Current standards/architecture/diagram 已更新，批准的旧资料已一次性归档；
13. `verification.md` 为 `Complete/Accepted/Approved`；
14. delta specs 已 sync，change 已 archive。

本阶段明确不要求 Langfuse/OTLP、生产灰度、性能 SLO、Sandbox/远程 MCP 或自动回滚。它们必须留在
deferred 清单中，但不得反向阻塞 P1 的当前验收，也不得被误写成已经具备。
