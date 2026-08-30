# 多 Agent 平台：Agent 服务目录与部署入口架构设计（Draft）

> 文档类型：Draft
>
> 状态：讨论中，不替代 `docs/standards/` 下的现行规范
>
> 冻结范围：多 Agent 平台中的服务目录、部署入口、子 Agent、依赖方向和代码规范
>
> 公共 Runtime、中间件、Tool 运行时授权、可观测、Durable Run、平台控制面和测试契约以关联
> 文档为准；本文只定义 Agent Service 的目录、组合根、部署入口和依赖方向。
>
> Tool、MCP 与副作用设计：`19-runtime-tool-capability-mcp-and-side-effect-design.md`
>
> Backend、Workspace、Skills 与 Subagents 设计：
> `20-runtime-backend-workspace-skills-and-subagents-design.md`

> 测试目录与跨服务契约设计：
> `25-runtime-testing-and-cross-service-contract-design.md`

## 1. 本轮结论

新的业务 Agent 统一放在：

```text
apps/runtime-service/src/runtime_service/services/<service_name>/
```

每个 Service 只有一个 Top-level Agent 和一个组合根 `agent_server.py`。顶层
`src/runtime_service/graphs/` 是部署契约层，应用根 `langgraph.json` 只注册该目录中的稳定入口，
不感知 `services/` 的内部位置。

Agent 组合根不是 HTTP/FastAPI Server。它负责组合模型、Prompt、工具、中间件、
Backend、Context 和最终图；`graphs/<graph_id>.py` 只负责把该结果稳定导出给
LangGraph Agent Server。

本轮采用以下原则：

1. 每个 Service 统一导出 `async get_agent(config: RunnableConfig) -> Pregel`；静态图默认只
   编译一次，只有运行前必须创建线程级资源时才在 `get_agent` 内动态构图。
2. `create_agent` 是普通工具调用 Agent 的默认选择。
3. 只有确实需要文件系统、Skills、Subagents 或长任务上下文管理时才使用
   `create_deep_agent`。
4. 只有流程本身存在确定步骤、分支、循环或恢复点时才新增 `workflow.py` 并使用
   `StateGraph`。
5. Tools 和 Skills 是两类能力，不能放进同一个 `tools.py`。
6. 目录按真实职责生长，不创建空文件和未来可能使用的抽象层。

### 1.1 面向多 Services / Agents 的平台方向

未来平台中的三个概念必须分开：

| 概念 | 含义 | 是否进入 `langgraph.json` |
| --- | --- | --- |
| Service | 业务能力、代码所有权和演进边界 | 否 |
| Top-level Agent | 可被平台直接创建 Assistant/Run 的图 | 是 |
| Subagent | 只由父 Agent 委派的内部执行单元 | 否 |

平台统一采用“单入口、多智能体 Service”：

```text
1 Service = 1 Top-level Agent = 1 graph_id = 1 agent_server.py
```

Top-level Agent 内部可以使用 `create_agent`、`create_deep_agent`、多个 Subagents 或显式
`StateGraph`。如果某个内部 Agent 需要被平台直接调用，或需要独立版本、权限、Run、状态、
扩缩容和发布生命周期，则将它提升为新的 Service，而不是在原 Service 下暴露第二个
Top-level Agent。

目标调用关系是：

```text
Platform API / Assistant Catalog
  -> 稳定 graph_id + version
  -> LangGraph Agent Server
  -> runtime_service.graphs.<graph_id>:get_agent
  -> runtime_service.services.<service>.agent_server:get_agent
  -> create_agent | create_deep_agent | StateGraph
  -> service-private Subagents / Tools / Skills
```

Platform API 管理 Agent 的身份、版本、租户授权和发布状态，但不理解 Python 文件位置；
Runtime Service 负责执行。顶层 `graphs/` 就是两者之间最小而稳定的部署边界。

## 2. 为什么这样设计

本设计按目标架构从零收敛职责，不以当前 `runtime_service/agents/*` 和
`runtime_service/services/*` 的目录、graph ID、导入路径或行为兼容性作为约束。现有实现
统一视为 Legacy，只用于确认需要归档的范围，不作为新代码范式。

Open SWE 的真实入口链路是：

```text
LangGraph registration
  -> agent/graphs/agent.py:traced_agent    # 稳定导出层
  -> agent/server.py:get_agent(config)     # 动态组合根
  -> create_deep_agent(...)                # 编译执行图
```

它还把 `prompt.py`、`tools/`、`middleware/`、`runtime/` 和 `skills/` 分开。这个依赖方向
值得借鉴，但不能照搬它的大型 `server.py`。Open SWE 必须按线程解析 Sandbox、GitHub
身份、仓库指令和动态集成；SQL、测试用例或知识问答 Agent 通常没有这个前提。

因此本项目借鉴的是：

- 稳定注册入口与实际能力实现分离；
- 组合根统一决定工具和中间件顺序；
- Tools 采用明确的能力清单，不把所有工具默认暴露给模型；
- Skills 作为独立资源按需加载；
- 动态工厂只服务于真实的运行期资源差异；
- 所有 Service 使用相同的异步 `get_agent` 部署入口，但不强迫静态 Agent 每次重新编译；
- 探测 schema、读取状态等非执行调用不得创建昂贵外部资源。

本项目不照搬：

- 不把业务装配逻辑写进顶层 `graphs/`；该层只提供稳定部署地址；
- 不复制 Open SWE 与 GitHub、Slack、Linear、Sandbox 绑定的业务模块；
- 不把所有普通 Agent 改成每次运行重新编译的动态工厂；
- 不建设一个接受所有可选参数的“万能 Agent Builder”。

## 3. 推荐目录

平台与常规业务 Agent 的基线如下：

```text
apps/runtime-service/
├── src/runtime_service/
│   ├── graphs/                      # LangGraph 部署契约层
│   │   ├── __init__.py              # 不批量导入所有 graph
│   │   └── <graph_id>.py            # 只重导出 get_agent
│   └── services/
│       └── <service_name>/
│           ├── __init__.py
│           ├── agent_server.py      # 唯一 Top-level Agent 组合根
│           ├── prompts.py
│           ├── tools.py
│           ├── schemas.py
│           ├── README.md
│           └── skills/              # 仅使用 Deep Agents Skills 时存在
│               └── <skill-name>/
│                   ├── SKILL.md
│                   └── ...          # 可选 scripts/templates/references
└── tests/services/<service_name>/
    └── test_agent_server.py
```

这是一份职责地图，不是空文件生成清单。物理文件规则如下：

| 路径 | 要求 | 职责 |
| --- | --- | --- |
| `__init__.py` | 必需 | 标识 Python package；默认不做重导出，不产生导入副作用 |
| `agent_server.py` | 必需 | Service 唯一 Top-level Agent 的组合根，导出 `get_agent` |
| `src/runtime_service/graphs/<graph_id>.py` | 注册后必需 | 稳定部署入口，只重导出正式符号 |
| `README.md` | 必需 | 记录能力、契约、依赖、风险和验证方式 |
| `tests/services/<service_name>/` | 注册前必需 | 在生产包外覆盖入口加载和本服务的关键行为 |
| `prompts.py` | 通常需要 | 静态 Prompt 与纯渲染函数；没有服务 Prompt 时省略 |
| `tools.py` | 按需 | 服务私有业务工具；没有私有工具时省略 |
| `schemas.py` | 按需 | 服务私有输入、输出、状态和配置类型；没有类型时省略 |
| `skills/` | 按需 | Deep Agents 的 Agent Skills 资源；普通 Agent 不创建 |

复杂度出现后才允许增加：

```text
services/<service_name>/
├── workflow.py         # 显式 StateGraph 的节点和拓扑
├── middleware.py       # 服务私有的横切策略
├── mcp.py              # 服务私有 MCP 连接和工具加载
├── subagents.py        # 少量轻量声明式 SubAgent
├── subagents/          # 复杂或多个 Subagent 时替代单文件
├── backend.py          # 服务确有专属 Backend 组合时
├── tools/              # tools.py 已包含多个独立能力域时替代单文件
├── middleware/         # 私有 middleware 已形成多个独立生命周期组件时
└── evals/              # 领域数据集和发布门槛成熟后
```

不能同时保留同一职责的单文件和 package。例如从 `tools.py` 拆到 `tools/` 后，删除原
单文件，由 `tools/__init__.py` 只维护必要的公开导出。

## 4. 依赖方向

```text
langgraph.json
  -> runtime_service.graphs.<graph_id>:get_agent
       -> runtime_service.services.<service>.agent_server:get_agent

被选中的 Agent 组合根
  -> prompts.py / schemas.py
  -> tools.py | tools/
  -> workflow.py                 # 仅显式 StateGraph
  -> middleware.py                # 仅服务私有策略
  -> mcp.py / subagents.py / backend.py
  -> runtime_service 的公共稳定能力

skills/<skill>/SKILL.md
  -> 由 Deep Agents SkillsMiddleware + Backend 按需读取
```

必须遵守：

1. 依赖只能从 `agent_server.py` 指向服务内部模块，内部模块禁止反向导入组合根。
2. `prompts.py`、`schemas.py` 应保持纯净，不能创建模型、网络客户端或 Backend。
3. 一个业务服务禁止直接导入另一个业务服务的私有实现。
4. 公共能力只通过 `runtime_service` 后续确定的稳定公开入口消费，不复制到服务目录。
5. `langgraph.json` 只指向 `runtime_service.graphs.*`，不直接指向 Service 实现。
6. `skills/` 是运行时资源，不参与 Python import 依赖图。
7. `src/runtime_service/graphs/__init__.py` 禁止批量导入所有 Agent，避免制造额外的跨 Agent 导入耦合。

## 5. `agent_server.py` 组合根编写规范

### 5.1 允许负责

- 声明服务默认值；
- 从公共 Runtime 取得模型、Context 和平台能力；
- 导入并选择服务私有 Prompt、Tools、Middleware、Skills、Subagents 和 Backend；
- 明确中间件顺序；
- 调用 `create_agent`、`create_deep_agent` 或服务私有 `workflow.py`；
- 向顶层 `src/runtime_service/graphs/` 导出唯一正式入口。

### 5.2 禁止负责

- 实现具体工具函数；
- 存放大段 Prompt 文本；
- 定义业务 API schema；
- 实现 MCP client、数据库 repository 或 HTTP client；
- 在模块 import 时连接数据库、加载远程 MCP、创建 Sandbox 或访问外部服务；
- 同时维护多套互相竞争的 graph 构建路径。

### 5.3 统一入口与内部生命周期

平台对外只有一个组合根协议：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    ...
```

`get_agent` 统一的是部署入口，不统一 `create_agent`、`create_deep_agent` 和 `StateGraph`
的构造参数，也不意味着每次调用都必须重新编译图。Service 内部仍然区分静态图和动态
构图两种生命周期。

静态图的默认形态是在模块加载时编译一次。`get_agent` 不重新构图；如果需要把本次执行的
`RunnableConfig` 绑定到返回值，可对已编译实例调用 `.with_config(...)`：

```python
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

_AGENT: Pregel = create_agent(...)


async def get_agent(config: RunnableConfig) -> Pregel:
    return _AGENT.with_config(execution_config(config))
```

`_AGENT` 也可以来自 `create_deep_agent(...)`。显式 `StateGraph` 由 Service 自己声明节点和边
并调用 `compile()`；这不是公共 `build_graph()`。下划线表示它是 Service 内部实现，不是
`langgraph.json` 的正式导出。

以下变化仍使用静态图，由 Runtime、Middleware 或 Backend 自己处理：

- 每次请求选择不同模型、温度、Prompt 或工具 allowlist；
- 根据用户、租户、角色和项目做权限过滤；
- 使用 `StateBackend()` 的 thread-scoped 状态；
- 使用 `StoreBackend(namespace=...)` 按 Runtime 做租户隔离；
- 主 Agent 和 Subagents 的集合、工具 schema、中间件顺序在部署版本内稳定；
- 外部 client 可以在 Tool 调用时通过 Runtime 安全取得，而不是绑定到编译图。

只有满足以下条件之一，并且无法由上述机制安全表达时，才在 `get_agent` 内动态构图：

- Backend/Sandbox 必须绑定当前 thread 或 run；
- 租户隔离要求每次创建不同的资源句柄；
- 工具 schema 来自只能在执行前异步发现的 MCP 服务；
- Subagent runnable 或其不可复用资源必须在运行前按可信上下文创建。

动态实现保持同一个入口签名，只把确实依赖运行配置的装配留在函数内部：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    backend = await create_thread_backend(config)
    agent = create_deep_agent(
        model=DEFAULT_MODEL,
        tools=SERVICE_TOOLS,
        backend=backend,
    )
    return agent.with_config(execution_config(config))
```

这里的 `SERVICE_TOOLS`、`SERVICE_SUBAGENTS` 和 Middleware 都由当前 Service 显式装配；不能
通过公共 Builder、自动扫描或一个通用 `build_graph()` 统一生成。

典型动态场景是 Open SWE：每个 thread 要连接或创建自己的 Sandbox，并把该 Backend 绑定
给 Deep Agents 的文件和执行工具。典型静态场景是测试用例 Agent：即使使用 Skills、
Subagents 和 thread-scoped StateBackend，只要图结构和资源类型稳定，仍然可以启动时编译。

LangGraph Agent Server 会把 `get_agent` 作为 graph factory 调用，并且不只在创建 Run 时
调用，也会在读取 state、schema 和可视化等场景调用。因此动态实现必须：

1. 通过 Agent Server 提供的执行上下文区分真实执行与探测调用；
2. 探测路径不得连接 Sandbox、MCP、数据库或其他昂贵资源；
3. 所有调用返回相同的 nodes、edges 和 state schema；
4. `get_agent` 不兼任资源 teardown 管理器；连接释放由 Backend、Tool 或明确的资源所有者负责；
5. 不缓存用户、租户、thread、凭据或连接到 module global；
6. 对动态构建耗时、失败率和资源回收建立测试与观测。

如果资源必须由 graph factory 自身 setup/teardown，`async get_agent(...) -> Pregel` 已不足以
表达其生命周期。该场景必须单独评审 LangGraph async context manager factory，不允许悄悄
改变返回类型或留下连接泄漏。

选择顺序固定为：

```text
能否启动时编译？
  -> 能：是否只存在 per-run 值变化？
       -> 是：module-level _AGENT + get_agent 复用同一编译实例（按需绑定 config）
       -> 否：继续检查资源是否必须绑定到编译图
  -> 不能：资源能否由 Backend/Tool 自己管理生命周期？
       -> 能：get_agent 内动态装配并返回编译图
       -> 不能：单独评审 async context manager factory
```

### 5.4 唯一导出

每个 `agent_server.py` 只导出一个正式入口：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    ...
```

对应的 `src/runtime_service/graphs/<graph_id>.py` 只重导出该符号，例如：

```python
from runtime_service.services.test_case.agent_server import get_agent

__all__ = ["get_agent"]
```

测试 helper 和 Service 私有拓扑 helper 使用下划线前缀，不作为部署契约；它们不能演变成跨
Service 的通用 Builder。`langgraph.json` 只指向
顶层部署适配文件中的 `get_agent`。`config` 默认只读；Service 不得为了方便原地修改调用方
传入的 `RunnableConfig`。

### 5.5 为什么 `get_agent` 不是万能 Builder

`get_agent` 只约束输入和返回值，不提供统一构造参数，也不判断 Agent 类型。每个 Service
仍然直接调用最适合自己的官方 API：

```text
get_agent(config)
  -> create_agent(...)
  |  create_deep_agent(...)
  |  StateGraph(...).compile()
  -> Pregel
```

公共层只提供 `RuntimeContext`、运行时设置解析、公共 Middleware、Runtime Policy 和可观测等
横切能力。禁止增加 `kind="deep"`、包含大量可选字段的 `AgentSpec`，或同时接收 Tools、
Skills、Subagents、Nodes 和 Edges 的统一 Builder。只有新架构下至少两个 Agent 出现真实、
稳定的重复，才提取小而专一的公共函数。

`.with_config(...)` 只用于绑定当前 Run 的执行控制和追踪字段，例如
`recursion_limit`、`tags`、`metadata` 以及受控的 `configurable` 执行 ID。它不负责选择模型、
Prompt、Tools、Backend 或 Graph 类型；这些仍由 Service 的显式装配和 Runtime Middleware/
Resolver 完成。Service 不得原地修改传入的 `RunnableConfig`，也不得把完整的
`configurable` 字典无过滤地绑定到 Graph。

## 6. 各模块编写规范

### 6.1 `prompts.py`

- 存放服务身份、领域规则和 Prompt 模板；
- 动态 Prompt 使用纯函数渲染，参数应来自明确 schema；
- 区分可信平台指令和外部不可信内容，不能简单字符串拼接后混为系统规则；
- 不读取环境变量、数据库、文件系统或网络；
- 不把工具权限控制仅写成 Prompt，权限必须由服务端策略执行。

### 6.2 `tools.py` / `tools/`

- 只实现服务领域动作，不重复 Deep Agents 已有能力；
- 每个 Tool 必须有稳定名称、清晰描述和严格参数 schema；
- 身份、租户、权限和项目范围从可信 Runtime 取得，不能相信模型传入的同名参数；
- 读操作、写操作和外部副作用必须可区分；高副作用动作后续接统一审批和审计；
- 工具错误只归一化模型能够修正或降级的错误，编程错误不能静默吞掉；
- 动态工具加载由组合根或 Middleware 完成，工具模块不反向修改 Agent；
- 当单文件已经包含多个独立集成域并需要独立测试时，才拆成 `tools/` package。

### 6.3 `skills/`

- 每个 Skill 使用独立目录和 `SKILL.md`，遵循 Agent Skills 标准；
- Skill 用于工作流程、领域知识、模板和按需说明，不等同于可执行 Tool；
- scripts、templates、references 跟随对应 Skill，不塞进 `tools.py`；
- Skill 不能授予权限，也不能绕过 Tool、Backend 或 Middleware 的安全边界；
- 不复制系统 Prompt 或 Tool 文档来制造三份真源；
- 只有 `create_deep_agent` 服务确实启用 Skills 时才创建该目录。

### 6.4 `schemas.py`

允许包含：

- 服务私有输入/输出 schema；
- structured response schema；
- 服务私有配置类型；
- 显式 `StateGraph` 或私有 Middleware 需要的状态类型。

禁止包含：

- 环境变量读取和配置优先级解析；
- 模型、工具、Backend 或 client 创建；
- 数据库访问和业务流程；
- `platform-api` 公共接口模型的复制品。

先保持一个 `schemas.py`。只有真实出现独立的 state、config、API 类型族后再拆分，
不预建 `state.py`、`config.py`、`types.py` 和 `models.py`。

### 6.5 `workflow.py`

`workflow.py` 不是所有 Agent 的标配。它只用于显式 LangGraph 工作流：节点、边、条件路由、
循环、interrupt 和恢复点。普通 ReAct/tool-calling Agent 直接在 `agent_server.py` 调用
`create_agent` 或 `create_deep_agent`。

存在 `workflow.py` 时：

- `workflow.py` 负责业务拓扑；
- `agent_server.py` 负责模型、工具、中间件、Context 和服务导出；
- 两者不能都成为组合根；
- 节点函数不读取进程全局的用户/租户状态。

### 6.6 私有 Middleware、MCP、Subagents 和 Backend

- `middleware.py` 只放该业务独有的横切策略，不复制公共超时、重试、观测和错误处理；
- 确定性业务步骤放 `workflow.py`，不要伪装成 Middleware；
- `mcp.py` 只负责该服务私有 MCP 的连接、工具加载和生命周期；
- `backend.py` 只在公共 Backend 组合无法表达该服务需求时创建。

### 6.7 Subagents 的代码位置

Subagent 是父 Agent 的内部能力，不是缩小版的部署服务。按复杂度选择第一种够用的结构。

#### 轻量声明式 SubAgent

只有少量 `SubAgent`，且主要由 name、description、Prompt、Tools 和 Skills 组成时：

```text
services/<service_name>/
├── agent_server.py
├── subagents.py
├── prompts.py
└── tools.py
```

`subagents.py` 导出 `build_subagents(...)`，由 `agent_server.py` 显式传给
`create_deep_agent(subagents=...)`。不要把 SubAgent 定义塞进 `tools.py`。

#### 多个或复杂 Subagent

当 Subagent 有独立 Prompt、Tools、Skills、Middleware、schema 或测试时：

```text
services/<service_name>/
└── subagents/
    ├── __init__.py                 # 只暴露必要 builder
    ├── reviewer.py                 # 中等复杂度时一 Agent 一文件
    └── researcher/                 # 有独立资源时才升级为 package
        ├── __init__.py
        ├── agent.py                # build_subagent(...)
        ├── prompts.py
        ├── tools.py
        ├── schemas.py              # 按需
        ├── workflow.py             # 仅 CompiledSubAgent 的显式状态流
        └── skills/                 # 按需

tests/services/<service_name>/
└── subagents/
    └── test_researcher.py
```

内部 Subagent 使用 `agent.py`，不用 `agent_server.py`，因为它不被 Agent Server 注册。

#### 声明式与编译式选择

| Subagent 形态 | 使用场景 | 构建位置 |
| --- | --- | --- |
| `SubAgent` 字典/类型 | 专用 Prompt、Tools、Model、Skills 足够表达 | `subagents.py` 或 `subagents/<name>.py` |
| `CompiledSubAgent` | 自己需要 `create_agent` 或显式 `StateGraph` | `subagents/<name>/agent.py` |
| Top-level Agent | 需要被平台直接调用、独立版本和 graph ID | 提升为新 Service：`agent_server.py` + 顶层 `graphs/<graph_id>.py` |

子 Agent 还必须遵守：

1. Prompt 不继承主 Agent，必须显式定义；
2. Tools 默认继承行为不能作为权限设计，生产代码显式给出最小工具集；
3. 自定义 Middleware 不继承主 Agent，可靠性、Runtime 注入和权限策略必须显式配置；
4. Skills 默认隔离，Subagent 需要自己的 Skills 路径；
5. Subagent 的文件权限、interrupt 和 structured response 独立声明；
6. 父 Agent 只接收 Subagent 最终结果，不能依赖其内部临时状态；
7. `CompiledSubAgent` 的 runnable 必须已编译，并包含 Deep Agents 要求的 `messages` state key；
8. 如果平台需要直接查询、恢复或观测该图的独立状态，将它提升为 Top-level Agent，
   不再藏在 `task` tool 后面。

#### Subagent 流式展示与状态边界

Subagent 不能被平台当作独立 Run 管理，不等于其执行过程不可见。Deep Agents 和
LangGraph 支持将 Subagent 的详细过程流式投影给前端：

| 能力 | 是否支持 | 说明 |
| --- | --- | --- |
| 识别主 Agent / Subagent | 支持 | namespace 标识 Agent 层级和 `task` tool call ID |
| 模型消息与 token | 支持 | 使用 messages/event projection |
| Tool 调用、参数、结果 | 支持 | 使用 tools、updates 或 event projection |
| 任务进度和自定义状态 | 支持 | 使用 tasks、updates、custom projection |
| Subagent 最终输出 | 支持 | 父 Agent 和 Subagent stream 都可消费 |
| 断线后重放事件 | 条件支持 | 需要远程 resumable stream 或 Protocol v2 `since` |
| 独立 `get_state` / checkpoint | 默认不支持 | `task` tool 内启动的 Subagent 不是独立平台资源 |
| 独立恢复、取消或重试 | 默认不支持 | 只能通过父 Run 控制，或提升为独立 Service |

本地 Python 调用可以使用：

```python
agent.stream(
    input,
    stream_mode="updates",
    subgraphs=True,
    version="v2",
)
```

新 event streaming API 使用 `stream_events(...)` / `astream_events(...)` 的 typed
projections；前端 `useStream` 可以通过 `stream.subagents` 展示独立 Subagent 卡片、消息和
Tool calls。远程 Agent Server 创建 Run 时需要设置 `stream_subgraphs=true`，否则默认不返回
子图事件。

每个启用 subgraph streaming 的事件都带 namespace。例如空 namespace 表示主 Agent，
`("tools:<call_id>",)` 表示某次 `task` 创建的 Subagent，更深的 namespace 表示其内部模型
或节点。前端应按 namespace / tool call ID 聚合为可折叠的 Subagent timeline，不把所有
原始事件倾倒进主聊天记录。

Protocol v2 的目标事件接口继续使用 channels、namespaces、depth 和 `since` 做筛选与重放。
但必须区分：

- **流式事件是观察面**：可以展示消息、Tools、进度、生命周期和结果；
- **checkpoint 是状态面**：决定状态能否查询和恢复；
- **Run/Command 是控制面**：决定能否取消、interrupt 和 resume。

`stream_resumable` 或 Protocol v2 `since` 只能恢复事件观看位置，不能把内部 Subagent 变成
可独立恢复的 Run。声明式 Subagent 的 `interrupt_on` 可以让父 Run 暂停并从父 Run 恢复，
但平台仍不能把它当作独立 Subagent Run 控制。

如果产品确实需要查看嵌套 checkpoint，应把 Subagent 作为显式 `StateGraph` subgraph 从
node 调用；如果还需要独立版本、Run、取消、恢复、权限或 SLA，则提升为新的单入口 Service。

生产流禁止直接暴露原始敏感 Tool 参数、Tool 结果、凭据或未脱敏模型内容。Platform API
必须按租户、权限和事件 channel 做授权、裁剪与脱敏。

## 7. 顶层 `src/runtime_service/graphs/` 部署层

本 Draft 采纳 Open SWE 的 `agent/graphs/` 思想，但只保留最薄的一层稳定入口。

采用它的原因不是“目录更整齐”，而是未来多个 Services/Agents 后需要稳定的部署契约：

- `langgraph.json` 的路径不随 Service 内部重构变化；
- graph ID、Python 导出符号和业务目录明确分离；
- 不通过 `graphs/__init__.py` 聚合导入制造额外的跨 Agent 导入耦合；
- 所有 graph ID 使用相同的 `get_agent` 导出契约；静态或动态生命周期留在 Service 内部；
- 将来调整 Service 内部目录或新增单入口 Service 时无需改控制面认知。

目录规则：

```text
src/runtime_service/graphs/
├── __init__.py              # 保持空或只写 package docstring
├── assistant.py             # __all__ = ["get_agent"]
├── test_case.py             # __all__ = ["get_agent"]
└── coding_agent.py          # __all__ = ["get_agent"]
```

每个文件名与 graph ID 保持一致，只允许：

1. 从对应 Service 的 `agent_server.py` 导入正式符号；
2. 必要时做稳定别名；
3. 声明 `__all__`。

禁止在这一层解析配置、创建模型、加载 Tools、注册 Middleware、连接外部资源或维护一份
额外的 Agent metadata registry。graph 描述、启用状态和平台治理元数据属于后续控制面，
不塞进这些三行适配文件。

示例：

```json
{
  "graphs": {
    "test_case": {
      "path": "runtime_service.graphs.test_case:get_agent",
      "description": "测试用例 Agent"
    },
    "coding_agent": {
      "path": "runtime_service.graphs.coding_agent:get_agent",
      "description": "带 thread-bound Sandbox 的 Coding Agent"
    }
  }
}
```

Open SWE 的 `graphs/agent.py`、`graphs/reviewer.py`、`graphs/analyzer.py`、`graphs/chat.py`
证明了这种稳定导出层对多图产品有价值。本项目不复制其 tracing wrapper 细节；公共 tracing
如何接入留到可观测专题统一决定。

## 8. 框架选择规则

| 场景 | 首选 |
| --- | --- |
| 普通对话、检索、少量业务工具 | `create_agent` |
| 需要文件工作区、Skills、Subagents、长任务分解 | `create_deep_agent` |
| 确定步骤、条件分支、循环、人工中断或显式恢复点 | `StateGraph` |
| 仅模型/Prompt/工具随请求变化 | module-level 静态图 + Runtime Middleware |
| thread/run 绑定 Sandbox、动态 Backend 或资源生命周期 | `get_agent` 内动态构图 |
| 同一 Deep Agent 有固定声明式/编译式 Subagents | 静态 `create_deep_agent` |
| Subagent runnable 必须绑定 per-run 不可复用资源 | `get_agent` 内动态构图，且保持拓扑稳定 |

禁止为了“以后可能复杂”直接选择 `create_deep_agent`、`StateGraph` 或动态构图。

## 9. README 与测试基线

每个已注册服务的 `README.md` 至少记录：

- graph ID、`runtime_service.graphs.*` 入口和 Service 组合根；
- 服务目标与不负责的边界；
- 使用的 Agent 形态；
- 必需/可选 Tools、Skills、MCP 和 Subagents；
- RuntimeContext 字段与服务私有配置；
- 外部副作用、权限和审批要求；
- 本地运行与最小验证命令。

注册前至少证明：

1. 导入或 schema 探测不会连接外部资源；
2. `get_agent` 是异步函数并返回 `Pregel`；静态实现重复调用返回同一图实例；
3. Prompt 渲染和关键 Tool schema 符合契约；
4. 私有 Middleware 的关键分支有 focused test；
5. 动态 `get_agent` 的非执行路径不会创建 Sandbox/MCP/数据库连接；
6. Skills 目录和 `SKILL.md` 可被 Deep Agents 发现；
7. Subagents 的工具、Middleware、Skills 和权限没有错误依赖主 Agent 隐式继承；
8. 启用 Subagent 的服务能够通过 namespace / tool call ID 区分主 Agent 与 Subagent 事件；
9. 远程流对敏感 Tool 参数和结果完成授权、裁剪与脱敏。

测试优先使用 fake model、fake tool 和本地 backend，不把真实 LLM 调用作为目录规范的
基础验收。

## 10. 明确禁止的结构

- 每个 Agent 复制一套公共超时、重试、观测和 Tool error middleware；
- `graphs/<graph_id>.py`、Agent 组合根、`workflow.py` 三处都在装配 Agent；
- 空的 `helpers.py`、`utils.py`、`base.py`、`interfaces.py`；
- 只有一个实现的 factory/strategy/adapter 抽象；
- 在 `tools.py` 中存放 Skills，或把 Tool 实现写进 `SKILL.md` 代替受控执行；
- 在 module global 保存用户、租户、thread、凭据或动态工具状态；
- 业务服务之间直接导入私有模块；
- 为了目录“整齐”创建没有真实职责的文件。

## 11. 绿地落地原则

1. 本次不迁移现有 `runtime_service/agents/*` 和 `runtime_service/services/*`。
2. 现有 Agent/Services 立即视为 Legacy：不新增功能、不适配新架构、不维护兼容层。
3. 不保留旧 graph ID、旧 Python 导入路径、旧目录结构或旧运行行为作为目标约束。
4. 旧代码不复制到任何 `legacy/`、`archive/` 或 `v2/` 包；Git 历史就是代码存档。只有仍有
   解释价值的文档进入应用根 `docs/archive/`。
5. 后续从零创建 reference Agents，分别验证 `create_agent`、`create_deep_agent` 和
   `StateGraph`，同时覆盖静态 `get_agent`、动态 `get_agent`、Subagents 和顶层 `graphs/`；
   不复用任何旧 Service 实现。
6. 只有新架构下至少两个 Agent 出现真实重复，才下沉公共封装。
7. 目标结构验证并评审后，再重写 `docs/standards/` 和脚手架，旧规范同时归档。

## 12. 下一轮讨论

本轮目录、部署入口和 Subagents 规则冻结后，按以下顺序讨论公共能力：

1. `RuntimeContext`、运行选项、默认值和配置快照；
2. 公共 Middleware 生命周期、顺序和失败语义；
3. 公共 Tool registry、Capability Policy、MCP 和副作用隔离；
4. Backend、Workspace、Skills 和 Subagents 的公共接入；
5. Trace、日志、指标、成本、评测与发布门槛；
6. Platform API 与 Runtime Service 的控制面/执行面契约。

本轮不提前创建这些公共模块。后续使用全新的 reference Agent 验证目录和依赖方向，
再根据新代码中的真实重复决定公共 API 的形状。

## 13. 参考依据

- Open SWE：`agent/server.py`、`agent/graphs/agent.py`、`agent/prompt.py`、
  `agent/tools/`、`agent/middleware/`、`agent/runtime/`、`agent/skills/`
- Open SWE 学习资料：`docs/agent-engineering-learning/03-agent-factory-and-context.md`
- Open SWE 学习资料：`docs/agent-engineering-learning/04-tools-and-middleware.md`
- Open SWE 学习资料：`docs/agent-engineering-learning/15-static-and-dynamic-graphs-zh.md`
- LangChain Docs：`/oss/python/langchain/agents`、`/oss/python/langchain/middleware/overview`
- Deep Agents Docs：`/oss/python/deepagents/overview`、`/oss/python/deepagents/skills`
- Deep Agents Docs：`/oss/python/deepagents/subagents`、`/oss/python/deepagents/backends`
- Deep Agents Docs：`/oss/python/deepagents/streaming`、`/oss/python/deepagents/event-streaming`
- LangSmith Docs：`/langsmith/graph-rebuild`、`/langsmith/cli`
- 本仓库：`docs/knowledge/10-production-agent-platform-roadmap.md`
