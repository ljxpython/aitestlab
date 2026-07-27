## Why

`RuntimeRequestMiddleware` 当前会覆盖图在创建时注册的工具，导致普通 Agent 工具和 DeepAgents 内置工具可能对模型或 ToolNode 不可用；同时，仅启用工具但未提供 allowlist 时会暴露全部 builtin 与 MCP 工具。该行为破坏工具执行链路，也扩大了生产权限边界。

现在需要以最小改动明确工具注册、运行时筛选和动态工具执行语义，并把业务 Agent 收敛到独立的 `runtime_service/services/<agent>/` 模块中。

## What Changes

- 保留 `create_agent`、middleware 与 DeepAgents 在图创建时已注册的内部工具；运行时策略只筛选或追加明确允许的公共工具。
- 将 `enable_tools=true` 且 `tools` 缺省或为空的默认行为改为仅使用 Agent 声明的 `public_tool_names`；未声明时不暴露公共 optional 工具或 MCP server。**BREAKING**
- 为运行时发现的工具建立可执行约束：工具必须预注册，或通过同时覆盖模型调用与工具调用的稳定代理执行；禁止仅在模型调用阶段临时注入不可执行工具。
- 明确业务 Agent 以 `runtime_service/services/<agent>/` 为独立模块；公共 middleware、工具注册和 runtime context 保持为共享层，`agents/` 仅承载样例或演示。
- 保持 `platform-api` 作为控制面：它继续将调用方可配置的运行字段归一化到 runtime `context`，不承担工具解析或 Agent 执行逻辑。

## Capabilities

### New Capabilities

- `runtime-agent-tool-governance`: 规范图注册工具、公共工具 allowlist、动态工具执行和 DeepAgents 内置工具的保留语义。
- `runtime-agent-service-boundary`: 规范业务 Agent、共享运行时能力和 `platform-api` runtime gateway 的模块职责边界。

### Modified Capabilities

- 无。

## Impact

- 所有者 locus：`apps/runtime-service/runtime_service`；关联链路为 `apps/platform-api` runtime gateway -> runtime context -> runtime middleware -> service graph tools。
- 执行等级：B3 Governed。涉及运行时工具暴露与权限默认语义，以及跨服务 runtime contract 的验证。
- 已加载标准：根 `AGENTS.md`、`docs/standards/01-ai-execution-system.md`、runtime-service 的架构/Agent/middleware/服务模块化标准，以及 platform-api runtime gateway 与开发手册。
- 受影响实现包括 `middlewares/runtime_request.py`、`tools/registry.py`、runtime request resolver、各服务 graph 和对应的 runtime-service/platform-api 契约测试。
- 不引入新的依赖、通用插件框架或 Agent 重写；现有调用方若依赖“未指定 `tools` 即获得全部公共工具”的行为，必须改为显式 allowlist 或 Agent 默认声明。
- 回滚方式：恢复原有工具筛选默认值即可恢复旧暴露范围；不涉及数据迁移。
