# R2 Workflow Contract Verification

## Pre-Apply Review

- 变更等级：B3 Governed。
- owning locus：`apps/runtime-service`。
- 原因：修改 active spec、改变认证失败语义、增加 Interrupt/Resume 恢复合同。
- 当前决定：建议保留 R1 fail-closed Auth；空 `RunnableConfig` 不补 Principal/Policy；本地测试使用显式 test-only adapter。
- owner 已批准 Workflow 纳入 R2，以及 `get_agent({})` 缺少 Auth 时 fail-closed 的合同；允许进入 apply。
- 批准范围：本地 Workflow 使用 in-memory checkpointer；真实 PostgreSQL/Redis、Worker 重启和生产 Durable 仍由 R6 验证。

## Checks

| 层级 | 命令/检查 | 输入 | 结果 |
| --- | --- | --- | --- |
| contract | `openspec validate runtime-service-r2-workflow-contract --strict --no-interactive` | 本变更四类 planning artifacts | passed |
| local | `uv run pytest tests/services/workflow_demo tests/services/reference_agent tests/test_r0_baseline.py -q` | fake workflow、显式 local adapter、Auth denial | `21 passed` |
| local-full | `uv run pytest tests -m "not integration and not durable and not e2e" -q` | Runtime 本地测试 | `82 passed, 13 deselected` |
| chain | `uv run pytest tests/integration -q` | production reference Auth chain + `langgraph.demo.json` workflow chain | `2 passed, 1 skipped`；skip 为未设置 `RUNTIME_E2E=1` 的真实模型测试 |
| build | `uv run python -m compileall -q src tests scripts` | Runtime Service Python 源码 | passed |
| lock | `uv lock --check` | Runtime Service 依赖锁 | passed |
| hygiene | `git diff --check` | 工作区差异 | passed |
| formal | R6 Durable 测试 | PostgreSQL、Redis、Worker restart | 不属于本变更；由 R6 单独验证 |

## Acceptance Evidence

- 条件分支两条路径均有可失败测试，且互不执行对方节点。
- Interrupt 能产生可识别恢复点；Resume 使用服务端声明的 interrupt 标识。
- 同一 Thread Resume 后，已完成节点只执行一次。
- 重复加载静态 Workflow 的 nodes、edges、state schema 一致，且无 Sandbox/MCP/数据库/Platform I/O。
- `reference_agent.get_agent({})` 在无 Auth facts 时返回稳定认证错误。
- 显式 local test adapter 可以运行 fake model，但生产配置和匿名 Agent Server 请求不会启用它。

## Implementation Evidence

- `workflow_demo` 使用 `InMemorySaver`；输入 `route=approve/reject` 分别进入唯一条件路径。
- `requires_confirmation=True` 时首次调用返回 `workflow_confirmation` interrupt；同一
  `thread_id` 使用 `Command(resume="approve"|"reject")` 完成恢复。
- Resume 后 `prepared_count` 保持为 `1`，证明已完成的 `prepare` 节点未重复执行。
- `langgraph.demo.json` 下的 Workflow Agent Server `/info`、assistant 搜索和执行链均通过。
- `reference_agent.get_agent({})` 仍返回 `runtime.auth.missing_principal`；显式 fake model
  和 Auth fixture 测试通过。

## Uncovered Boundaries

- 本地 in-memory checkpointer 不能证明 PostgreSQL 持久化、Redis 队列、Worker 重启、SIGTERM handoff 或跨进程恢复。
- 本变更不验证 Platform 正式签发链、Run/Event 投影或生产发布。

## Docs / Runbook Impact

- 需要同步 11、28、31 号 R2 对齐记录和 `workflow_demo/README.md`。
- active spec 只有在 owner 接受并完成实现验证后，才执行 delta sync；不修改归档 R2 历史文件。

## Disposition

- 当前：`accepted-local-agent-server / R6-durable-deferred`
- active spec delta 已在 owner 批准和本地/Agent Server 验证后 sync；不能使用 R6 skip 作为
  Durable 通过证据。
