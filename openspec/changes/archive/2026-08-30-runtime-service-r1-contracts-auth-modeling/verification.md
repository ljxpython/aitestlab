# R1 验证记录

- Status: Passed
- Disposition: Ready for archive
- Pre-apply review: Approved
- Owner/依据：用户于 2026-08-30 明确同意进入 R1：Runtime Contracts / Auth / Resolver / Modeling。

## Local

- `uv run pytest tests/runtime tests/test_r0_baseline.py -q`：通过，`22 passed`。
- `uv run python -m compileall -q src`：通过。
- `uv lock --check`：通过，锁文件无需更新。
- `openspec validate runtime-service-r1-contracts-auth-modeling --strict --no-interactive`：通过。
- `git diff --check`：通过。
- R0 Graph 测试仍使用 fake model，无 Platform API 和 Provider 凭据依赖。

## Real-model / Provider

- R1 Modeling 单测不调用真实 Provider，只验证构造参数和失败映射。
- DeepSeek/GPT Provider 分支的凭据缺失会返回 `runtime.model.initialization_failed`，不会降级 fake。
- 显式加载 `.env` 并设置 `RUNTIME_E2E=1` 后运行 R0 真实 DeepSeek E2E：通过，`1 passed`。

## Shortest chain

- R1 不修改 `platform-api`，不执行跨服务链路；Platform Delegation 签发留到 P1。

## Formal / Human

- B3 pre-apply review 已获用户批准；R1 本地验收通过，变更可归档。

## 未覆盖边界与残余风险

- LangGraph Agent Server `Runtime.context` 的 HTTP 注入位置留到 R2 集成测试。
- Middleware 生命周期、Tool/MCP、Backend、Checkpoint、Trace 和 Platform Gateway 不属于 R1。
- JWT 使用本地 HS256 测试密钥验证；生产密钥轮换和非对称算法由 Platform/P1 另行冻结。

## Docs / Runbook

- 已更新 `apps/runtime-service/README.md` 和 `apps/runtime-service/docs/README.md`，记录 R1 模块边界和测试入口；不恢复旧标准。
