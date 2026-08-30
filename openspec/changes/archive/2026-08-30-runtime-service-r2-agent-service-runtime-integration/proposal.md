## Why

R1 已经提供不可变 Runtime 合同、解析器和模型构造，但 R0 的参考 Agent 仍固定使用 fake model，公共 Runtime 没有进入真实的 Service 组合根。现在需要用一个最小纵向闭环证明新目录规范可用，避免后续 Middleware 和能力接入建立在未使用的合同之上。

本变更归属 `apps/runtime-service`，执行链为 `langgraph.json -> graphs/reference_agent.py -> services/reference_agent/agent_server.py`，属于 B2 Runtime 单服务链路。

## What Changes

- **BREAKING** 将 `reference_agent` 的组合根改为显式解析 Runtime Context、构造 `ResolvedRuntimeConfig` 并通过 Modeling 创建模型。
- **BREAKING** `reference_agent` 使用 `RuntimeContext` 作为 `create_agent(..., context_schema=...)` 的运行时 Context 边界；未授权模型或工具直接失败。
- 为本地调试提供不依赖 Platform API 的静态 Principal、Policy 和 AgentDefaults；真实 Provider 仍只从环境变量读取。
- 保留 fake model 的确定性测试，并增加对组合根解析结果和 Context 传递的覆盖。
- `workflow_demo` 继续作为静态 `StateGraph` 示例，不强行接入不需要的模型解析链路。

## Capabilities

### New Capabilities

- `runtime-agent-service-integration`: 定义 Agent Service 组合根如何显式消费 Runtime 合同并导出可运行 Graph。

### Modified Capabilities

- `runtime-agent-service-boundary`: 补充 Service 组合根必须在构图前完成 Runtime 合同解析，并将已决议模型和 Context Schema 传入官方 Agent 构造函数。

## Impact

- 代码：`apps/runtime-service/src/runtime_service/services/reference_agent/agent_server.py`，必要时新增服务私有工具或测试辅助函数。
- 测试：`apps/runtime-service/tests/services/reference_agent/` 及现有 R0/R1 测试。
- 运行时：Provider 凭据继续由 `runtime_service.runtime.modeling` 从环境读取；不修改 `platform-api`、旧归档目录或公共 API 路由。
- 回滚：删除本变更文件并恢复 R0 参考组合根即可；没有数据迁移、旧 Graph 兼容或持久化变更。
