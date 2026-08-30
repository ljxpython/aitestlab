## Why

R2 已让 `reference_agent` 使用 Runtime 合同构图，但模型和工具调用仍没有统一的超时、调用上限和可恢复错误边界。R3 需要建立最小公共 Middleware 可靠性栈，保证 Agent 在 Provider 卡死、工具失败或循环失控时有确定行为。

本变更归属 `apps/runtime-service`，影响 `reference_agent` 的构图和执行链，属于 B3 Governed Change；执行前已获得任务所有者明确同意。

## What Changes

- **BREAKING** 新增公共 `RuntimeConfigMiddleware`，在 Agent 生命周期中重新验证并绑定 Runtime Context。
- 新增最小 `ModelCallTimeoutMiddleware`，只包裹单次 Provider 调用，不处理 Run 总 deadline、retry 或 fallback。
- 在 `reference_agent` 中显式装配官方 `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、`ToolErrorMiddleware` 和受限 `ToolRetryMiddleware`。
- 增加 Middleware 生命周期顺序、取消传播、超时传播和工具错误分类测试。
- **BREAKING** 未知 Tool 异常、取消、interrupt、权限错误和非幂等不确定结果继续向外抛出，不转换为成功消息。

## Capabilities

### New Capabilities

- `runtime-middleware-reliability`: 公共 Middleware 的生命周期、顺序、超时、调用限制和失败语义。

### Modified Capabilities

- `runtime-agent-service-integration`: Service 组合根必须显式列出 Middleware，并保持 Runtime 配置绑定与模型/工具执行边界一致。

## Impact

- 代码：`apps/runtime-service/src/runtime_service/middlewares/`、`reference_agent/agent_server.py`。
- 测试：新增 Middleware 单元/组合测试，更新 reference service 测试。
- 依赖：只使用当前锁定 LangChain 官方 Middleware；超时实现使用 Python 标准库 `asyncio`。
- 不修改：Platform API、旧归档目录、Tool/MCP/Backend、Durable Run、Langfuse 或发布版本控制。
- 回滚：移除 Middleware 装配和新增模块即可，无数据迁移。
