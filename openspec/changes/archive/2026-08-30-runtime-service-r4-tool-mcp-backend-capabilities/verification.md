# R4 Verification

## Pre-Apply Review

- 变更等级：B3，涉及 Agent Service 能力边界、Tool Policy、MCP 装配和 Backend 资源隔离。
- 评审结论：任务所有者已明确同意进入 R4；实现仅位于新 Runtime 包，不兼容旧代码，也不修改 Platform API。
- 简化决策：每个 Service 在 `get_agent()` 中直接调用官方 `create_agent`/`create_deep_agent`；没有公共
  `build_agent`、Builder、Factory 或 Registry。MCP loader 和 Backend 逻辑保持 Service 私有。

## Checks

| 检查 | 结果 |
| --- | --- |
| `uv run pytest tests -q` | 44 passed, 1 skipped |
| `RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -m e2e -q` | 1 passed（真实 DeepSeek 中转模型） |
| `uv run python -m compileall -q src` | passed |
| `uv lock --check` | passed |
| `git diff --check` | passed |
| `openspec validate runtime-service-r4-tool-mcp-backend-capabilities --strict --no-interactive` | passed |
| `graphify update .` | passed；32468 nodes / 66075 edges；HTML 因超过 5000 节点上限跳过 |

## Covered Boundaries

- `reference_agent`：只读 Tool 的模型可见过滤、执行前 allowlist 和 Tool schema。
- `deep_agent_demo`：`StateBackend`、Bundled Skill、显式 `tools=[]` 的缩权 Subagent。
- `backend_demo`：每次 `get_agent()` 独立构图、Backend 初始化失败直接传播，不静默 fallback。
- `mcp_demo`：Service 私有 stdio fake MCP、`MultiServerMCPClient.get_tools()`、显式 allowlist、名称冲突在构图前失败。
- 所有 Demo：标准 `get_agent(config) -> Pregel`、Graph 导出和无外部服务 fake model 装配。

## Residual Risk

- R4 使用 `StateBackend` 和本地 stdio fake MCP；真实 Sandbox、远程 MCP 凭据租约和 Durable 恢复留到 R6/P1。
- Fake model 只验证构图和确定性响应，不模拟真实模型 Tool Call；真实 Tool Call E2E 需要 Provider 支持后补充。
- `StateBackend` 的跨 Run 持久化依赖 LangGraph Checkpoint，R6 才做 PostgreSQL/Worker 重启验证。

## Docs / Runbook Impact

- 更新 `apps/runtime-service/README.md`、`docs/README.md` 和 28 号开发计划。
- 新增三个 Demo README 和 `langgraph.demo.json` 注册项。
- 记录 Service 组合逻辑直接内联 `get_agent()` 的简化规范。
