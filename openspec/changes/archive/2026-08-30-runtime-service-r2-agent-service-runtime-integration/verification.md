# R2 Verification

## Pre-Apply Review

- 变更等级：B2，单一 `apps/runtime-service` Runtime 链路；不涉及 Platform、权限数据迁移或生产发布。
- 评审结论：可实施。方案只修改新 `src/runtime_service`，没有旧代码适配、万能 Builder 或隐式模型 fallback。

## Checks

| 检查 | 结果 |
| --- | --- |
| `uv run pytest tests/runtime tests/test_r0_baseline.py tests/services/reference_agent -q` | 26 passed |
| `RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -q` | 1 passed（真实 DeepSeek 中转模型） |
| `uv run python -m compileall -q src` | passed |
| `uv lock --check` | passed |
| `git diff --check` | passed |
| `openspec validate runtime-service-r2-agent-service-runtime-integration --strict --no-interactive` | passed |
| `graphify update .` | passed |

## Residual Risk

- `reference_agent` 的本地 Principal/Policy 仅用于独立调试，不代表 Platform 授权；真实 Delegation Token 接入留给 P1。
- 模型覆盖发生在构图前，运行中不能切换 Provider；这符合当前不建设自定义路由的决定。
- R2 尚未接入 Middleware、Tool/MCP、Backend、Checkpoint 和 Run Event，这些边界由后续阶段验证。

## Docs / Runbook Impact

- 更新 `reference_agent/README.md`、两个 LangGraph 配置描述和 28 号开发计划的阶段状态。
- 没有新增部署环境变量；真实 E2E 使用现有 `DEEPSEEK_PROXY_*` 配置。
