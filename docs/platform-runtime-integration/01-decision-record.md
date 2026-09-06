# Platform Runtime Integration 决策记录

> 2026-09-04 处置：D04/D05 中旧模型代理、revision、Secret Store 和 RS256/JWKS 设计已废弃。当前只
> 保留最小七字段模型配置和服务端加密契约；旧内容不再作为实施输入。

- 文档类型：Draft Supporting Decision Record
- 状态：`pre-apply-approved; implementation-partial`
- 阶段口径：当前实施使用 `L1/L2/L3`；文中的 `P1` 仅指历史 OpenSpec 变更范围，不是新的实施阶段。
- 决策 owner：用户
- 记录日期：2026-09-04
- 关联 change：[`redesign-platform-runtime-integration`](../../openspec/changes/redesign-platform-runtime-integration/)

## 1. 决策纪律

每项决策必须同时回答：

1. 谁拥有数据或行为；
2. 哪一层可以写入；
3. 成功输入、输出和错误语义是什么；
4. 缺失、越权、超时和重启如何处理；
5. 哪条最短真实链能证明它；
6. 哪些旧代码、旧数据或旧文档要在证据后处置。

`Accepted` 只表示方案已获 owner 接受，可以进入 apply contract；不表示代码、迁移或真实链已经通过。

## 2. Owner 决策总表

| ID | 决策 | 状态 | 当前含义 |
| --- | --- | --- | --- |
| D01 | Agent/Thread 标识与绑定 | Accepted | `agent_key = graph_id = assistantId`；Thread 首次 Run 绑定 Agent，之后不可切换 |
| D02 | Context transport | Accepted | Gateway server-side promotion；浏览器候选值经服务端决议后转成标准顶层 `context` |
| D03 | Context schema 与 Tools | Accepted | 使用现有 Runtime 字段；Tools 三态保留，浏览器不能提交 Tools |
| D04 | 模型配置与凭据 | Accepted | 七字段配置；API key 只写不读，服务端加密，Secret 不进入 Run/GraphHarbor |
| D05 | Auth/delegation | Accepted | delegation 绑定 target、scope 和 Context hash；RS256/JWKS 旧方案废弃 |
| D06 | 执行事实源与 Run ledger | Accepted | GraphHarbor PostgreSQL 是 Thread/Run/Checkpoint/Event 事实源；Platform 只保存治理快照和最小 ledger |
| D07 | 幂等与 reconciliation | Accepted | 统一 launch use case；intent/outbox、Idempotency-Key、request digest、timeout reconciliation |
| D08 | 并发、SSE 与取消 | Accepted | Chat 单 Thread 单 active Run；HITL 仍 active；SSE 断开不取消，显式 Stop 才取消 |
| D09 | Gateway allowlist | Accepted | 只开放正式 Chat 所需显式 endpoint allowlist；不做 catch-all |
| D10 | 历史 Thread 与 fallback | Accepted | 只为真实需求保留读取兼容；必须有脱敏 fixture；无证据 fallback 待新链通过后删除 |
| D11 | 最小观测边界 | Accepted | 通用 Run/Event、结构化错误和 correlation；Runtime 不接 GraphHarbor 专属观测 SDK |
| D12 | 版本、迁移与发布 | Accepted | 锁版本；数据库 forward-only migration；删除和切换等待证据与 owner 处置批准 |

## 3. 详细方案

### D01：Agent 和 Thread

- Platform 产品只维护 `(project_id, agent_key)` 的 Agent 关系。
- `agent_key` 创建后不可复用；改名创建新 key，旧 key 禁用。
- Thread 创建先绑定可信 `tenant/project`，第一次被接受的 Run 才绑定 `agent_key`。
- 后续 Run 使用不同 Agent 时返回 `409 AgentThreadMismatch`，不调用 GraphHarbor。
- 两个并发首次 Run 必须有数据库唯一约束或等价并发保护，只允许一个成功。
- 用户切换 Agent 必须创建新 Thread。

### D02–D03：Context 和 Tools

- 浏览器只能提交模型和生成参数偏好，不能提交身份、Project、Secret、`tools` 或 `enable_tools`。
- Gateway 校验权限、Policy、Agent defaults 和 per-run preference，生成最终标准顶层 `context`。
- Runtime Context 当前只允许 `model_id`、`temperature`、`max_tokens`、`top_p`、`tools`。
- `tools` 缺失表示继承服务端决议，`tools: []` 表示明确禁用，非空列表表示服务端允许子集。
- `system_prompt` 属于 Graph/Agent，不属于浏览器运行配置。
- 使用版本化稳定 JSON + SHA-256 计算 `context_hash`；hash 绑定 delegation 和治理记录，不进入 Runtime Context。

### D04：模型配置和凭据（替代旧模型代理方案）

- Platform 保存 `provider`、`display_name`、`base_url`、`protocol`、`model`、加密后的 `api_key` 和 `enabled`。
- API key 只写不读；GET/list 只返回 `credential_configured`。密钥不进入浏览器、Run、Context、GraphHarbor、日志或审计详情。
- 停用模型、字段校验失败、凭据错误和连接失败全部 fail closed。
- 旧 `execution_model_id`、revision、Secret Store 编排和统一代理要求已废弃。

### D05：认证和 delegation

- Platform session 先完成 actor/project/permission 校验，再签发单次 operation-scoped delegation。
- delegation 绑定 issuer、audience、actor、tenant/project、Agent/Graph/Thread、scope 和 `context_hash`。
- 旧生产 `RS256 + JWKS`、`kid` 轮换和 workload identity 方案已废弃。
- GraphHarbor 在持久化/调度前校验 token；Runtime 在模型和 Tool 执行前再次校验可信 Runtime identity。
- `get_agent({})` 只允许无副作用构图、import 和 introspection，不得成为匿名执行入口。

### D06–D07：事实源、ledger、幂等和恢复

- GraphHarbor PostgreSQL 唯一保存 Thread、Run、Checkpoint、Event 执行事实。
- Platform 保存不可变 Run intent、Context snapshot/hash、模型执行引用、idempotency/digest、operation/audit 关联和可重建 projection。
- 所有 Run create 入口进入同一个 `LaunchRuntimeRun` application use case。
- 先写 intent/outbox，再以 `Idempotency-Key` 调 GraphHarbor；超时进入 `run_start_unknown`，通过查询和 reconciliation 收敛。
- 同 key + 同 digest 返回原 Run；同 key + 不同 digest 返回 `409 IdempotencyConflict`。

### D08：并发、SSE 和取消

```text
queued / running / waiting_human_input = active
success / error / cancelled            = terminal
```

- 同一 Thread 只有一个 active Run；HITL 等待中的 Run 仍阻止新 Run。
- HITL 只能对目标 Run 以 interrupt ID 响应；需要重新开始时先显式 cancel。
- SSE 断开不改变 Run；重新进入页面时按 snapshot 和 `since` 游标恢复。
- 事件按 `seq` 去重，重复事件不能重复应用，终态不能回退。
- API/Worker 重启以 GraphHarbor durable 状态为恢复依据，不以 Platform projection 反向覆盖事实。

### D09：Gateway endpoint allowlist

允许的正式 Chat surface：Thread create/search/get、State/History、Protocol command、Protocol event SSE、Run get/list/cancel。

默认拒绝：Assistant mutation、Cron、Batch、Store、System admin、prune、copy、state update、未登记 method/path 和 catch-all proxy。
每个实际 endpoint 必须在 Compatibility Profile 中单独记录字段、envelope、错误码和脱敏规则。

### D10：历史 Thread 和 fallback

- 实施期先盘点真实历史 Thread、旧 payload 和仍需保留的 route。
- 每类真实格式建立脱敏 fixture 和读取断言；没有 fixture 的兼容不进入正式链。
- 兼容代码只位于读取 normalization 边界，不写回旧 Thread，不生成新旧混合数据。
- 旧 `/runs/*` 不作为透明 fallback；版本回退是整体版本切换。
- `GATE-10` 在 inventory 和 fixture 结果产生前保持 `Pending inventory`。

### D11–D12：观测、版本和发布

- P1 只要求 `operation_id`、`thread_id`、`run_id` 可关联，且失败、取消、重试、重启恢复和未知状态可查询。
- Token、Secret、Context、完整消息和 Tool 参数不得进入普通日志。
- 组件版本组合必须锁定；升级先跑 Compatibility Profile。
- 数据库只做 forward-only migration；删除旧列、route、parser 或文档需真实证据、备份/迁移证明和 owner 处置批准。
- P1 不做 canary、自动回滚、性能 SLO、复杂 Trace UI、Sandbox 或远程 MCP。

## 4. 明确 Deferred 或待确认项

| 项目 | 状态 | 处理方式 |
| --- | --- | --- |
| 历史 Thread inventory | Pending inventory | 读取真实数据/fixture 后决定保留范围 |
| 统一模型代理、Secret Store、execution reference、JWKS | Superseded/Rejected | 不进入本 change；未来需求另立 change |
| Langfuse/OTLP、Run Explorer、canary、性能 SLO、自动回滚 | Deferred | 不计入 P1 完成门槛 |

## 5. 讨论结果

### 5.1 历史 change 处置台账

| Change | Disposition | Sync | 处置边界 |
| --- | --- | --- | --- |
| `platform-runtime-graphharbor-canary-routing` | `Abandoned` | 不 sync | 当前单 upstream，不做 Platform canary |
| `runtime-run-event-contract-and-run-explorer` | `Deferred` | 不 sync | Run Explorer 以后按 GraphHarbor 事实源另立设计 |
| `add-react-agent-web` | `Rejected` | 不 sync | 保留历史验收记录，未来 archive without sync |
| `redesign-platform-runtime-integration` | `Accepted; implementation-partial` | 按任务完成后 sync | 当前唯一实施真源 |

以上处置只改变 OpenSpec 生命周期，不删除业务代码或历史数据。替代证据完成前，旧兼容代码仍按
GATE-10 读取 fixture 规则保留。

截至 2026-09-04，架构争议已关闭，剩下的是实施约束和证据工作：

```text
已接受方案 ≠ 已实现 ≠ 已验证 ≠ 已上线
```

下一步不是继续发散设计，而是完成 GATE-10 inventory、模型代理落地约束确认，再按 Harness 计划进入 apply。
