# R3 Middleware Closure Verification

## Pre-Apply Review

- 变更等级：B3，涉及 Agent Middleware 的公共失败传播、重试和模型切换语义。
- 状态：任务所有者已明确同意 apply；实现和验证完成，保留生产 fallback 边界。
- 评审证据：任务所有者在当前会话明确回复“同意 apply R3”。
- 当前基线：R3 归档记录中的 Tool Error/Retry 未真实接入 `reference_agent`，只有独立 Middleware 测试。

## Checks

| 检查 | 结果 |
| --- | --- |
| `uv run pytest tests/middlewares tests/services/reference_agent tests/runtime tests/test_r0_baseline.py -q` | 68 passed |
| `RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -q` | 1 passed；真实 DeepSeek 中转模型，无 fake fallback |
| `uv run python -m compileall -q src tests scripts` | passed |
| `uv lock --check` | passed |
| `git diff --check` | passed |
| `openspec validate runtime-service-r3-middleware-closure --strict --no-interactive` | passed |
| `graphify update .` | passed；图谱已更新 |
| `RUNTIME_E2E=1 uv run pytest -q` | `100 passed, 23 skipped, 1 failed`；失败位于现有 `spikes/aegra/tests/test_platform_context.py`，fixture 缺少 `scope` claim，与本次 R3 文件无关 |
| `uv run ruff check ...` | 未执行；当前 `pyproject.toml` 未声明 ruff，环境中无该可执行文件 |

## Residual Risk

- 真实 Provider fallback 的模型目录、凭据和 Policy 授权尚未冻结；当前 fallback/retry 仅由显式 local test adapter 驱动。
- Run 总 deadline、durable terminal/finalizer、Sandbox 和 orphaned Tool Call 恢复仍由其他阶段/变更负责。
- `ToolErrorMiddleware` 当前只处理 `ConnectionError`/`ValueError` 的脱敏摘要；权限错误、取消、interrupt 和未知异常继续传播。

## Docs / Runbook Impact

- 更新 15 号 Middleware 对齐矩阵和 Reference Agent README。
- 当前证据等级：Tool Error/Retry 为 local graph-complete；Model fallback/retry 为 test-only；真实 Model smoke 为 chain-complete；Durable/生产 fallback 仍未完成。
