## Why

`RuntimeRequestMiddleware` 当前会隐藏请求期 resolver 返回但未在 graph 创建阶段注册的工具，避免模型调用 ToolNode 无法执行的工具；这保证了失败安全，却使 `research_demo` 的 Tavily MCP、测试用例知识 MCP 和部分 public MCP 能力实际不可达。现有 `runtime-agent-tool-governance` 已要求运行时发现工具同时具备模型可见与工具调用执行路径，现在需要补齐该执行闭环。

## What Changes

- 扩展共享 `RuntimeRequestMiddleware`，让经过现有 runtime context、Agent allowlist 和 resolver 校验的运行时发现工具可以进入模型请求。
- 在 `wrap_tool_call` / `awrap_tool_call` 阶段重新解析并按工具名绑定对应的运行时工具实现，使动态工具调用进入真实 handler，而不是停在模型可见层。
- 对不存在、未获允许、名称冲突或同步/异步路径不匹配的动态工具保持 fail-closed，不回退到任意 registry 工具。
- 保持 graph 静态导出、`RuntimeContext` 公共契约、现有静态工具和 DeepAgents 内置工具行为不变。
- 增加 middleware sync/async 单元测试与最小 Agent 工具调用链测试，证明动态工具最终产生真实工具结果。
- 不引入 `langgraph-bigtool`、语义工具检索、通用插件市场、graph factory、生产 MCP secret 或外部副作用测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `runtime-agent-tool-governance`：细化运行时发现工具在模型调用与工具调用阶段的绑定、授权一致性和 fail-closed 行为。

## Impact

- **Owning locus**：`apps/runtime-service/runtime_service`
- **Affected chain**：业务 graph -> `RuntimeRequestMiddleware.wrap_model_call` -> LangChain/DeepAgents ToolNode -> `RuntimeRequestMiddleware.wrap_tool_call` -> runtime-discovered MCP tool
- **Band**：B2 Chain，行为与验收标准需要持久对齐，但不改变公开 runtime contract、鉴权、数据所有权或跨服务职责。
- **Standards loaded**：
  - `AGENTS.md`
  - `docs/standards/01-ai-execution-system.md`
  - `apps/runtime-service/runtime_service/docs/standards/02-architecture.md`
  - `apps/runtime-service/runtime_service/docs/standards/03-agent-development-playbook.md`
  - `apps/runtime-service/runtime_service/docs/standards/08-middleware-development-playbook.md`
  - `openspec/specs/runtime-agent-tool-governance/spec.md`
- **Affected code**：共享 runtime middleware、相关 middleware 测试、动态 MCP graph/loader 的最短链测试；不修改 `platform-api` 转发契约。
- **Compatibility**：静态工具和现有 allowlist 语义保持兼容；此前被隐藏的合规动态工具将恢复可用。缺少执行路径的工具仍保持隐藏或拒绝。
- **Rollback**：可回退动态工具的 `wrap_tool_call` 绑定及其模型可见逻辑，恢复当前“隐藏所有未注册工具”的安全行为，不需要数据迁移。
