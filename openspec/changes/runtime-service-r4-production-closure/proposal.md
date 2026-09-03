## Why

R4 当前只有 Demo 构图和本地 fake 证据：Deep Agents 内置 Tool 没有被收缩，MCP/Backend Demo 没有统一消费 Runtime Policy，`backend_demo` 使用的进程内 `StateBackend` 也没有形成可验证的生产 Thread Workspace 闭环。本变更现在进行，是因为 R6 Durable 验证已经把“有 checkpoint”与“能力资源能安全恢复”区分开，继续把 R4 骨架当成生产能力会把未授权 Tool、跨租户文件访问和静默换 Workspace 带入后续 Platform 整合。

## What Changes

- 在 `deep_agent_demo`、`mcp_demo` 和 `backend_demo` 的组合根接入已验证 Runtime Principal、Policy、Context、Resolver 和 observability 边界；匿名生产调用继续 fail-closed，fake adapter 只保留在显式测试配置。
- 用锁定的 `deepagents==0.7.8` 官方 `FilesystemMiddleware`/`HarnessProfile` 能力显式收缩 Deep Agent 内置 Tool，关闭不需要的 `execute`、`task` 和写文件能力，并为 Subagent 声明独立的最小 Tool/Skill/Permission 集合。
- 增加真实 `create_deep_agent`/`create_agent` graph 失败测试，覆盖模型可见 Tool、伪造 Tool Call、Policy 禁止、Skill 写入、Subagent 缩权和 MCP 名称/加载失败。
- 将 `backend_demo` 改为生产可解释的 Thread Workspace 方案：默认使用 Agent Server 提供的 durable checkpointer + Thread-scoped `StateBackend`；不把宿主机 `FilesystemBackend` 伪装成 Web/API 生产存储。
- 为需要真实文件/代码执行的 Workspace 明确保留 Sandbox Provider 接口边界；没有真实隔离 Provider、持久化绑定、重连、清理和失败分类证据时，生产 Workspace 不标记完成，也不自动 fallback 到空目录。
- 增加同 Thread 跨 Turn、不同 Thread 隔离、Worker 重建、Backend 不可达和资源清理的分层测试/验证；外部 Agent Server、PostgreSQL、Redis 或 Sandbox 不可用时记录 `blocked`/`not-executed`，不把 skip 算通过。
- 更新 19、20、28、31 号文档和本变更 `verification.md`，记录实现位置、测试、证据等级、部署前置条件和未覆盖边界。

## Capabilities

### New Capabilities

- None. R4 能力已经存在于现有 capability specs，本变更收口其生产要求，不创建重复 Registry 或 Workspace capability。

### Modified Capabilities

- `runtime-agent-capabilities`: 要求 R4 Service 的 Tool/MCP/Deep Agent/Backend 能力统一经过 Runtime Policy，且 Thread Workspace 的持久化、隔离、重连和失败语义可验证。
- `runtime-agent-service-integration`: 要求所有 R4 Service 组合根消费 Runtime Context/Auth/Resolver，并在生产入口禁止匿名 fake adapter；Deep Agent 的 Backend、内置 Tool 和 Subagent 必须显式装配。
- `runtime-agent-tool-governance`: 要求 Deep Agents 内置 Tool 与业务/MCP Tool 一样具有模型可见和执行前的收缩路径，禁止通过默认内置 Tool 绕过 Policy。

## Impact

- **Owning locus**：`apps/runtime-service`；affected chain 为 Agent Server auth -> Service `get_agent()` -> Runtime Middleware -> Deep Agents/MCP Tool -> Checkpointer/Workspace Backend。
- **Execution band**：B3 Governed；涉及认证、权限、跨租户资源隔离、持久化和 Worker 恢复。
- **代码**：`src/runtime_service/demo/{deep_agent_demo,mcp_demo,backend_demo}/`、必要的 Demo 私有 backend/helper、R4 测试和部署配置。
- **依赖**：使用锁定的 `deepagents==0.7.8`、现有 LangGraph Agent Server/checkpointer 和已安装 MCP adapter；不新增公共 Registry、FilesystemBackend Web 直通或第二套 Run Coordinator。
- **生产边界**：`FilesystemBackend` 只允许受控本地开发；生产 Thread 文件状态由 durable checkpointer 承载，真实 Shell/Repo 工作区必须有独立 Sandbox Provider 和明确资源绑定。
- **兼容/回滚**：R4 Demo 的构图参数和 graph ID 保持不变；回滚只移除新增 R4 Service 接线和测试，不做数据迁移。若生产 Workspace 前置条件不足，保留明确失败，不回退到共享宿主机目录。
- **Loaded standards/design**：根 `AGENTS.md`、`docs/standards/01-ai-execution-system.md`、19/20/23/24/25 号 Runtime knowledge 文档，以及 LangChain `create_deep_agent`、`FilesystemMiddleware`、`HarnessProfile`、`StateBackend` API reference。
