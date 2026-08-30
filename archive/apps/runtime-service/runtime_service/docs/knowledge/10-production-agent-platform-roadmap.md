# 生产级 Agent 平台架构结论与演进路线（总路线图）

- 文档类型：`Supporting`
- 适用范围：`apps/runtime-service`、`apps/platform-api` 及二者最短正式链路
- 结论确认日期：2026-08-29
- 权威边界：本文记录已确认的架构方向和后续讨论顺序，不替代 leaf standard、
  OpenSpec change 或具体实现评审

## 1. 目的

本文是 `runtime-service` 重构的总路线图，固化当前项目与 Open SWE 的架构对照结论，
并统领后续章节的讨论、设计、实现和验收顺序。11～27 号文档是按主题展开的设计稿，
不得脱离本文单独决定实施顺序。

本文确认的是演进方向，不代表已经授权：

- 修改公开 runtime contract；
- 创建新数据库 schema；
- 升级共享环境依赖；
- 切换 staging 或生产流量；
- 删除旧 Runtime/Platform 实现；
- 引入 Sandbox、GitHub、PR 等高副作用能力。

本次是绿色开发：旧代码和旧数据不作为新实现输入，不做迁移、双读、双写或兼容层。上述
新 schema 创建和旧实现删除仍按仓库执行分级和 OpenSpec 流程单独评审。

## 1.1 五条核心主线

本次重构不按“单 Agent / 多 Agent”拆两套架构，而是围绕同一个 Runtime Service 内核推进
以下五条主线：

| 主线 | 已讨论内容 | 尚未冻结的关键问题 | 主要设计文档 |
| --- | --- | --- | --- |
| Runtime Service 本身 | 目录、`get_agent` 入口、静态 Graph、动态 factory 边界、RuntimeContext | 公共 Python API 的最终表面和 reference Agent 验证 | 11、12、13、14、25 |
| Middleware 生命周期 | 生命周期、显式顺序、失败语义、首期清单 | 每个 Middleware 的构造参数、上下文读写、错误码和测试矩阵 | 15 |
| Tool 装配 / Capability / MCP | `get_agent` 显式装配、工具可见性与执行复核、MCP 边界 | 首个 Agent 的工具清单、MCP 失败语义和副作用场景测试 | 11、14、15、19 |
| Backend / Workspace / Skills / Subagents | Backend 分级、Thread Workspace、只读 Bundled Skills、Subagent 显式缩权 | 具体 Sandbox Provider API、跨进程事件和恢复验证 | 11、12、18、20、25 |
| 观测 / 成本 / 评测 / 发布 | Langfuse、Run/Audit/Logs/Metrics 边界、关联 ID | 成本归集、评测数据集、质量反馈、SLO 和发布门槛 | 16、17、18 |

另有一条横向契约贯穿五条主线：`platform-api` 负责控制面、治理和 Durable Run，
`runtime-service` 负责 Graph 执行；两者通过 Runtime Context、Run 状态、事件和
安全摘要连接，不能互相吞并职责。

## 1.2 文档导航和状态

```text
10  总路线图：阶段、依赖、进度和实施门槛
11  Agent Service 目录与部署入口
12  RuntimeContext、运行时配置和本地调试
13  新 Runtime Service 物理目录与 Legacy 处置
14  Runtime Contracts 与配置决议
15  Middleware 生命周期、顺序和失败语义
16  Langfuse 与公共可观测边界
17  平台 Run 查询、事件时间线与 Admin Console
18  Open SWE 借鉴边界和 Run Explorer 适配
19  Tool 显式装配、Capability Policy、MCP 与副作用隔离
20  Backend、Workspace、Skills 与 Subagents 公共接入
21  Agent、Graph、Prompt、Tool Policy 版本与发布治理（延期）
22  Platform API / Runtime Service JSON、错误、事件、幂等和权限契约
23  Graph、Thread、Backend 与 Checkpoint 生命周期
  24  Package、langgraph.json、启动与优雅退出
  25  Runtime 测试目录、测试分层与跨服务契约测试
  26  Runtime Custom Route 与模型配置边界
  27  Platform API 与 Runtime Service 分阶段整合设计
```

当前状态统一解释为：

- **已讨论**：原则和责任边界已形成，但不代表可以直接写代码；
- **待冻结**：还缺少字段、失败语义、迁移或验证契约；
- **可实施**：完成讨论、评审和最小验证设计后，才允许进入实现阶段。

## 2. 已确认结论

目标不是把 Open SWE 搬进当前仓库，而是让现有多 Agent 平台获得生产级运行品质：

> 可控、可恢复、可观测、失败有结论、外部副作用可隔离。

当前项目已经选对了主要方向，应继续保留：

1. `runtime-service` 使用版本化静态 Graph 作为默认形态。
2. 可信身份和项目范围由 `platform-api` 签发并进入类型化运行时上下文。
3. 模型、Prompt 和工具选择通过共享 resolver / middleware 在请求期解析。
4. `platform-api` 只承担 control plane、治理、审计、operation 和受控 runtime gateway。
5. LangGraph Agent Server 持有 thread、run、checkpoint 和执行状态。
6. Deep Agents 继续提供文件、skills、subagent 和上下文管理等通用长任务能力，项目不重复实现。

本次重构不新增 Runtime Custom Route 和模型配置中心。模型目录、项目/Assistant 配置和权限
由 Platform API 管理；Platform 在启动 Run 时透传经过授权的 `RuntimeContext`，Runtime 只
负责本地校验、模型实例化和执行。只有出现明确的非 LangGraph 协议需求，才重新评审
`langgraph.json.http.app`。

首期明确不引入 `engine/`、`builder/`、`factory/`、`registry/`、`plugin/`、
`orchestrator/` 或 `coordinator/` 等公共万能抽象。Open SWE 的 `get_agent()` 是直接组合官方
构造函数，`dispatch.py` 只是其业务侧 Durable Run 入口；这些代码都不应被包装成 Runtime
公共 Builder 或第二套调度内核。

应该从 Open SWE 吸收的是与 Coding Agent 业务无关的通用机制：

- 统一 Durable Run 派发；
- `durability="sync"`、可恢复事件流和确定终态；
- 模型超时、调用限额、Fallback、工具错误和失败收敛；
- 按身份和策略收缩工具能力；
- Thread 级资源恢复原则；
- Run、模型、工具、子 Agent 和终态之间的观测关联；
- 以真实链路、故障场景和质量指标作为发布门槛。

不应该从 Open SWE 复制：

- Slack、Linear、GitHub、PR 和 CI 自动修复产品逻辑；
- 面向所有 Agent 的全局 Sandbox 或 shell 能力；
- 仅为了动态模型、Prompt 或工具选择而采用的 Graph factory；
- Open SWE 的身份字段、配置大字典和 Dashboard API 契约；
- 与当前 Protocol v2、gateway 和项目权限模型并存的第二套生产 Run 状态机。

## 3. 职责边界

正式生产链路保持：

```text
platform-web / agent-web
  -> platform-api
       -> runtime-service / LangGraph Agent Server
            -> interaction-data-service 或其他受控下游
```

### 3.1 `platform-api`

负责：

- actor、tenant、project 和 permission；
- Assistant / Graph 的控制面映射；
- RuntimeOptions 白名单和项目策略；
- Run Coordinator、幂等、operation、审计和安全摘要；
- runtime 协议代理、错误整形和事件脱敏。

不负责：

- Graph 编排；
- Prompt 业务逻辑；
- 工具或 MCP 实现；
- 模型调用循环；
- checkpoint 内部状态。

### 3.2 `runtime-service`

负责：

- 版本化 Graph；
- 类型化 RuntimeContext 和 RuntimeOptions 消费；
- 模型、Prompt、工具和 middleware 装配；
- Agent 执行可靠性；
- tool / MCP 执行边界；
- 业务 Agent、specialist Agent 和必要的状态流。

### 3.3 LangGraph Agent Server

负责：

- thread、run 和 checkpoint；
- durable execution；
- interrupt / resume；
- stream 和事件重放；
- worker 与持久化运行时语义。

浏览器连接和 SSE 都不是 Run 事实源。Run snapshot、thread state 和 checkpoint 才是恢复与
终态判断依据。

## 4. 当前基础与主要缺口

### 4.1 已有正确基础

- `langgraph.json` 只注册新 Graph、Auth 和必要部署配置；非 LangGraph HTTP 路由不作为默认能力。
- 静态 `create_agent(...)`、`create_deep_agent(...)` 和显式 `StateGraph` 已有清晰适用边界。
- Legacy 中已有 `RuntimeRequestMiddleware`，目标由新 `middlewares/runtime_config.py` 取代；
  新实现不兼容旧字段和旧解析入口。
- 动态工具已同时覆盖模型可见性和实际执行绑定。
- Legacy 中存在 `tools/registry.py`，但目标架构明确弃用公共 Tool Registry；新 Service 只在
  `agent_server.py` 中显式装配工具。
- `platform-api` 已具备 project scope、delegation、runtime gateway、operation 和审计基础。
- Platform API 当前 Durable Run change 已实现 Coordinator、幂等记录、单 active Run、operation 映射和
  Protocol v2 前端 transport 的主要本地能力。

### 4.2 需要优先解决的缺口

1. **运行契约口径不完全一致**：代码中的 `RuntimeContext`、`RuntimeOptions` 与部分文档描述
   仍需统一，尤其是可信身份、业务选项和 `configurable` 的边界。
2. **缺少共享可靠性内核**：尚未形成统一的模型调用限额、单次超时、Run deadline、Fallback、
   ToolMessage 错误、空结束保护和 finalizer。
3. **Thread 资源隔离未完全证明**：部分 Deep Agent backend 使用模块级目录或实例，并发 thread、
   多 worker 和进程恢复语义需要单独验证。
4. **工具能力边界仍需验证**：尚未在每个 Service 的显式工具装配上完整验证副作用、幂等性、权限、超时、重试、审批和
   审计级别。
5. **Durable Run 仍缺真实运行时证据**：worker restart、checkpoint 恢复、事件 replay、多
   interrupt、重复 completion webhook 和真实 PostgreSQL/Redis 链路尚未全部验收。
6. **观测和质量门槛不足**：还不能稳定回答某次 Run 使用了哪个 Agent 版本、模型、Prompt、
工具策略，失败发生在哪一层，以及部署版本是否需要回滚。

### 4.3 五条主线的当前状态

#### 主线一：Runtime Service 基座

已讨论目录、Graph 形态、`get_agent(config) -> Pregel`、静态 Graph 与受限动态 factory、
RuntimeContext 和配置决议。Service 组合根直接调用 `create_agent`、`create_deep_agent` 或
`StateGraph.compile()`，必要时只对结果使用 `.with_config(execution_config(config))`，不引入
公共 `build_graph()` 或万能 Builder。尚未冻结公共模块的最终 API，包括 `contracts.py`、
`runtime_config.py`、`resolver.py`、`modeling.py` 和第一个基准 Agent 的验证范围。

实现顺序采用薄实现：`contracts.py` 只定义不可变类型，`resolver.py` 只保留一个纯决议函数
及少量私有校验，`modeling.py` 先使用 LangChain 标准模型初始化入口。Open SWE 中因 Gateway、
OAuth 和多 Provider 场景存在的复杂模型分支，不在首期复制，只有真实 Provider 需求出现时
才在 `modeling.py` 内增量加入。

#### 主线二：公共 Middleware

已讨论生命周期、顺序、失败分类和不使用万能 Builder。尚未冻结每个 Middleware 的具体构造
参数、上下文读写权限、异常类型、组合测试和与 LangChain/Deep Agents 版本的兼容矩阵。

#### 主线三：Tool 显式装配、Capability Policy、MCP 与副作用

已确定不建设公共 Tool Registry、Capability Profile DSL 或 Tool 元数据框架。每个 Service 在
`agent_server.py/get_agent()` 中显式装配普通 Tool，代码中的工具列表就是该 Agent 的最大能力
边界；`RuntimePolicy` 与 `RuntimeConfigMiddleware` 只负责对已装配工具进一步收缩并在执行前
复核。MCP 由 Service 私有 `mcp.py` 加载后直接加入工具列表，高副作用能力通过 Agent 边界、
HITL、明确的 retry 名单和工具自身的幂等/范围校验隔离。详细结论见 19 号文档。

#### 主线四：Backend、Workspace、Skills、Subagents

已确定不建设 Backend、Workspace、Skill 或 Subagent Registry。普通 Deep Agent 默认使用
`StateBackend`；只有明确需要文件和代码执行的 Service 才使用 Thread-scoped Sandbox；首期只
挂载只读 Bundled Skills；Subagent 显式声明 Tools、Skills、Middleware 和高风险权限，并且只能
继续收缩父 Run 的有效能力。具体 Sandbox Provider API、资源清理任务和跨进程 Trace/事件传播
仍需在实施前通过锁定版本和真实 Provider 验证。详细结论见 20 号文档。

#### 主线五：Trace、日志、指标、成本、评测与发布

已确定 Langfuse 只负责 Agent 工程 Trace，Platform Run/Audit/Logs/Metrics 各有事实源。
尚未冻结成本归集口径、评测数据集和轨迹断言、质量反馈、SLO、告警和数据
保留策略。

#### 横向主线：Platform API / Runtime Service 契约

已讨论控制面和执行面职责、可信配置、Durable Run、事件和 Run Explorer 的方向。22 号文档已
形成首版契约草案；具体 Schema、错误映射和跨服务测试仍待实施阶段冻结。

## 5. 目标架构

```text
Platform governance
  actor / project / policy / audit / operation
        |
        v
Single Durable Run Coordinator
  idempotency / lifecycle / safe summary
        |
        v
LangGraph Agent Server
  thread / run / sync checkpoint / replay / interrupt
        |
        v
Static Graph
  RuntimeContext + RuntimeOptions
        |
        v
Shared reliability middleware
  prepare / limit / timeout / fallback / tool error / finalizer
        |
        v
Capability policy
  get_agent explicit tools
    intersect runtime policy
    intersect per-run selection
        |
        v
Service tools / MCP adapters
  explicit HITL + retry + scope checks
        |
        v
Backend / Workspace / Skills / Subagents
  thread isolation + resource lifecycle + parent policy
        |
        v
Business Agent execution
```

默认使用静态 Graph。只有以下条件成立时才讨论受限动态 factory：

- 每个 thread 必须连接独立 Workspace / Sandbox；
- backend 或状态 schema 无法在执行期安全替换；
- 资源装配会实质改变 Agent 实例；
- 恢复时能够重建相同版本和相同资源绑定。

动态模型、Prompt、采样参数、工具白名单、知识库选择和固定条件分支都不足以成为引入
factory 的理由。

## 6. 分阶段路线

阶段按 `0 -> 1 -> 2 -> 3 -> 4` 推进。每一阶段先讨论并冻结最小契约，再实现，再提供该边界的
证据；不把五个阶段塞进一次大重构。阶段与五条主线的关系如下：

| 阶段 | 目标 | 覆盖主线 | 当前状态 |
| --- | --- | --- | --- |
| 0 | Runtime Service 基座、Context、Contracts、Platform/Runtime JSON 契约 | Runtime 基座、控制面/执行面契约 | 原则已讨论，公共 API 待冻结 |
| 1 | 公共 Middleware 可靠性内核 | Middleware 生命周期、失败语义 | 顺序已讨论，具体 API/测试待冻结 |
| 2 | Durable Run、事件和可恢复流 | Platform/Runtime 契约、Run Explorer | 事件模型已讨论，投递/Schema/API 待冻结 |
| 3 | Tool 显式装配、Capability、MCP、Backend、Workspace、Skills、Subagents | 能力和资源隔离 | 方案已讨论，具体 Service API 和资源恢复测试待冻结 |
| 4 | Trace、日志、指标、成本、评测和发布 | 观测与质量门槛 | Trace 边界已讨论，成本/评测/SLO 待冻结 |

阶段 0～4 不是五套 Agent 架构，而是同一个 Runtime Service 内核的依赖顺序。所有 Agent
最终都使用同一套 Context、Middleware、Capability 和观测契约。

### 阶段 0：Runtime Service 基座、运行契约与配置快照

详细设计：11、12、13、14、22、25 号文档。

先讨论：

- `RuntimeContext`、`RuntimeOptions`、`RunnableConfig.configurable` 的最终字段归属；
- Thread 与业务对象的稳定索引；
- Run 状态、错误码、事件顺序和幂等语义；
- Thread、Run、Trace 分别保存哪些安全关联摘要；
- Graph 不兼容时使用新 Graph ID 或部署回滚的人工操作约束。

验收：

- 客户端不能伪造身份和项目范围；
- 同一幂等键不会创建第二个 Run；
- Run 能通过 deployment revision、model 和安全摘要排查实际执行；
- 不在 metadata 中保存完整 Prompt、Token 或密钥。
- Unit、Composition 和跨服务契约测试可以在无外部基础设施的环境下稳定运行。

### 阶段 1：公共 Middleware 可靠性内核

详细设计：15 号文档。

第一批只讨论并实现最小公共栈：

```text
RuntimeContext validation
  -> idempotent PrepareRun
  -> ModelCallLimit
  -> ToolPolicy
  -> ToolError
  -> ModelFallback
  -> ModelCallTimeout
  -> RunFinalizer
```

后续按真实故障证据再增加 Inbox、stale Run watchdog、orphaned tool-call repair 和
progress guard。

验收：

- 模型卡住会超时并形成确定状态；
- 只有临时 provider 错误进入受控 Fallback；
- 工具错误形成结构化 `ToolMessage`；
- 非幂等写操作不会盲目重试；
- Run 不会无文本、无工具、无终态地静默成功。

### 阶段 2：Platform/Runtime 契约、Durable Run 与恢复闭环

详细设计：17、18、22、25 号文档；事件和 Run Explorer 细节在实现前必须继续冻结。

本阶段创建新的 OpenSpec change，不复用旧 change，不创建第二套 Coordinator、Run API 或事件协议。

重点完成其尚未覆盖的 runtime 和真实链路边界：

- 固定 Agent Server 镜像、SDK、CLI 和锁文件组合；
- 隔离 PostgreSQL / Redis；
- sync checkpoint 和 worker restart；
- Protocol v2 `run.start` / `input.respond`；
- POST SSE `since` replay；
- 多 interrupt 精确恢复；
- cancel、终态、operation 和 audit 收敛；
- 重复 completion webhook 幂等；
- Platform/Runtime JSON、错误、权限和事件契约。
- 共享契约 fixtures、双端独立验证、事件顺序和幂等冲突测试。

验收必须来自真实部署的最短链；mock upstream 和 in-memory runtime 只能作为辅助证据，
而 Unit、Composition 和契约向量测试作为快速反馈门槛。

### 阶段 3：Tool 显式装配、Capability Policy、MCP 与资源/副作用隔离

详细设计：19 号文档负责 Tool、Capability、MCP 和副作用；20 号文档负责 Backend、Workspace、
Skills 和 Subagents。

首期不定义通用 Tool Policy 数据结构。副作用、幂等、超时、审批、重试和审计要求直接落实在
具体 Tool、官方 Middleware 配置、Service README 和测试中；第二个 Service 出现稳定重复后，
再判断是否提取小型公共 helper。

实施顺序：

1. 只读工具；
2. 需要审批的写工具；
3. 外部副作用工具；
4. 只有明确 Coding Agent 需求时，才引入 Workspace / Sandbox / Git / PR capability。

普通 SQL、Testcase、Research Agent 默认不得获得 repo execution 或任意 shell 能力。

### 阶段 4：Trace、日志、指标、成本、评测与发布门槛

详细设计：16、17、18 号文档；成本、评测和发布门槛仍待冻结。

统一关联：

```text
request_id -> thread_id -> run_id -> assistant_version
           -> model call / tool call / subagent
           -> checkpoint / finalizer / business outcome
```

第一批只建设能驱动决策的指标：

- Run 成功、失败、超时和取消；
- queue、Run、模型和工具耗时；
- checkpoint resume 和 SSE reconnect；
- duplicate start；
- Token、模型调用和工具调用次数；
- 工具失败、审批拒绝和用户重试。

之后再建设领域数据集、轨迹断言、质量反馈和发布门槛。

### 阶段 5：Platform API 与 Runtime Service 整合

详细设计：22、26、27 号文档。

本阶段在 Runtime Service 已能独立启动、调试和完成真实 LangGraph Run 后进行。Platform
只补控制面能力：Model Catalog、Project Model Policy、Assistant Runtime Config、Run
配置快照、Delegation Token 和 Gateway 注入；不把 Graph、模型调用、Tool 或 Checkpoint
实现搬到 Platform。

最小实施顺序：

1. 对齐现有 Catalog、Policy、Assistant Profile 与新 `RuntimeContext` 字段；
2. 在 `runtime_runs` 保存不可变的 Context snapshot、hash 和 policy revision；
3. 由 Gateway 统一完成配置合并、幂等预留和 Token/context 绑定；
4. 通过 Platform/Runtime 双端契约测试和真实 Gateway 链路；
5. 最后接入前端配置页和 Run Explorer。

本阶段不新增 Runtime Custom Route、模型配置中心、Provider 凭据托管、独立 Event Bus 或
第二套 Run API。完整边界见 27 号文档。

## 7. 后续逐项讨论顺序

后续每次只讨论一个决策单元，按以下顺序推进：

1. Runtime 公共 API 最终形态；
2. `contracts.py`、`resolver.py`、`modeling.py` 伪代码与边界；
3. Runtime 内部异常与错误映射；
4. Graph、Thread Backend、Checkpoint 生命周期；
5. Package、`langgraph.json`、启动和优雅退出；
6. 测试目录与跨服务契约测试；
7. 最后统一更新 13 号物理目录文档。

以上七项完成后，再进入 Run Explorer、成本/评测、SLO 和合规等平台扩展议题。版本治理暂不
进入当前实施，见 21 号延期文档。

每个决策单元必须回答：

```text
问题和失败模式是什么？
现有代码的唯一责任点在哪里？
是否已有框架或仓库能力可复用？
最小改动是什么？
公开契约、权限、审计和迁移是否变化？
最小可运行验证是什么？
哪些边界明确不在本轮处理？
```

## 8. 实施约束

- 不做一次性大重构；优先在共享责任点解决一个根因。
- 不先抽象 `BaseAgentFactory`、插件系统或万能配置中心。
- 不复制 Deep Agents 已有的 filesystem、skills、subagent 和 summarization 能力。
- 不把 `runtime-service` 执行逻辑迁入 `platform-api`。
- 不在每个 Graph 内各自实现一套 timeout、retry 和 error handling。
- 不把旧路径纳入新 Durable Run E2E；新链路通过后按确认流程删除旧路径。
- 新行为先选择一个基准 Agent 验证，再推广到其他 Agent。

第一轮基准建议使用 `assistant`：依赖少、已有 HITL、多模态和动态工具样板，适合先证明公共
可靠性内核。涉及 Deep Agent backend 的能力应在公共内核稳定后，再用 `research_agent` 做第二轮验证。

## 9. 相关资料

- [LangGraph 生态优秀仓库调研与 runtime-service 对照](./07-langgraph-ecosystem-repository-research.md)
- [官方 LangGraph Runtime 升级与事件流迁移记录](./09-langgraph-runtime-upgrade-and-event-migration.md)
- [Agent Service 目录与部署入口](./11-agent-service-directory-architecture.md)
- [RuntimeContext 与本地调试](./12-runtime-context-and-local-debug-architecture.md)
- [Runtime Service 目标物理目录与 Legacy 处置](./13-runtime-service-target-code-layout.md)
- [Runtime Contracts 与配置决议](./14-runtime-contracts-and-resolution-design.md)
- [Middleware 生命周期、顺序与失败语义](./15-runtime-middleware-lifecycle-and-failure-semantics.md)
- [Langfuse 与公共可观测边界](./16-runtime-observability-and-langfuse-design.md)
- [平台可观测查询与 Admin Console](./17-platform-observability-query-and-admin-console-design.md)
- [Open SWE 借鉴与 Run Explorer 适配](./18-open-swe-to-runtime-event-and-run-explorer-design.md)
- [Tool 显式装配、Capability Policy、MCP 与副作用隔离](./19-runtime-tool-capability-mcp-and-side-effect-design.md)
- [Backend、Workspace、Skills 与 Subagents 接入](./20-runtime-backend-workspace-skills-and-subagents-design.md)
- [Agent、Graph、Prompt、Tool Policy 版本与发布治理](./21-agent-release-versioning-rollout-rollback-and-run-binding-design.md)
- [Platform API / Runtime Service 契约](./22-platform-runtime-contract-design.md)
- [Graph、Thread、Backend 与 Checkpoint 生命周期](./23-graph-thread-backend-checkpoint-lifecycle-design.md)
- [Package、langgraph.json、启动与优雅退出](./24-package-langgraph-startup-shutdown-design.md)
- [Runtime 测试目录与跨服务契约测试](./25-runtime-testing-and-cross-service-contract-design.md)
- [Runtime Custom Route 与模型配置边界](./26-runtime-custom-routes-and-model-config-design.md)
- [Platform API 与 Runtime Service 分阶段整合设计](./27-platform-runtime-integration-phased-design.md)
- [runtime-service 当前架构标准](../standards/02-architecture.md)
- [Agent 开发 Playbook](../standards/03-agent-development-playbook.md)
- [Middleware 开发 Playbook](../standards/08-middleware-development-playbook.md)
- [platform-api Runtime Gateway 标准](../../../../platform-api/docs/standards/runtime-gateway-interface-standard.md)
- [现有 React Agent Web / Durable Run change](../../../../../openspec/changes/add-react-agent-web/proposal.md)
- [Open SWE](https://github.com/langchain-ai/open-swe)

外部 `agent-engineering-learning` 分析资料用于形成本文结论，但不作为本仓库 current standard；
后续实现必须以当前锁文件、官方文档、活代码和真实验证结果为准。
