## Context

R4 是 Runtime Service 的能力接入阶段。LangChain/Deep Agents 已提供 Tool、MCP、StateBackend、Skills 和 SubAgent 原语；本项目只需在 Service 组合根显式选择和限制它们。当前没有生产 Tool、MCP Server 或 Sandbox，因此示例优先使用纯 Python Tool、本地 stdio fake MCP 和 StateBackend。

## Goals / Non-Goals

**Goals:**

- `reference_agent` 展示一个只读 Tool 的声明、Context 读取和 Runtime Policy 限制。
- `deep_agent_demo` 展示 `create_deep_agent`、StateBackend、Bundled Skill 和显式缩权 Subagent。
- `mcp_demo` 展示 MCP tools 在构图前加载、名称冲突立即失败和显式 allowlist。
- `backend_demo` 展示 thread-scoped in-memory Backend 的隔离、失败关闭和资源清理。
- 每个 Demo 都保持 `get_agent(config) -> Pregel` 和 `graphs/` 稳定导出。

**Non-Goals:**

- 不创建公共 Tool Registry、Capability Registry、Plugin 或自动扫描。
- 不接入真实 Sandbox、外部 MCP 凭据、Platform API、数据库、审批产品或 Durable Run。
- 不把 Deep Agents 默认工具全部暴露给普通 `create_agent`。

## Decisions

### 1. Tool 显式装配

Service 在 `tools.py` 定义并在 `agent_server.py` 直接传入 `tools=[...]`。Runtime Policy 同时约束模型可见 Tool 和执行边界；未知名称直接失败。Tool 自身优先使用 `@tool` schema 校验，不用公共包装器。

### 2. MCP 只在 Service 内部加载

`mcp_demo/loader.py` 使用官方 `MultiServerMCPClient` 通过 stdio 启动 Service 私有 `fake_server.py`，调用 `await client.get_tools()` 获取 LangChain Tool；加载结果在组合根中显式过滤。最终名称冲突在构图前抛出 `RuntimeResolutionError`；凭据只从环境读取，测试使用本地 fake server，不进入 checkpoint。客户端保持默认 stateless 行为，由适配器管理每次 Tool 调用的 Session 生命周期。

### 3. Backend 和 Skills 使用 Deep Agents 原语

`deep_agent_demo` 使用 `StateBackend()`，文件状态由 LangGraph thread/checkpoint 承载；Skills 通过 `skills=[...]` 指向 Service 内的只读目录。Subagent 使用声明式 `SubAgent`，工具集合和模型显式缩权，不继承父级额外能力。

### 4. Backend Demo 资源边界

`backend_demo` 只使用内存 Backend 工厂，按 `thread_id` 在 `get_agent` 中创建或复用当前线程资源；无 thread 时 fail-closed。该工厂是 Demo 私有函数，不上升为公共 Backend Factory。

## Risks / Trade-offs

- [Deep Agent 默认带文件工具和 task 工具] -> Demo README 明确列出暴露工具；普通 Agent 继续使用 `create_agent`。
- [MCP handshake 依赖外部进程] -> 单元测试使用本地 stdio fake server；真实远程 MCP smoke test 单独标记。
- [StateBackend 依赖 checkpoint 才能跨 Run 保留] -> R4 只验证同一 thread 的行为，Durable 恢复留给 R6。
- [内存 Backend 不适合多进程] -> 仅作为本地契约 Demo，生产 Backend 需在 R6/P1 另行评审。

## Migration Plan

无迁移。新增 Demo 不改变既有 `reference_agent` 的生产 graph 注册；`langgraph.demo.json` 增加学习用 graph。失败时可单独移除 Demo。

## Open Questions

真实 Sandbox、MCP 凭据租约和审批 Tool 的生产实现留到 R6/P1，不在本变更猜测。
