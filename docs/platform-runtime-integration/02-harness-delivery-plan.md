# Platform Runtime Integration Harness 实施与验收计划

> 旧模型代理/revision/Secret Store/JWKS 方案已 `Superseded/Rejected`。本计划当前只实施七字段模型配置、
> API key write-only 和服务端加密；相关旧步骤不再是门禁。

- 文档类型：Draft Supporting Delivery Plan
- 状态：`pre-apply-approved; implementation-partial`
- 说明：`P1.x` 是历史 OpenSpec 变更分解；当前实施和验收统一以 `L1/L2/L3` 为准，`L1` 即当前 P0 模型配置闭环。
- Execution band：B3 Governed
- 任务真源：[`tasks.md`](../../openspec/changes/redesign-platform-runtime-integration/tasks.md)
- 证据真源：[`verification.md`](../../openspec/changes/redesign-platform-runtime-integration/verification.md)

## 1. Harness Intake

| 字段 | 结论 |
| --- | --- |
| Goal | 在不重写 Runtime Durable Core 的前提下，完成 Platform 到 GraphHarbor 的受治理 SDK 兼容链 |
| Owning locus | `platform-api` 负责 Gateway、IAM、Policy、ledger、delegation；`platform-web` 负责 SDK 产品交互 |
| Adjacent loci | GraphHarbor Compatibility Profile、`runtime-service` Runtime contract |
| Shortest chain | Web -> API Gateway -> GraphHarbor API -> Redis -> Worker -> Runtime -> PostgreSQL |
| Standards | `docs/harness/README.md`、`docs/standards/01-ai-execution-system.md`、相关 Platform leaf standards、Runtime tests/contracts |
| Evidence depth | local/minimal -> shortest relevant chain -> formal/human |
| Human gates | owner pre-apply review、真实 Provider/租户授权、页面 UAT、删除/归档处置批准 |

## 2. 生命周期

```text
analyze
  -> scope
  -> plan
  -> pre-apply review
  -> implement
  -> local verify
  -> shortest-chain verify
  -> formal/browser/UAT
  -> accept
  -> sync specs
  -> cleanup/archive
```

当前已完成：分析、定界、方案记录、owner pre-apply review、GATE-13、七字段模型管理基础实现和文档/OpenSpec 静态检查。
当前未完成：Runtime 动态读取平台保存的连接配置、真实 HITL 图、完整 Browser E2E、UAT、历史数据盘点和清理归档。

## 3. 阶段计划与门禁

### P1.0：决策和现状冻结

目标：冻结标识、Context、事实源、幂等、并发、allowlist、历史兼容和文档处置边界。

必须完成：

- 锁定版本组合并形成 Compatibility Profile 清单；
- 为正式 Chat、Gateway caller 和历史 Thread 建 characterization fixture；
- 完成 GATE-10 inventory；
- 旧模型代理 owner、Secret Store 接口和 Provider proxy 兼容性方案已废弃，不再作为专项门禁；
- 对旧文档和重叠 OpenSpec 形成 disposition 矩阵。

入口门禁：D01–D12 已 Accepted，pre-apply review 已 Approved。
出口门禁：GATE-10 有 inventory 结论，七字段模型配置和 local-compat profile 证据完整，fixture 可执行。

### P1.1：GraphHarbor Compatibility Profile

目标：先证明 GraphHarbor 的通用 Agent Server surface，不用旧 `langgraph dev` 冒充真实链。

验证范围：

- Thread create/search/get、State、History；
- Protocol v2 `run.start`、`input.respond`、commands、events、SSE reconnect、cancel；
- 标准 Runs API 的 Context、durability、stream options 和 error semantics；
- delegation 缺失/过期/错误 target/scope/hash 的 fail-closed；
- API/Worker/PostgreSQL/Redis 重启后的 durable resume。

出口门禁：GraphHarbor 仅修改通用兼容层，固定版本可供 Platform 使用。

### P1.2：Platform API domain 与 migration

目标：把旧 Assistant 模块收敛为 Agent 目录、模型目录、Policy、Run governance ledger 和 delegation。

必须验证：

- `(project_id, agent_key)` 唯一性和首次 Run 绑定；
- 七字段模型配置、API key write-only、服务端加密和基础 URL/protocol 校验；
- Context resolver、Tools 三态和 hash；认证使用现有本地 delegation，不引入 RS256/JWKS；
- Run intent/outbox、Idempotency-Key、digest 冲突和 reconciliation；
- forward-only migration 与旧数据审计/回填。

出口门禁：API 本地契约和 denial 测试通过，migration 可重放，未删除旧列或旧数据事实。

### P1.3：Gateway 收敛

目标：所有 Run create 入口进入统一 `LaunchRuntimeRun`，Gateway 只开放显式 allowlist。

必须验证：

- v2 输入中的不可信偏好被消费并转成标准顶层 Context；
- GraphHarbor 请求不携带 Platform 私有字段、Secret 或身份猜测字段；
- Thread/Run/State/History/SSE/cancel 按 Project/Thread scope 授权；
- 401/403/404/409/422/502 envelope 稳定；
- denial 分支无上游持久化、调度或执行副作用。

出口门禁：allowlist、幂等、Context/hash、delegation、跨 Project denial 和日志脱敏测试通过。

### P1.4：Platform Web Chat

目标：官方 SDK 成为当前 Thread 的 live state owner，删除重复 runtime state。

必须验证：

- SDK client 固定同源 `/api/langgraph`、Platform auth 和 project scope；
- 浏览器只发送允许的模型/生成参数，不发送 Tools、身份和 Project 字段；
- Thread 列表/选择与 active stream 分离；
- submit、HITL respond、retry、cancel、history、重连、loading/empty/error 和响应式行为通过；
- `ChatDebugPage`、Tools 配置入口和无证据 legacy fallback 按处置矩阵清理。

出口门禁：组件检查和浏览器 E2E 达到可接受结果，未把 SDK view model 重新变成第二套事实源。

### P1.5：最短真实链与 owner UAT

目标：证明完整链路和真实用户可用性。

覆盖：

- 本机最短链：Web/API -> GraphHarbor -> Redis -> Worker -> Runtime -> PostgreSQL；
- owner 授权的 `.env` 真实模型只用于 local-compat smoke；
- Thread reopen、interrupt/respond、cancel、API restart、Worker restart；
- 跨 Project denial、Context/hash 一致性和敏感数据不落日志；
- Platform 页面 UAT。

出口门禁：`verification.md` 中 local、chain、formal/human 证据完整，owner 明确接受。

### P1.6：清理、同步和归档

目标：只删除已经有替代证据的内容。

- 更新 current standards、架构图、配置说明和 runbook；
- 按 disposition 矩阵删除无 fixture 的 legacy payload、route fallback、重复状态和 upstream Assistant mutation；
- accepted delta specs 先 sync 到 `openspec/specs/`；
- change 仅在 evidence Complete 后 archive；
- 旧文档移入 archive 或标为 Archived，不修改历史 OpenSpec archive。

## 4. 证据矩阵

| 边界 | 最小检查 | 当前状态 | 完成标准 |
| --- | --- | --- | --- |
| Planning coherence | `openspec validate redesign-platform-runtime-integration --strict --no-interactive` | local-complete | artifacts 合法一致 |
| Documentation | `uv run --frozen python scripts/check_docs.py` | local-complete | 导航和链接通过 |
| Platform Web | test/lint/typecheck/build | local-complete | 38 files/123 tests、typecheck、build、lint 无 error |
| Platform API | pytest、HTTP、migration、permission、audit | local-complete | 145 tests、migration、HTTP denial 和安全回归通过 |
| GraphHarbor Profile | 真实 API/Worker/PostgreSQL/Redis suite | partial | endpoint、SSE、denial、独立 API/Worker restart 已验证；HITL/去重仍待 |
| Shortest chain | 本机 local-compat smoke | local-complete | 创建、执行、流式读取、显式取消、负面场景和重启恢复通过 |
| Identity/Thread | 同 Agent、换 Agent、并发首次 Run、跨项目 | partial | active conflict、跨项目隐藏和幂等冲突已验证；换 Agent/并发专门 fixture 待补 |
| Context/Tools | 非法字段、三态、Policy 变化、hash | partial | v2 promotion、disabled model、脱敏合同通过；完整三态矩阵待补 |
| Run consistency | 重复 key、digest 冲突、timeout、restart | partial | marker/reconciliation 单测和 restart smoke 通过；正式 outbox/定时扫描待补 |
| Auth | 现有 delegation 的 target/scope/hash mismatch | partial | 本地 fail closed；生产身份治理另立 change |
| Provider | owner 授权 `.env` local-compat 调用 | local-complete | 固定非敏感 prompt smoke 通过；不形成生产代理结论 |
| Browser E2E | Web -> API -> GraphHarbor -> Runtime | partial | Runtime Models 页面加载、表单和 console errors=0；完整 Chat 流程待补 |
| Human | owner UAT | not-executed | 页面、对象模型和功能接受 |

## 5. 实施前不可跳过的检查

1. GATE-10 inventory 必须有真实输入来源、脱敏规则、fixture 路径和保留/删除结论。
2. 模型配置必须有七字段、write-only、服务端加密和脱敏证据；不再要求模型代理 owner/Secret Store。
3. 不能用 mock、fake、in-memory 或旧 `langgraph dev` 记录为 GraphHarbor 真实链通过。
4. 任何删除、迁移和发布切换都要等替代证据和 owner 处置批准。
5. `tasks.md` 勾选不等于 `verification.md` 有证据；两者必须分别维护。
