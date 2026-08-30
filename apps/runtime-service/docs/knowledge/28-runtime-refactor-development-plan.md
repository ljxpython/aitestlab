# Runtime Service 绿色重构开发计划

> 文档类型：Draft
>
> 状态：R0、R1、R2、R3、R4 已实施并归档；下一阶段为 R5
>
> 适用范围：`apps/runtime-service`，以及后续最短的 `platform-api` 整合链路
>
> 关联文档：`10-production-agent-platform-roadmap.md`、`13-runtime-service-target-code-layout.md`、
> `14-runtime-contracts-and-resolution-design.md`、`15-runtime-middleware-lifecycle-and-failure-semantics.md`、
> `27-platform-runtime-integration-phased-design.md`

## 1. 总原则

本次是绿色开发，不是旧系统迁移。开发者按照本计划在新目标目录中重新实现，旧代码和旧数据
不作为输入。

硬规则：

- 新 Runtime 只写入 `apps/runtime-service/src/runtime_service/`；
- 旧 `apps/runtime-service/runtime_service/` 包已归档到 `archive/apps/runtime-service/runtime_service/`，不能导入、复制或适配；
- 不支持 `platform_runtime`、`enable_tools`、旧 Graph ID、旧 Assistant 字段或旧 HTTP 路由；
- 不做双读、双写、兼容 Adapter、旧数据迁移或旧 Thread 恢复；
- 不先创建 `engine/`、`builder/`、`factory/`、`registry/`、`plugin/`、`orchestrator/` 等公共层；
- 每个 Agent Service 直接暴露 `async def get_agent(config: RunnableConfig) -> Pregel`；
- 只使用 LangGraph Agent Server 标准 Graph/Thread/Run/Stream 接口，不新增 Runtime Custom Route；
- 每个阶段完成最小验证后才能进入下一阶段。

## 2. 开发阶段总览

```text
R0 新包和启动基线
  -> R1 Runtime Contracts / Auth / Resolver / Modeling
  -> R2 Agent Service 组合根和第一个 reference_agent
  -> R3 Middleware 可靠性栈
  -> R4 Tool / MCP / Backend / Workspace / Skills / Subagents
  -> R5 Trace / Logs / Metrics / Run Event 投影
  -> R6 Durable Run 真实部署验证
  -> P1 Platform 控制面和配置快照整合
```

当前已完成 R0、R1、R2、R3 和 R4，并通过各阶段门槛；当前阶段为 R5 可观测与事件投影准备。任何后续阶段的代码、Demo
或 Platform 整合不得提前实施；Demo 按本计划第 13 节随所属阶段进入。

R0～R6 完成前不改 Platform 业务代码。P1 不是 Runtime 的前置条件，而是 Runtime 已经可以
独立运行后的第二条工作流。

### 2.1 阶段与设计文档映射

开始某个阶段前，先阅读该阶段的必读文档；只有实现触及对应边界时才阅读辅助文档。本文档
负责阶段顺序、交付物和门槛，具体设计文档负责各自领域的契约与实现约束。

| 阶段 | 必读设计文档 | 辅助参考 | 阅读重点 |
| --- | --- | --- | --- |
| R0 | [13 目标目录](./13-runtime-service-target-code-layout.md)、[24 启停设计](./24-package-langgraph-startup-shutdown-design.md)、[12 本地调试](./12-runtime-context-and-local-debug-architecture.md) | [11 Service 目录规范](./11-agent-service-directory-architecture.md)、[10 总路线](./10-production-agent-platform-roadmap.md) | 新包边界、Graph 导出、配置文件、启动和本地调试 |
| R1 | [14 Contracts 与 Resolver](./14-runtime-contracts-and-resolution-design.md) | [22 Platform/Runtime 契约](./22-platform-runtime-contract-design.md)、[26 模型配置边界](./26-runtime-custom-routes-and-model-config-design.md) | Context、Token、解析、模型选择和 fail-closed |
| R2 | [11 Service 目录规范](./11-agent-service-directory-architecture.md)、[13 目标目录](./13-runtime-service-target-code-layout.md) | [12 本地调试](./12-runtime-context-and-local-debug-architecture.md)、[24 启停设计](./24-package-langgraph-startup-shutdown-design.md)、[14 Contracts](./14-runtime-contracts-and-resolution-design.md) | `get_agent()` 组合根、`create_agent`、`StateGraph` 和 Demo 模板 |
| R3 | [15 Middleware 生命周期](./15-runtime-middleware-lifecycle-and-failure-semantics.md) | [14 Contracts](./14-runtime-contracts-and-resolution-design.md)、[16 可观测设计](./16-runtime-observability-and-langfuse-design.md)、[25 测试契约](./25-runtime-testing-and-cross-service-contract-design.md) | 顺序、异常传播、超时、取消、重试和清理 |
| R4 | [19 Tool/MCP/副作用](./19-runtime-tool-capability-mcp-and-side-effect-design.md)、[20 Backend/Workspace/Skills/Subagents](./20-runtime-backend-workspace-skills-and-subagents-design.md) | [11 Service 目录规范](./11-agent-service-directory-architecture.md)、[23 生命周期](./23-graph-thread-backend-checkpoint-lifecycle-design.md)、[14 Contracts](./14-runtime-contracts-and-resolution-design.md) | 显式工具装配、权限隔离、资源生命周期和子 Agent |
| R5 | [16 可观测与 Langfuse](./16-runtime-observability-and-langfuse-design.md)、[18 事件与 Run Explorer](./18-open-swe-to-runtime-event-and-run-explorer-design.md) | [15 Middleware 生命周期](./15-runtime-middleware-lifecycle-and-failure-semantics.md)、[22 Platform/Runtime 契约](./22-platform-runtime-contract-design.md)、[25 测试契约](./25-runtime-testing-and-cross-service-contract-design.md) | Trace、日志、指标、脱敏和 Run Event 投影 |
| R6 | [23 Graph/Thread/Checkpoint 生命周期](./23-graph-thread-backend-checkpoint-lifecycle-design.md)、[24 启停设计](./24-package-langgraph-startup-shutdown-design.md)、[25 测试契约](./25-runtime-testing-and-cross-service-contract-design.md) | [18 事件与 Run Explorer](./18-open-swe-to-runtime-event-and-run-explorer-design.md)、[22 Platform/Runtime 契约](./22-platform-runtime-contract-design.md) | Durable Run、恢复、重连、重启和终态收敛 |
| P1 | [22 Platform/Runtime 契约](./22-platform-runtime-contract-design.md)、[27 分阶段整合](./27-platform-runtime-integration-phased-design.md) | [10 总路线](./10-production-agent-platform-roadmap.md)、[18 事件与 Run Explorer](./18-open-swe-to-runtime-event-and-run-explorer-design.md)、[25 测试契约](./25-runtime-testing-and-cross-service-contract-design.md) | 配置快照、Gateway、权限、幂等和跨服务契约 |

文档冲突时，28 号只决定“何时做、做到什么门槛”；14、15、19、20、22、23、24、25 等领域
文档决定“具体怎么做”。旧目录和旧契约仍然不属于任何阶段的参考输入。

## 3. R0：新包、依赖和启动基线

### 目标

建立一个不依赖旧包的可启动 Runtime Service。

### 产物

- `apps/runtime-service/src/runtime_service/` 新包；
- `graphs/<graph_id>.py`、`agent.py`、`prompts.py`、`schemas.py`、`tools.py` 等 Service
  目录；
- `services/reference_agent/`、`services/workflow_demo/` 的第一批参考实现骨架；
- `langgraph.demo.json` 的本地 Demo 注册配置；
- 根目录 `langgraph.json`，R0 只注册新 Graph；Auth 延后到 R1；
- 固定的 `pyproject.toml`、锁文件、容器启动命令和 `.env.example`；
- 本地 fake model、真实模型 E2E 配置和 `langgraph dev` 调试脚本；文本模型使用 DeepSeek 中转，
  多模态模型使用 GPT 中转。

### 门槛

- `langgraph dev --config ./langgraph.json` 能启动；
- 新 Graph 能被 Agent Server introspection 找到；
- 导入路径不触碰旧 `runtime_service` 包；
- `git grep` 不出现新代码对旧模块的导入；
- R0 真实模型 E2E 在显式提供中转凭据时必须执行并通过，不能用 fake model 代替；未提供凭据时
  只能标记为未执行，不能标记为通过。

## 4. R1：Runtime Contracts、Auth、Resolver、Modeling

### 目标

冻结并实现 14 号文档定义的最小运行时契约。

### 产物

- `runtime/contracts.py`：不可变的 `RuntimeContext`、`RuntimePolicy`、`AgentDefaults`、
  `RuntimePrincipal` 和 `ResolvedRuntimeConfig`；
- `runtime/resolver.py`：纯函数校验、默认值合并和 fail-closed 决议；
- `runtime/modeling.py`：`model_id -> ChatModel` 的明确映射；
- `runtime/auth.py`：签名、audience、scope、过期时间和 Context hash 校验；
- `runtime/errors.py`：稳定 Runtime 错误码和安全错误摘要；
- `middlewares/runtime_config.py`：把已验证 Context 注入 Agent 执行。

### 约束

- Resolver 不访问 env、HTTP、数据库、MCP 或模型 Provider；
- Provider 凭据只从 Runtime 环境或 Secret Store 读取；
- `context.tools` 使用 `None`、空数组、非空数组三态语义；
- 旧字段直接拒绝，不提供 fallback；
- `model_id` 位于 Context，不位于 `configurable`。

### 门槛

- Unit 覆盖合法、缺失、越权、边界值和 hash 篡改；
- 不启动 Platform API 也能完成 Resolver 和 fake model 测试；
- 错误码和脱敏摘要固定下来。

## 5. R2：Agent Service 组合根

### 目标

用全新的 `reference_agent` 和 `workflow_demo` 证明基础组合根和两种官方 Graph 形态。

### 产物

- `agent.py` 中直接调用 `create_agent(...)`、`create_deep_agent(...)` 或
  `StateGraph(...).compile()`；
- 工具、Prompt、Schema、Middleware、Backend 和 Subagent 在 Service 内显式装配；
- 只有确实需要 Thread 级资源时才在 `get_agent(config)` 中动态创建实例；
- 不创建公共 `build_graph()` 或万能 Builder。

### 门槛

- `get_agent(config) -> Pregel` 组合测试通过；
- 静态 Graph 多次调用拓扑一致；
- 动态 Graph 只绑定当前 Thread 资源；
- introspection 不创建 Sandbox、MCP 连接或外部副作用。

`reference_agent` 和 `workflow_demo` 必须有独立 README、fake model 测试和标准
`langgraph.demo.json` 启动方式，作为后续 Demo 的复制模板。

## 6. R3：公共 Middleware 可靠性栈

### 目标

按 15 号文档实现最小、显式、有顺序的 Middleware 生命周期。

### 首批顺序

```text
RuntimeContext validation
  -> PrepareRun
  -> ModelCallLimit
  -> ToolPolicy
  -> ToolError
  -> ModelFallback
  -> ModelCallTimeout
  -> RunFinalizer
```

每个 Middleware 独立文件、独立构造参数、独立测试；不做万能 Middleware Builder。

### 门槛

- 顺序、异常传播、清理和取消测试通过；
- Provider 临时错误只进行有界 retry/fallback；
- 非幂等 Tool 不自动重试；
- 超时、工具错误和空结束都形成确定终态。

## 7. R4：能力和资源接入

### 目标

在真实 Service 需求出现后，逐项接入能力，不预建 Registry。

### 顺序

1. 只读 Tool；
2. 需要审批的写 Tool；
3. Service 私有 MCP；
4. 明确 Coding Agent 才接入 Thread Workspace/Sandbox；
5. 只读 Bundled Skills；
6. 显式缩权 Subagents。

R4 同时完成三个能力 Demo：`deep_agent_demo`、`mcp_demo`、`backend_demo`。它们分别覆盖
`create_deep_agent`、Service 私有 MCP、Tool 副作用隔离、Thread Workspace、动态
`get_agent` 和资源清理；不把这些能力硬塞进 `reference_agent`。

### 门槛

- Tool 同时通过模型可见性和执行前检查；
- MCP 名称冲突立即失败；
- 子 Agent 不得扩大父 Agent 权限；
- Backend 失败不静默切换目录；
- Thread、Workspace、Checkpoint 的恢复和清理有真实测试。

## 8. R5：观测和事件投影

### 目标

建立 Runtime 侧可排查性，但不把 Langfuse 当作 Run 状态库。

### 产物

- Langfuse Trace：模型、Tool、Subagent 和 Graph span；
- 结构化 Service 日志：`request_id`、`thread_id`、`run_id`、错误码和耗时；
- Runtime 指标：成功、失败、超时、取消、Tool 错误、Token 和恢复次数；
- 向 Platform 投影的安全 Run Event，不包含 Secret、完整 Prompt 或 Tool 参数。

### 门槛

- Langfuse 不可用不影响 Run 核心状态；
- 每次 Run 可定位 Graph、Model、Tool、Checkpoint 和终态；
- 日志和事件经过脱敏和大小限制。

## 9. R6：Durable Run 真实验证

### 目标

证明新 Runtime 在真实 Agent Server、PostgreSQL、Redis 和 Worker 重启下可恢复。

### 必须验证

- `durability=sync`、可恢复 Stream 和明确的断线策略；
- Thread 连续 Run、Interrupt/Resume、多次中断；
- Worker restart 后 checkpoint 恢复；
- cancel、timeout、Tool failure 和 terminal 状态收敛；
- SSE 重连按游标补发且不重复；
- 不依赖 Platform API 也能使用本地 Token 完成 smoke test。

R6 通过后，Runtime 才进入可被 Platform 调用的状态。

## 10. P1：Platform 控制面整合

### 前置条件

R0～R6 全部通过，Runtime 的 Context、错误码、事件和模型执行边界已经冻结。

### 产物

- 新建 Model Catalog、Project Model Policy、Assistant Runtime Config 和 Durable Run schema；
- Platform 侧配置合并和不可变 `RuntimeContext` snapshot；
- `context_hash` 与 Delegation Token 绑定；
- Gateway 统一注入 Context、durable 默认值和幂等键；
- Platform/Runtime 双端独立契约测试；
- 最后接入配置页面和 Run Explorer。

### 禁止事项

- 不把模型调用、Graph、Tool、Checkpoint 搬入 Platform；
- 不让 Platform 访问 Provider 凭据；
- 不增加 Runtime Custom Route、Model Registry、Route Registry 或第二套 Run API；
- 不读取或迁移旧 Platform 数据；新配置通过新管理 API 或部署清单创建。

## 11. 每个开发任务的执行模板

每个任务必须按同一循环执行：

```text
确认本计划对应阶段
  -> 写/更新该阶段最小契约和伪代码
  -> 创建独立 OpenSpec change（进入实现阶段后）
  -> 先写最小失败测试
  -> 实现最小代码
  -> 运行本阶段门槛和最短相关链验证
  -> 更新文档、verification.md 和下一阶段入口
```

任何任务如果需要旧代码适配、旧数据迁移、兼容路由或新公共抽象，应立即停止并重新评审，
不得为了“先跑起来”偷偷加入。

## 12. 完成定义

本次 Runtime 重构完成的最低标准：

1. 新 Runtime 包可独立部署和本地调试；
2. 一个 `reference_agent` 通过真实 Agent Server 的 Thread/Run/Stream/Checkpoint 闭环；
3. Contracts、Middleware、Tool、Backend 和观测边界有可运行测试；
4. Runtime 不依赖旧代码、旧数据或 Platform API；
5. Platform 整合只通过新 Context、Token、Run Event 和 Gateway 契约完成；
6. 所有旧兼容、迁移、双读、双写和 Adapter 方案均不在仓库目标实现中。

## 13. 可运行 Demo 计划

Demo 是开发计划的一部分，不是重构完成后的补充材料。每个 Demo 都必须是一个遵守正式
Service 规范的可运行参考实现，具备独立的 `agent.py`、`get_agent()`、README、测试
和 `graphs/<graph_id>.py` 导出。Demo 不承载产品业务，也不依赖旧 Runtime、旧数据或
Platform API。

### 13.1 Demo 目录和注册

不创建公共 `server/` 目录。每个 Demo 都放在正式 Service 目录下：

```text
apps/runtime-service/src/runtime_service/
├── graphs/
│   ├── reference_agent.py
│   ├── workflow_demo.py
│   ├── deep_agent_demo.py
│   ├── mcp_demo.py
│   └── backend_demo.py
└── services/
    ├── reference_agent/
    ├── workflow_demo/
    ├── deep_agent_demo/
    ├── mcp_demo/
    └── backend_demo/
```

生产和学习使用不同配置：

```text
langgraph.json       -> 默认只注册 reference_agent
langgraph.demo.json  -> 注册五个 Demo，供本地学习和集成测试
```

`graphs/<graph_id>.py` 只重导出对应 Service 的 `get_agent`，不放业务装配、模型创建、Tool
扫描、MCP 连接或额外 metadata registry。

### 13.2 五个 Demo 的覆盖矩阵

| Demo | 主要构造方式 | 必须覆盖 | 开始阶段 |
| --- | --- | --- | --- |
| `reference_agent` | `create_agent` | 最小 Service、Prompt、Schema、显式只读 Tool、Context、Middleware、Trace | R2 |
| `workflow_demo` | `StateGraph` | Typed State、节点/边、条件分支、Checkpoint、Interrupt/Resume | R2 |
| `deep_agent_demo` | `create_deep_agent` | Skills、显式缩权 Subagent、StateBackend、子图事件、长任务上下文 | R4 |
| `mcp_demo` | `create_agent` + 私有 MCP | MCP 加载、名称冲突、凭据边界、Tool Policy、读写副作用隔离 | R4 |
| `backend_demo` | `create_deep_agent` + Backend | Thread Workspace、动态 `get_agent`、资源隔离、失败和清理 | R4 |

公共 Contracts、Auth、Resolver、Modeling、Middleware、Observability 和错误处理不重复复制成
第六个 Demo，而是在所有 Demo 中使用同一公共实现，由 `reference_agent` 展示最短路径。

### 13.3 各 Demo 的最低实现要求

`reference_agent` 是默认复制模板，必须展示 `create_agent(...)`、显式 Tool、RuntimeContext
绑定、公共 Middleware 顺序、fake model、真实 Provider smoke test 和标准 Thread/Run/Stream
调用。它不包含 MCP、Sandbox、Git、任意 shell 或复杂 Subagent。

`workflow_demo` 必须展示 Typed `WorkflowState`、确定的节点和条件边、人工确认或恢复点，
并说明为什么确定性流程不应伪装成 `create_deep_agent`。`workflow.py` 只负责拓扑，
`agent.py` 负责组合和导出。

`deep_agent_demo` 必须展示 `create_deep_agent(...)`、一个显式缩权 Subagent、Bundled Skill、
默认 `StateBackend`、`stream_subgraphs`、namespace 和 Subagent 事件投影。它不接真实
Sandbox、GitHub、Slack 或 Linear。

`mcp_demo` 必须使用本地 stdio fake MCP Server，展示 Service 私有 `loader.py`、
`MultiServerMCPClient.get_tools()`、名称冲突立即失败、
`context.tools` 三态语义、模型可见 Tool 与执行前策略双重检查，以及写 Tool 的审批、幂等、
超时和明确 retry 名单。

`backend_demo` 必须使用本地 fake/in-memory Backend，展示 Thread-scoped Workspace、动态
`get_agent(config)`、不同 Thread 的资源隔离、Backend fail-closed、introspection 不创建
外部资源、worker restart 重建和 TTL 清理。真实 Sandbox 只能作为可选 smoke test。

### 13.4 Demo 实施顺序

```text
R0  创建 Demo 目录规范、Graph 导出约定和 langgraph.demo.json
R1  让 Demo 统一使用 Contracts/Auth/Resolver/Modeling 的调用样例
R2  实现 reference_agent 和 workflow_demo
R3  将公共 Middleware、错误和 Trace 接入前两个 Demo
R4  实现 deep_agent_demo、mcp_demo 和 backend_demo
R5  为五个 Demo 增加日志、指标、事件和脱敏验证
R6  对 reference_agent、workflow_demo 做必需 Durable E2E，其余做能力专项 E2E
```

R4 的组合原则已经落地：每个 Demo 在自己的 `get_agent()` 中直接调用官方构造函数并显式装配
能力。不会新增公共 `build_agent`、Builder、Factory 或 Registry；只有真实重复、复杂资源生命周期
或独立测试边界出现时，才允许 Service 私有的下划线辅助函数。

Demo 必须跟随阶段实现，不能等全部 Runtime 开发完成后再临时补写。R2 的两个 Demo 是第一条
完整纵向链路和后续复制模板；R4 的三个 Demo 只在对应公共能力有最小实现后加入。

### 13.5 Demo 统一验收

每个 Demo 都必须满足：

1. `async def get_agent(config: RunnableConfig) -> Pregel` 是唯一正式入口；
2. fake model 下可以在不启动 Platform API 的情况下运行；
3. `langgraph.demo.json` 能加载，graph ID 与导入路径一致；
4. README 说明构造函数选择、静态/动态生命周期、Context 和依赖装配位置；
5. 至少有一个 Service 装配测试和一个关键失败分支测试；
6. introspection 不触发 Sandbox、MCP、数据库或其他外部副作用；
7. 必要时能验证 Tool、Skills、Subagents、Backend、Checkpoint、Interrupt 和事件边界；
8. 生产 `langgraph.json` 不自动注册 Demo。

Demo 不引入公共 Builder、Factory、Registry、Plugin、Custom Route 或重复的 Runtime 内核。
