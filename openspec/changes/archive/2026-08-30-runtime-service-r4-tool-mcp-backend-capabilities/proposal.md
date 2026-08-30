## Why

R3 已冻结 Runtime Middleware 的执行边界，但当前 Runtime Service 仍没有可复制的能力接入范例。R4 需要用最小、可测试的 Service 示例证明只读 Tool、MCP、Thread Backend、Skills 和 Subagent 可以在组合根显式装配，并且不会引入自动扫描或公共 Registry。

本变更归属 `apps/runtime-service`，覆盖 R4 的第一条能力链路，属于 B3 Governed Change；不改 Platform API，不迁移旧服务。

## What Changes

- **BREAKING** `reference_agent` 增加一个显式只读 Tool，并由 Runtime Policy 控制可见与执行。
- 新增 `deep_agent_demo`，展示 `create_deep_agent`、StateBackend、Bundled Skill 和一个缩权 Subagent。
- 新增 `mcp_demo`，使用本地 fake MCP tool，显式检查名称冲突和 allowlist。
- 新增 `backend_demo`，使用 in-memory Backend 证明 Thread 资源隔离和失败关闭。
- 新增对应 Graph 导出、README、fake model 测试和能力边界测试。

## Capabilities

### New Capabilities

- `runtime-agent-capabilities`: Service 私有 Tool、MCP、Backend、Workspace、Skills 和 Subagent 的显式接入规范与最小示例。

### Modified Capabilities

- `runtime-agent-service-integration`: 允许 Service 在组合根内显式装配能力依赖，并保持 Runtime Middleware 与工具策略一致。

## Impact

- 代码：`apps/runtime-service/src/runtime_service/services/`、`src/runtime_service/graphs/`、`langgraph.demo.json`。
- 测试：新增能力 Demo 测试和跨 Thread 隔离测试。
- 依赖：复用已锁定 `deepagents`、`langchain-mcp-adapters`，不添加依赖。
- 不修改：Platform API、旧归档、公共 Tool Registry、自动插件发现、真实 Sandbox 或外部 MCP 凭据。
- 回滚：移除新增 Demo 和 reference Tool 即可，不涉及数据迁移。
