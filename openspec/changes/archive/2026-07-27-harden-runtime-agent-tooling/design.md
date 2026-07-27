## Context

`RuntimeRequestMiddleware` 在 `wrap_model_call` 中以运行时解析结果替换 `request.tools`。这把 LangChain/LangGraph 在图创建阶段登记的执行工具与模型可见工具混为一层：普通 Agent 显式注册的工具、middleware 工具和 DeepAgents 文件/待办/子任务工具都可能丢失；运行时 resolver 临时返回的工具也可能没有对应的 ToolNode 执行路径。

`platform-api` 已负责将调用方的模型、提示词、采样参数和工具选择归一化到 runtime `context`，并注入受信任项目范围。该控制面边界应保持不变。

## Goals / Non-Goals

**Goals:**

- 保证图创建阶段注册的工具在 runtime middleware 生效后仍可执行。
- 让公共 optional 工具采用明确 allowlist，禁止隐式全量暴露。
- 让运行时发现工具只有在模型调用和工具调用均具备执行路径时才暴露。
- 让每个业务 Agent 自包含在 `runtime_service/services/<agent>/`，共享能力只保留在 runtime、tools 和 middlewares。
- 用最短的 platform-api 到 runtime-service 契约测试证明调用字段和项目范围不变。

**Non-Goals:**

- 不重写全部现有 Agent，不迁移 `agents/` 演示目录。
- 不创建通用 Agent 插件框架、工具市场或新的权限服务。
- 不把工具解析、模型调用或图执行迁入 `platform-api`。
- 不改变用户身份、项目授权或持久化/checkpointer 策略；HITL 的运行环境配置仅作为独立后续项确认。

## Decisions

### 1. 以图注册工具为执行基线，runtime middleware 只叠加公共工具

middleware 必须从 `request.tools` 开始构造模型可见工具，再追加 required 工具和经过 allowlist 解析的 public 工具，并按名称去重。图注册工具是可执行的基线，不能因 `enable_tools` 或请求工具选择而被清空。

`enable_tools` 仅控制 public optional 工具；它不移除业务 Agent 的必备工具、middleware 工具或 DeepAgents 内置工具。

替代方案是由 middleware 重建所有工具列表。拒绝：它需要复制各图的注册事实，已经造成覆盖缺陷，且 DeepAgents 内置工具无法安全枚举。

### 2. 公共工具默认采用 Agent 级 allowlist

当 context 未提供 `tools` 时，使用 `AgentDefaults.public_tool_names`；当其为空时，公共工具集合为空。调用方显式传入空列表同样不公开 optional 工具。未知名称必须在 runtime-service 返回清晰错误，不能降级为全量公开。

`platform-api` 保持原有归一化：它只传递调用方声明的 `tools` 到 context，不推导或扩展允许工具。

替代方案是 `enable_tools=true` 时公开 registry 全量工具。拒绝：它绕开 Agent 的最小权限定义，并将新增 registry 工具自动扩大到全部 Agent。

### 3. 动态工具必须同时满足可见与可执行

静态可枚举工具在 graph 创建时通过 `tools=` 或 `middleware.tools` 注册。真正运行时发现的 MCP/远程工具只允许通过一个稳定、预注册的代理工具暴露，该代理在工具调用阶段根据已验证的 context 解析并执行目标工具；若当前业务不需要该能力，则不注入动态工具。

在设计评审后，首个实施批次只修复已注册工具保留和 allowlist 默认值。现有动态 resolver 若无法证明 ToolNode 可执行，将不再在 `wrap_model_call` 中直接暴露，直到对应的稳定代理与 `wrap_tool_call` 一并实现。

替代方案是在 `wrap_model_call` 临时追加工具。拒绝：LangChain 要求 Agent 在执行前已知该工具，模型可见不等于 ToolNode 可执行。

### 4. 业务 Agent 保持独立，公共层保持窄

服务 graph、prompt、Agent 私有工具和特定 runtime defaults 均放入 `runtime_service/services/<agent>/`。只有跨多个 Agent 的 context 解析、公共工具注册和 middleware 才进入共享目录。新 Agent 不必继承基类或注册到通用工厂，只需导出其 graph 并显式声明默认公开工具。

替代方案是以统一 Agent 框架管理所有 graph。拒绝：当前规模下会把业务差异塞入配置和 hook，增加维护成本而不解决工具执行契约。

## Risks / Trade-offs

- [调用方依赖空 `tools` 的全量公开行为] -> 通过服务默认 `public_tool_names` 或显式请求名称迁移；回归测试覆盖空值语义。
- [保留 `request.tools` 可能使同名工具冲突] -> 按当前名称去重规则固定优先顺序，并在测试中覆盖重复名称。
- [动态 MCP 功能暂时不暴露] -> 仅影响原本不可可靠执行的路径；稳定代理方案落地前不向模型声明该能力。
- [服务模块独立后存在少量重复] -> 只抽取已有跨 Agent 使用的 runtime/tools/middleware，单 Agent 代码保持本地，避免过度抽象。
