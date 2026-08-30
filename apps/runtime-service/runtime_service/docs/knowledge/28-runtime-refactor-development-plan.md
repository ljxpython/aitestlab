# Runtime Service 绿色重构开发计划

> 文档类型：Draft
>
> 状态：实施计划，尚未开始编码
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
- 旧 `apps/runtime-service/runtime_service/` 包只作背景参考，不能导入、复制或适配；
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

R0～R6 完成前不改 Platform 业务代码。P1 不是 Runtime 的前置条件，而是 Runtime 已经可以
独立运行后的第二条工作流。

## 3. R0：新包、依赖和启动基线

### 目标

建立一个不依赖旧包的可启动 Runtime Service。

### 产物

- `apps/runtime-service/src/runtime_service/` 新包；
- `graphs/<graph_id>.py`、`agent_server.py`、`prompts.py`、`schemas.py`、`tools.py` 等 Service
  目录；
- 根目录 `langgraph.json`，只注册新 Graph 和新 Auth；
- 固定的 `pyproject.toml`、锁文件、容器启动命令和 `.env.example`；
- 本地 fake model、开发 Token 和 `langgraph dev` 调试脚本。

### 门槛

- `langgraph dev --config ./langgraph.json` 能启动；
- 新 Graph 能被 Agent Server introspection 找到；
- 导入路径不触碰旧 `runtime_service` 包；
- `git grep` 不出现新代码对旧模块的导入。

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

用一个全新的 `reference_agent` 证明三种官方 Graph 形态的边界。

### 产物

- `agent_server.py` 中直接调用 `create_agent(...)`、`create_deep_agent(...)` 或
  `StateGraph(...).compile()`；
- 工具、Prompt、Schema、Middleware、Backend 和 Subagent 在 Service 内显式装配；
- 只有确实需要 Thread 级资源时才在 `get_agent(config)` 中动态创建实例；
- 不创建公共 `build_graph()` 或万能 Builder。

### 门槛

- `get_agent(config) -> Pregel` 组合测试通过；
- 静态 Graph 多次调用拓扑一致；
- 动态 Graph 只绑定当前 Thread 资源；
- introspection 不创建 Sandbox、MCP 连接或外部副作用。

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

