# R4 Production Closure Verification

## Status

- Status: `Partial`
- Disposition: `Pending acceptance`
- Execution band: `B3 Governed`
- Owning locus: `apps/runtime-service`
- Affected chain: Agent Server Auth -> Service `get_agent()` -> Runtime Middleware -> Deep Agents/MCP Tool -> durable checkpointer/Workspace Backend

## Pre-apply Review

- Pre-apply review: `Approved`
- Owner: 用户
- Decision: 用户明确批准 `apply R4`
- Evidence: proposal、specs、design、tasks 已整体审阅并获批准，允许进入实现阶段
- Waiver: 无

## Baseline

- 当前 R4 Demo local 测试已通过，但尚未证明 Deep Agents 内置 Tool 已被真实 graph 收缩。
- 当前 `backend_demo` 的进程内 `StateBackend` 不能证明跨 Worker 或重启后的生产持久性。
- 外部 Agent Server durable checkpointer、PostgreSQL、Redis 和真实 Sandbox 的可用性尚未作为本变更的通过条件确认。

## Evidence Matrix

| Boundary | Command/check | Input | Result | Evidence status |
| --- | --- | --- | --- | --- |
| Local/minimal | `apps/runtime-service` R4 capability tests | 显式 `_runtime_test_*` adapter、fake model | Existing baseline only; closure tests not yet run | `Pending` |
| Runtime Policy | 三个 R4 `get_agent()` 的 allowlist、匿名入口和伪造 Tool Call 测试 | verified Auth facts 或显式 local test adapter | Not executed for this change | `Pending` |
| Deep Agents graph | 真实 `create_deep_agent` graph Tool surface 与执行失败测试 | locked `deepagents==0.7.8` | Not executed for this change | `Pending` |
| Thread Workspace | 同 Thread 跨 Turn、不同 Thread 隔离 | `StateBackend` + explicit local checkpointer | Not executed for this change | `Pending` |
| Shortest chain | Agent Server Auth -> Service -> Middleware -> Backend | durable checkpointer environment | External environment not yet verified | `Pending` |
| Production-like | Worker restart、数据库/Redis、备份恢复、清理和告警 | real durable deployment resources | Not executed; mark `blocked`/`not-executed` if unavailable | `Pending` |
| Static hygiene | `git diff --check`、OpenSpec strict validation、`graphify update .` | repository worktree | 已通过；最终结果见下方 Final Verification Update | `passed` |

## Residual Risk And Uncovered Boundaries

- `StateBackend` 的生产保证依赖 Agent Server durable checkpointer；单进程或 `InMemorySaver` 结果不得升级为生产证据。
- 在真实 Sandbox Provider、Thread 绑定、清理和重连责任未冻结前，Shell/Git/代码执行保持关闭，不能声称 R4 完成。
- 真实 MCP 远程凭据、连接超时、取消和关闭生命周期需要部署环境证据；本地 fake MCP 不能替代该证据。
- 生产多租户、备份恢复、TTL/配额和告警仍需 production-like 环境验证。

## Docs And Runbook Impact

- 实现后更新 `apps/runtime-service/docs/knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md`、`20-runtime-backend-workspace-skills-and-subagents-design.md`、`28-runtime-refactor-development-plan.md` 和 `31-runtime-refactor-alignment-audit.md`。
- 若 Agent Server、持久化资源或 Sandbox 的部署/恢复操作发生变化，补充对应 README/runbook；没有真实部署证据时不得写成已支持。

## Completion Disposition

完成条件：所有 required local 与 shortest-chain evidence 通过；B3 owner review 已批准；production-like 外部边界要么通过，要么在 disposition 中明确 `blocked`/`not-executed` 及不影响哪些声明。未满足时保持 `Pending`，不得标记 `Complete` 或 `Accepted`。

## Apply Update (2026-09-01)

| Boundary | Command/check | Input | Result | Evidence status |
| --- | --- | --- | --- | --- |
| Local/minimal | `uv run pytest tests/services/test_r4_capability_demos.py -q` | fake model、fake MCP、显式 local auth/checkpointer | `44 passed` | `local-complete` |
| Deep Agents graph | 同上 | Deep Agents `0.7.8`，真实 `create_deep_agent` graph | Deep Agent 只暴露声明的 filesystem/task surface；Backend 不暴露 `execute`/`task`；伪造调用返回 `runtime.tool.not_allowed` | `local-complete` |
| MCP | 同上 | 官方 `MultiServerMCPClient` + 本地 stdio fake | 工具加载、真实 graph 执行、名称冲突、required/optional 失败、客户端资源/凭据注入拒绝通过 | `local-complete` |
| Thread Workspace | 同上 | `StateBackend` + `InMemorySaver`，graph 重建，`thread-a`/`thread-b` | 同 Thread 跨 graph rebuild 可读；不同 Thread 返回 not found | `local-complete` |
| Skill boundary | 同上 | 伪造 `/skills/runtime-notes/SKILL.md` 写调用 | 在 Runtime Tool handler 前返回 `runtime.tool.not_allowed`；官方 `/skills/**` deny permission 已配置 | `local-complete` |
| Durable chain | `uv run pytest tests/durable -m durable -q` | Agent Server、PostgreSQL、Redis、Worker | 当前环境未提供可用 durable entitlement/resources | `blocked` / `not-executed` |
| Production-like | R4 durable smoke entrypoint | licensed Agent Server、持久化依赖、真实 Sandbox | 未执行；没有真实 Sandbox 时 `execute` 保持关闭 | `blocked` / `not-executed` |

### Remaining Tasks

- `3.4`：尚无真实 Subagent 委派调用及事件/工具隔离断言。
- `5.4`：尚无完整 checkpointer/backend 资源清理和 scope mismatch 专项测试。
- `5.5`、`5.6`、`6.2`、`6.3`：依赖真实 Agent Server 或生产资源；不得用本地内存结果替代。

结论：R4 当前为 `local-complete`，不是 `chain-complete` 或 production complete。

## Final Verification Update (2026-09-01)

| Boundary | Command/check | Input | Result | Evidence status |
| --- | --- | --- | --- | --- |
| Full runtime regression | `uv run pytest tests -q` | 当前 runtime-service 测试集 | `126 passed, 11 skipped in 66.93s`；skip 为真实 Durable/E2E 环境门控，不计入通过 | `local-complete` |
| OpenSpec validation | `openspec validate "runtime-service-r4-production-closure" --strict --no-interactive` | 当前 R4 change artifacts | `Change 'runtime-service-r4-production-closure' is valid` | `passed` |
| Static hygiene | `git diff --check` | repository worktree | 通过，无 whitespace error | `passed` |
| Knowledge graph | `graphify update .` | repository worktree | 成功重建 `33,554 nodes`、`67,451 edges`、`1,483 communities` | `passed` |

本次验证只完成 R4 local harness 和静态门禁。OpenSpec 仍有 6 项能力任务开放：`3.4`、`5.4`、
`5.5`、`5.6`、`6.2`、`6.3`；它们分别涉及真实 Subagent 委派、scope/cleanup、跨 Worker/服务
重启、PostgreSQL/Redis/SIGTERM/备份/TTL/告警以及真实最短链。R4 不能因此升级为
`chain-complete` 或 production complete。
