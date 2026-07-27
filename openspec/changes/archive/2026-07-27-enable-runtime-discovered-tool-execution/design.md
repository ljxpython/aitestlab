## Context

现有 `RuntimeRequestMiddleware` 已统一解析 `RuntimeContext`、动态模型、system prompt 和工具 allowlist。上一轮工具治理修复将 `request.tools` 作为可执行基线，并过滤 resolver 返回的未注册工具，从而避免模型生成 ToolNode 无法执行的调用。

这个防错同时切断了确实需要请求期发现的工具：`research_demo` 的 Tavily MCP、`test_case_agent` / `test_case_agent_v2` 的知识 MCP，以及通过公共 registry 请求期加载的 MCP。LangChain 当前官方模式允许 middleware 在 `wrap_model_call` 暴露动态工具，并在 `wrap_tool_call` 为调用绑定真实 `BaseTool`。本地 `langchain 1.3.14` 的 `ToolCallRequest.override(tool=...)`、`AgentMiddleware.wrap_tool_call` 和 `awrap_tool_call` 已具备该能力。

约束如下：

- graph 继续静态导出，不因工具发现重建 graph；
- 现有 `RuntimeContext.enable_tools/tools`、Agent defaults 和服务 resolver 继续作为授权与选择真源；
- middleware 实例会被多个 run 并发共享，不能把某次 run 的工具对象保存在实例可变状态中；
- MCP 可能在模型调用和工具调用之间失效或改变，执行阶段必须重新验证；
- 当前工作区已有未提交的工具治理改动，本次实现必须在其上增量修改，不能回退。

## Goals / Non-Goals

**Goals:**

- 让通过现有 resolver 合法发现的动态工具同时具备模型可见和真实执行路径。
- 静态注册工具、DeepAgents 内置工具和同名工具冲突时保持确定行为。
- sync/async 路径采用同一授权和匹配语义。
- 通过无外部 secret 的最小 Agent 调用证明工具从模型调用走到真实 ToolMessage。

**Non-Goals:**

- 不引入 `langgraph-bigtool`、embedding 或语义工具检索。
- 不新增通用插件市场、工具持久化 registry 或跨 run 工具对象缓存。
- 不迁移到 graph factory，也不改变 `RuntimeContext` 或 `platform-api` 契约。
- 不修改 MCP server 的认证、session、传输或 fail-soft 策略。
- 不处理 CORS、生产 graph 拆分、运行预算和领域 benchmark；这些作为独立后续 change。

## Decisions

### 1. 由共享 RuntimeRequestMiddleware 同时负责动态工具可见与执行绑定

`RuntimeRequestMiddleware` 在 model call 阶段合并：

1. graph 创建阶段已注册的工具；
2. required resolver 返回的工具；
3. 经 `enable_tools/tools` 和 Agent allowlist 选择的 public resolver 工具。

合并仍按标准化名称去重，已注册工具排在前面，因此同名冲突时静态已注册实现优先。resolver 返回的未注册工具只有在同一 middleware 安装了 tool-call hook 后才允许进入模型请求。

在 tool call 阶段：

- `request.tool` 已存在时直接交给后续 handler，不重新绑定静态工具；
- `request.tool` 不存在时，使用 `request.runtime.context` 重新解析 settings 和本次获准动态工具；
- 仅当标准化工具名精确匹配时使用 `request.override(tool=resolved_tool)` 交给 handler；
- 未匹配时保持原请求交给 LangChain 的未知工具处理，不选择其他工具或扩大 allowlist。

替代方案是在各业务 graph 注册通用 `call_mcp_tool(name, args)` 代理。拒绝：它丢失原始工具 schema，使模型必须手工拼工具名和参数，并在每个业务模块重复路由逻辑。

替代方案是为每个已知 MCP 工具写静态 wrapper。只适用于工具名称和 schema 稳定的单个服务，无法覆盖公共 MCP registry 和 Tavily 远端工具发现，因此不作为共享方案。

### 2. model call 与 tool call 重新解析，不保存跨调用可变工具表

middleware 不在 `self`、全局变量或 LangGraph state 中保存动态 `BaseTool` 对象。tool call 使用相同 runtime context 和 resolver 再次解析获准工具。

这样会增加一次 MCP 工具目录解析，但避免：

- 并发 run 之间泄漏租户或项目工具；
- 把不可序列化工具对象写入 checkpoint；
- 缓存过期后继续执行已撤销工具；
- 以 tool name 之外的弱标识跨请求复用凭证。

如果后续观测证明目录解析成为延迟瓶颈，应在具体 MCP loader 内增加有界、按授权维度隔离的缓存，而不是在通用 middleware 中引入隐式全局缓存。

### 3. 复用现有 required/public resolver，不新增第二套动态工具接口

现有 graph 已通过 sync/async required/public resolver 表达服务必备工具和调用方允许的公共工具。实现将提取“本次获准 runtime tools”的共享 helper，同时供 model-call 合并和 tool-call 绑定使用。

同步调用遇到仅配置 async resolver 时继续抛出当前明确的 `TypeError`；异步调用优先使用 async resolver。不会静默跨事件循环执行异步 resolver。

替代方案是新增 `dynamic_tool_resolver` 参数。拒绝：现有 resolver 已承载同一事实，再加一套接口只会要求每个 graph 重复声明工具来源。

### 4. 失败保持 fail-closed，并保留下游 middleware 顺序

动态工具在执行阶段不再获准、MCP 不可用或名称不匹配时，middleware 不绑定工具，让 LangChain 现有未知工具路径生成错误结果。它不得回退到 registry 同名之外的工具，也不得绕过后续 `ToolArgumentAliasMiddleware`、`ToolRuntimeContextSanitizerMiddleware` 等业务 middleware。

`RuntimeRequestMiddleware` 继续位于业务 middleware 列表前部。其 `wrap_tool_call` 先提供真实工具对象，后续 middleware 再处理参数和运行时上下文。

## Risks / Trade-offs

- [每次动态工具调用会再次请求 MCP 工具目录，增加延迟] -> 首批保持无共享状态；用测试和后续 trace 判断是否需要在服务 loader 内增加隔离缓存。
- [MCP 目录在模型调用后发生变化] -> 执行阶段重新解析并 fail-closed，宁可返回未知工具也不执行错误实现。
- [静态工具和动态工具同名] -> 静态注册工具优先，动态 resolver 不覆盖已注册执行基线。
- [下游 middleware 依赖 tool 对象] -> Runtime middleware 保持在列表前部并在调用 handler 前完成 `request.override(tool=...)`。
- [外部 MCP 无法在 CI 稳定验证] -> 使用本地 fake resolver 和 scripted model 验证完整 Agent 链；真实 MCP 连接列为未覆盖边界。

## Migration Plan

1. 先增加失败测试，覆盖动态工具模型可见、sync/async 执行绑定、未授权和同名冲突。
2. 增量扩展 `RuntimeRequestMiddleware`，不改变 graph 配置和 resolver 签名。
3. 运行 middleware、research、test-case、SQL 和 harness 相关测试，再运行 runtime-service 全量测试与 compileall。
4. 如回归出现不可接受行为，回退 tool-call hook 和动态工具合并，恢复“隐藏全部未注册工具”的安全状态；无数据迁移或配置回滚。

## Open Questions

- 无实施前阻塞问题。动态工具目录缓存、生产 MCP live 验证和工具级审计属于后续优化，不阻塞本次本地执行闭环。
