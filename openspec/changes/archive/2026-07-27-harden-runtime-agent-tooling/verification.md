# Verification

## Pre-apply review

- Decision: Approved
- Owner approval or waiver: Owner approved implementation in this conversation.
- Scope: runtime-service 工具保留、公共工具 allowlist、动态工具执行约束、服务模块边界，以及 platform-api runtime gateway 契约验证。

## Evidence

- `cd apps/runtime-service && rtk uv run pytest runtime_service/tests`: 178 passed.
- `cd apps/runtime-service && rtk uv run python -m compileall runtime_service`: passed.
- `cd apps/platform-api && rtk uv run python -m unittest tests.test_runtime_gateway_runtime_contract`: 3 passed.
- `rtk graphify update .`: completed after code changes.

## Results

- `RuntimeRequestMiddleware` 以 `request.tools` 为可执行工具基线，保留业务、middleware 和 DeepAgents 已注册工具；public optional 工具仍按 allowlist 筛选。
- 运行时 resolver 返回但未在 graph 注册的工具不再对模型可见，避免 ToolNode 无法执行的调用。
- `resolve_requested_tools(None)` 与空列表均不再默认选择 builtin 或 MCP 工具。
- platform-api runtime gateway 仍只归一化 `enable_tools` 与 `tools` 到 context，并保持受信任项目范围注入。
- 开发规范已说明兼容性：调用方必须显式选择 public 工具，或由 Agent 在 `public_tool_names` 声明默认 allowlist。

## Uncovered boundaries

- 生产 MCP server 的真实连接和外部工具副作用不在本地自动化测试范围内；运行时发现的 MCP 工具在具备预注册工具或稳定代理前不会对模型公开。
- HITL/checkpointer 部署持久化策略不属于本次工具管线修复，需在实际运行环境单独确认。

## Disposition

- Accepted: local and shortest-chain evidence passed.
