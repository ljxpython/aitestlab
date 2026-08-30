# R3 Verification

## Pre-Apply Review

- 变更等级：B3，涉及公共 Middleware 生命周期、超时和失败传播语义。
- 评审结论：任务所有者已明确同意进入 R3；实现范围限制在新 Runtime 包和 reference service。
- 取舍：复用 LangChain 官方 limit/error/retry 能力；本阶段不加入 fallback、Model Retry、Tool Retry 或 Run Finalizer。

## Checks

| 检查 | 结果 |
| --- | --- |
| `uv run pytest tests/middlewares tests/runtime tests/test_r0_baseline.py tests/services/reference_agent -q` | 33 passed |
| `RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -q` | 1 passed（真实 DeepSeek 中转模型） |
| `uv run python -m compileall -q src` | passed |
| `uv lock --check` | passed |
| `git diff --check` | passed |
| `openspec validate runtime-service-r3-middleware-reliability --strict --no-interactive` | passed |
| `graphify update .` | passed |

## Residual Risk

- `ModelCallTimeoutMiddleware` 当前覆盖异步模型调用；Runtime Service 的正式入口和验证链路均为 async。
- `reference_agent` 暂无业务 Tool，因此 ToolError/ToolRetry 未装配空实例；官方组件的显式异常和重试边界由独立契约测试覆盖。
- 未验证中断 Tool Call 的 checkpoint 恢复；只有 R6 真实 Durable Run 复现后才决定是否实现恢复 Middleware。
- Run 总 deadline、Provider fallback、观测和最终状态持久化仍由后续阶段负责。

## Docs / Runbook Impact

- 更新 `reference_agent/README.md`，说明 Middleware 顺序和 Tool retry 何时加入。
- 更新 28 号开发计划，标记 R3 完成、R4 为下一阶段。
- 组合根已将短小装配逻辑直接内联到 `get_agent()`，没有保留 `_build_agent()` 私有 Builder。
