# Agent/Thread 统计与保留策略

- 文档类型：Harness supporting policy record
- 状态：`local-complete; legacy assistant cleanup completed; retention window pending`
- 更新时间：2026-09-05
- 适用范围：Platform Web、Platform API、GraphHarbor Agent Server、Runtime Service

## 1. 结论

当前产品对象是 Agent，不再维护 upstream Assistant 主数据。`langgraph.json` 中注册的 graph 是当前
Runtime 可执行 Agent 的来源；Platform 数据库中的 `agents` 只是项目级配置、权限和默认值绑定。

GraphHarbor 持有 Thread、Run、Checkpoint、Event 的唯一事实。Platform 的 `runtime_runs` 只保存
治理关联、Context snapshot/hash、幂等和审计信息，不能被当成 Thread/Run 主数据。

## 2. 统计口径

| 指标 | 唯一事实源 | 计算方式 | 备注 |
| --- | --- | --- | --- |
| 可执行 Agent 数 | `langgraph.json` / GraphHarbor graph catalog | `graphs/search` 或 `graphs/count` 返回的 graph key 数 | 不统计旧 Assistant 行；当前正式 graph 为 `reference_agent`、`workflow_demo` |
| 项目 Agent 数 | Platform PostgreSQL `agents` | 按 `project_id` 过滤记录数 | 表示项目绑定/配置数，不表示 graph catalog 总数 |
| Agent 使用数 | GraphHarbor Run + Platform `runtime_runs.agent_key` | 按 `agent_key` 去重 | 只统计真实 Run，不读取 `langgraph_assistant_id` 作为新键 |
| Thread 总数 | GraphHarbor PostgreSQL | 通过 Gateway 的 scoped `threads/count` | Platform `runtime_runs` 的 distinct `thread_id` 只能作为治理下界 |
| Run 总数/状态 | GraphHarbor PostgreSQL | 通过 Gateway 的 scoped Runs 查询 | Platform 状态是 projection，不覆盖 upstream 状态 |
| Active Run | GraphHarbor 当前 Run 状态 + Platform durable ledger | `submitted/running` 或 HITL interrupt 未解决均为 active | SSE 断开不改变 active；显式 cancel 才改变状态 |

任何跨项目统计都必须由 Platform API 先做 project scope 校验，再调用 GraphHarbor；浏览器不能直连
GraphHarbor，也不能根据 Thread metadata 自行汇总权限范围。

## 3. 保留策略

### 3.1 Agent

- `langgraph.json` 和 graph 代码随 Runtime 发布版本保留；删除 graph 必须先下线对应项目绑定。
- Platform `agents` 记录在项目仍使用时保留，可先设为 disabled；disabled Agent 不允许新 Run，历史
  Thread/Run 仍可按权限读取。
- 删除 Agent 只删除 Platform 配置和 profile，不级联删除 GraphHarbor Thread/Run；后者必须有单独、
  明确的 Thread purge 操作和 owner 审批。

### 3.2 Thread/Run

- active Run、等待 HITL 的 Run、未完成 reconciliation 的 Run 永不自动清理。
- 已完成 Thread/Run 的具体时间窗口由 GraphHarbor 部署的 retention 配置决定；在没有明确窗口前，
  本地环境不自动执行 prune，避免误删验收证据。
- Platform governance 记录至少保留到对应 GraphHarbor 数据可审计的时间结束；清理必须同时留下
  汇总审计事件，不复制完整 message、Context 或 provider secret。

### 3.3 历史 Assistant 兼容数据

兼容读取只服务于有真实业务价值的历史 Thread。owner 已确认旧 `graph_id=assistant` 记录及其 profile
无需保留；删除前确认没有对应 `runtime_runs`，随后完成物理删除。当前状态：

| 表 | 数量 | 观察 |
| --- | ---: | --- |
| `agents` | 0 | 旧 `graph_id=assistant` 行已删除 |
| `assistant_profiles` | 0 | 对应旧 profile 已删除 |
| `runtime_runs` | 125 | 未发现上述旧 Agent 对应的当前项目治理引用 |
| `runtime_run_interrupts` | 2 | 仅为治理索引 |

删除不级联 GraphHarbor Thread/Run；历史执行事实仍按 GraphHarbor retention 管理。旧列和 fallback
的 migration/清理仍需独立审计，不能因为记录删除而宣称全部历史迁移完成。

## 4. 实施与代码落点

- Graph catalog：`apps/runtime-service/langgraph.json`；Platform Gateway 的 `graphs/search`、
  `graphs/count` allowlist。
- Project Agent：`apps/platform-api/app/modules/agents`；数据库表 `agents`、`assistant_profiles`。
- Thread/Run 代理：`apps/platform-api/app/modules/runtime_gateway`；事实读取转发 GraphHarbor。
- Governance projection：`apps/platform-api/app/modules/runtime_gateway/infra/sqlalchemy/models.py`。
- 旧包兼容：`apps/platform-api/app/modules/assistants` 只做导出，不得新增业务逻辑。

## 5. 验证

- 删除前只读盘点：SQLite `mode=ro` 查询上述四张表；owner 确认后删除旧 Agent/profile，删除后复查为 0。
- Agent catalog：读取 `apps/runtime-service/langgraph.json`，正式 graph 为 `reference_agent`、`workflow_demo`。
- Platform API：Agent CRUD、Agent/Thread 绑定、跨 project denial 和 active/HITL 冲突测试。
- GraphHarbor 链：`threads/count`、Run list/status、真实 `workflow_demo` HITL respond 通过 Gateway 验证。
- 浏览器：Playwright 已验证登录、项目切换、Agent/Graphs/Chat 页面；完整 send/stream/reopen/HITL/respond/cancel/cross-project 仍未逐项完成。

## 6. 当前本地数据与最小额外输入

本地 `langgraph.json` 已有真实 `reference_agent` 和可中断的 `workflow_demo`，不需要 fake model 或
fake Agent。当前账号已具备 catalog refresh/项目绑定权限，`dev` 项目已完成两个真实 Agent 绑定。

浏览器真实 Chat E2E 的前置条件已满足：

1. 当前账号已允许刷新 Graph catalog、创建项目 Agent；
2. `reference_agent` 和 `workflow_demo` 已完成真实项目绑定；
3. owner 已确认旧 `graph_id=assistant` 记录和 profile 无需保留并已删除。

不需要提供生产 DRI、Secret Store、JWKS、Provider smoke、execution reference 或额外真实租户数据。
旧记录删除不级联 GraphHarbor Thread/Run；其余浏览器交互仍需逐项执行。

## 7. 剩余门禁

- 旧 `graph_id=assistant` 记录/profile 的 owner 删除门禁已完成。
- `3.6` 仍保留为部分完成：旧记录已删除，但历史列删除、完整迁移审计和失败恢复演练尚未完成。
- `7.4` 仍保留为部分完成：服务端真实 HITL 已通过，浏览器完整交互尚未逐项执行。
- `7.6` 仍需 owner 做页面 UAT；技术验收不能代替产品接受结论。
