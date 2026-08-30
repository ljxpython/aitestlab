## Context

R2 的 Agent Service 已完成 Runtime 解析和模型构造，但执行时没有横切可靠性控制。当前锁定的 LangChain 版本已经提供调用次数限制、Tool 错误和 Tool 重试 Middleware；项目只需要补上 Runtime Context 绑定和单次模型调用超时。

## Goals / Non-Goals

**Goals:**

- 在 `src/runtime_service/middlewares/` 提供两个独立、可测试的 Middleware。
- 让每次 Model/Tool 边界都重新使用同一套 Resolver，拒绝越权配置。
- 在 `reference_agent` 中显式固定 Middleware 顺序，并验证取消、超时和错误传播。
- 复用 LangChain 官方可靠性 Middleware，不复制 Open SWE 的业务中间件。

**Non-Goals:**

- 不创建 Middleware Builder、默认全家桶、Registry 或自动扫描机制。
- 不实现 Run 总 deadline、durable finalizer、Auth、Fallback、Model Retry、MCP、Backend 或观测 Middleware。
- 不自动重试任何业务 Tool；R3 仅验证官方组件的显式配置方式。

## Decisions

### 1. RuntimeConfigMiddleware 负责边界，不负责协调

Middleware 构造时接收本 Service 的 `RuntimePrincipal`、`RuntimePolicy`、`AgentDefaults` 和一个已明确的模型构造 callable。`abefore_agent` 先解析 Context；`awrap_model_call` 重新解析并按 resolved 配置选择基础模型或构造覆盖模型；`awrap_tool_call` 重新解析并校验 Tool 名称后才调用下一层。

Resolver 仍是纯函数，Middleware 不缓存跨 Run 的 Context、Principal、Policy 或模型。模型构造 callable 只是 Service 显式注入的依赖，不形成公共 Factory API。

### 2. ModelCallTimeoutMiddleware 只包单次调用

使用标准库 `asyncio.timeout()` 包裹 `handler(request)`，超时异常原样传播给外层 Middleware。它不捕获、不重试、不 fallback，也不改变 Run 总 deadline。超时 Middleware 放在模型调用链最内层，便于外层可靠性组件观察 `TimeoutError`。

### 3. 顺序固定在 Service 组合根

`reference_agent` 顺序固定为：

```text
RuntimeConfigMiddleware
  -> ModelCallLimitMiddleware
  -> ToolCallLimitMiddleware
  -> ToolErrorMiddleware
  -> ToolRetryMiddleware (当前无 Tool，不装配)
  -> ModelCallTimeoutMiddleware
```

列表顺序由组合根直接书写，公共层不提供 stack helper。R3 不配置 fallback/retry，避免 Provider SDK retry 与 Middleware retry 叠加。

对只有一个 Top-level Agent 且组合逻辑仍短小的 Service，默认把解析、Middleware 列表和官方
构造函数直接写在 `get_agent()` 内，不额外创建 `_build_agent()` 或同类私有 Builder。只有
动态资源分支、重复装配或独立测试需求使入口明显难以阅读时，才允许增加 Service 私有辅助函数。

### 4. 错误语义

- Context、Policy、Tool 授权错误：直接抛出 `RuntimeResolutionError`。
- 模型超时：传播 `TimeoutError`，由 Agent Server/Run Coordinator 决定终态。
- 官方 ToolError 只转换显式允许的可恢复异常；未知异常、取消和 interrupt 继续传播。
- 调用上限按官方组件语义执行，reference service 使用 run-level 上限。

## Risks / Trade-offs

- [动态 Context 覆盖会在对应 Model call 构造新模型] -> 默认配置复用构图时的基础模型；只有模型或生成参数变化才调用注入的模型构造 callable。
- [Middleware 读取 Runtime context 的 API 随 LangChain 版本变化] -> 使用当前锁定版本 `ModelRequest.runtime`，并以真实 `ainvoke(context=...)` 组合测试固定行为。
- [R3 没有 Provider fallback] -> 明确记录为后续阶段能力，超时和未知异常不伪装成成功。

## Migration Plan

无数据迁移。先将 Middleware 接入 `reference_agent`，测试通过后再由其他 Service 按同样方式显式装配。失败时移除 Middleware 列表即可回到 R2 行为。

## Open Questions

无。Fallback、Tool retry 名单和 orphaned Tool Call 恢复在后续阶段按真实需求决定。
