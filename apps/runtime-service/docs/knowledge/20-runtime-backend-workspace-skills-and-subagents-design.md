# Runtime Backend、Workspace、Skills 与 Subagents 接入设计（Draft）

> 文档类型：Draft
>
> 状态：讨论结论，暂不替代 `docs/standards/` 下的现行规范
>
> 关联文档：`11-agent-service-directory-architecture.md`、
> `12-runtime-context-and-local-debug-architecture.md`、
> `13-runtime-service-target-code-layout.md`、
> `14-runtime-contracts-and-resolution-design.md`、
> `15-runtime-middleware-lifecycle-and-failure-semantics.md`、
> `19-runtime-tool-capability-mcp-and-side-effect-design.md`
>
> 冻结范围：Backend 选择、Workspace 生命周期、Skills 挂载和 Subagent 装配边界
>
> 暂不展开：具体 Sandbox Provider、用户/组织 Skill 管理 API、独立 Subagent Run、代码实现

> R6 范围决策（2026-09-02）：Sandbox/远程 MCP 的真实 Provider 验收、Langfuse/OTLP 生产故障矩阵、
> 真实回滚演练、Platform 灰度和性能 SLO 均明确 `deferred`。这些延期项不改变本文对职责边界的定义。

## 1. 本轮结论

Runtime Service 不建设公共 `BackendManager`、`WorkspaceRegistry`、`SkillProvider`、
`SubagentRegistry` 或万能资源 Builder。

这四类能力的“公共接入”只包含共同约定、可信输入和安全边界。每个 Agent Service 继续在
`agent.py/get_agent()` 中使用 Deep Agents 官方类型显式装配实际能力：

```text
Runtime 公共层
  RuntimeContext / RuntimePolicy / RuntimeConfig / Middleware
          |
          v
Service 组合根 agent.py:get_agent()
  显式选择 Backend / Workspace / Skills / Subagents
          |
          v
Deep Agents 原生能力
  StateBackend / CompositeBackend / SandboxBackend / SubAgent
```

首期冻结以下规则：

1. 普通 `create_agent` 不引入 Backend。
2. 没有真实文件或代码执行需求的 `create_deep_agent` 使用默认 `StateBackend`。
3. 只有明确需要 Shell、Git、编译或真实文件的 Service 才接入 Sandbox。
4. Workspace 是 Backend 暴露的受控路径空间，不设计新的公共 `Workspace` 类。
5. 首期只支持 Service Bundled Skills，并强制只读。
6. Subagent 的 Prompt、业务 Tools、Skills、Middleware 和高风险权限由 Service 显式声明；
   Deep Agents 内置 Tool 另行显式审计和收缩。
7. Service 声明最大能力，Runtime Policy 和 Middleware 只能继续收缩，不能扩权。
8. 两个以上 Service 出现相同、稳定的 Sandbox 生命周期代码后，才提取具体公共 helper。

### 1.1 R6 中四类资源的责任边界

Sandbox 和远程 MCP 是 Deep Agents/Runtime Service 的资源能力，不是 GraphHarbor 的业务能力。
Runtime Service 负责 Provider/client 的创建、Thread binding、重连、Tool Policy、配额、清理和
Provider-specific failure handling；GraphHarbor 只负责通用 Run、Thread、Checkpoint、事件、队列、
Worker lease，以及保存和恢复不透明的 resource binding。

本轮只验收了本地 Workspace 和本地 Streamable HTTP MCP 的真实链路。真实 Sandbox Provider、任意
远程 MCP、Langfuse/OTLP 生产故障、真实 rollback、Platform 灰度和性能 SLO 均为 `deferred`，不能
因为 GraphHarbor 已通过 Durable Core 验收就提前扩展为生产承诺。只有后续最小契约证明 GraphHarbor
丢失通用 binding、context 或生命周期语义时，才在 GraphHarbor 创建独立变更。

## 2. Open SWE 的真实设计

Open SWE 是 Coding Agent，因此它的 Backend 和 Workspace 比普通业务 Agent 复杂，但其中有四个
通用思想值得借鉴。

### 2.1 Thread 与 Sandbox 绑定

`agent/server.py:ensure_sandbox_for_thread()` 按 `thread_id` 创建或重连 Sandbox：

1. 进程内有缓存时先复用并检查；
2. Thread metadata 有 Sandbox ID 时重新连接；
3. 两者都没有时创建并在初始化成功后写入 metadata。

进程内缓存只用于加速和重连，Thread metadata 才是可跨进程恢复的资源绑定。Open SWE 对失败
进行了重要区分：

- Sandbox 已删除：允许创建新的 Sandbox 并更新绑定；
- Sandbox 仍存在但暂时不可达：默认直接失败；
- 只有工作区完全可重新生成的只读场景，才允许显式替换不可达 Sandbox。

不能把“暂时不可达”和“已不存在”混成同一种自动重建。静默换成空 Workspace 会丢失 Agent
尚未提交或导出的工作成果，比明确失败更危险。

### 2.2 CompositeBackend 组合资源空间

Open SWE 以 Thread Sandbox 作为默认 Backend，再将不同 Skill 来源挂到独立路径：

```text
default                -> Thread Sandbox
/skills/               -> Bundled Skills
/user-skills/          -> User Skills Store
/organization-skills/  -> Organization Skills Store
```

Deep Agents 的 `CompositeBackend` 已经解决路径路由问题。本项目不再围绕它创建一套 Backend
配置 DSL 或资源插件系统。

### 2.3 Skills 只读

Open SWE 将 Bundled、User 和 Organization Skills 分开路由，并用自定义 `ReadOnlyBackend`
阻止 Agent 修改 Skill 来源。Skill 修改由独立管理 Tool 完成，不通过 Agent 读取 Skill 的 Backend
直接写入。

当前 Deep Agents Python 已提供 `FilesystemPermission`。本项目首期优先使用官方 Permission 对
`/skills/**` 拒绝写入，不复制 Open SWE 的只读 Backend。只有自定义 Tool 会绕过内置文件工具、
直接持有 Backend 时，才评审增加 Backend 层只读包装。

### 2.4 Subagent 显式缩权

Open SWE 的 General-purpose 和 Browser Subagent 都显式声明 Model、Prompt、Tools 和
Middleware。General-purpose Subagent 主动排除了 Slack、Thread 管理等只属于父 Agent 的 Tool；
Browser Subagent 只获得浏览器相关 Tool。

父 Agent 的 Middleware 不会自动完整包裹自定义 Subagent。Open SWE 因此给 Subagent 单独配置
模型超时、Provider 响应清理和工具排除。这种显式装配值得采用。

## 3. 不照搬 Open SWE 的内容

本项目不复制以下 Coding Agent 专属复杂度：

- GitHub Proxy、Git identity、Repository checkout 和环境 snapshot；
- 面向 Slack、Linear、PR、CI 的 Tool 和 Prompt；
- 所有 Agent 默认获得 Sandbox 或任意 Shell；
- Open SWE 的全局 Sandbox proxy/cache 实现；
- 首期同时支持 Bundled、User、Organization、Desktop 四类 Skills；
- 仅为了未来扩展而设计 Backend Provider Registry；
- 把临时 Subagent 提升成第二套平台 Run 状态机。

借鉴的是资源隔离、恢复语义和显式缩权，不是复制整个产品实现。

## 4. Backend 选择规则

### 4.1 普通 Agent

`create_agent` 本身不需要 Deep Agents 文件系统能力。SQL 查询、知识问答、业务操作等普通 Agent
没有文件和任务分解需求时，不引入 Backend。

```python
return create_agent(
    model=runtime.model,
    tools=tools,
    middleware=middleware,
    context_schema=RuntimeContext,
)
```

### 4.2 普通 Deep Agent

需要任务规划、长结果卸载、临时文件或 Subagent，但不需要真实主机文件和代码执行时，使用
Deep Agents 默认 `StateBackend`。文件保存在 LangGraph state 中，通过 Checkpointer 在同一
Thread 的多个 Turn 之间保留，不同 Thread 互相隔离。

没有路径路由时可以省略 `backend` 参数；需要挂载 Bundled Skills 时显式使用：

```python
CompositeBackend(
    default=StateBackend(),
    routes={
        "/skills/": FilesystemBackend(
            root_dir=SKILLS_DIR,
            virtual_mode=True,
        ),
    },
)
```

### 4.3 Workspace / Sandbox Agent

只有明确需要以下能力时才增加 Sandbox：

- 真实文件的读写和产物生成；
- Shell 命令；
- Git checkout、diff 或提交准备；
- 编译、测试或隔离代码执行。

该 Service 按需增加私有 `backend.py`：

```text
services/<service_name>/
├── agent.py
├── backend.py
├── prompts.py
├── tools.py
├── subagents.py
└── skills/
```

`backend.py` 只负责本 Service 的资源创建、重连和失败分类，不负责 Agent、Tool、Prompt 或
Middleware 装配。`agent.py` 仍是唯一组合根。

Sandbox 必须来自隔离的生产 Backend。`LocalShellBackend` 和直接宿主机 `FilesystemBackend`
只允许受控本地开发，不得用于多租户生产请求。

### 4.4 Deep Agents 内置 Tool 边界

`create_deep_agent(tools=[...])` 中的 `tools` 是追加业务 Tool，不是 Agent 的完整 Tool 集。Deep
Agents 还会根据当前 Harness 组合内置文件 Tool、`execute` 和 `task`：

- 文件 Tool 包括 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`；
- `execute` 只有 Backend 实现 `SandboxBackendProtocol` 时才能真正执行，但非 Sandbox Backend
  下仍可能对模型可见并返回不支持错误；
- `task` 用于调用同步 Subagent；没有同步 Subagent 且关闭默认 General-purpose Subagent 时才
  不暴露。

因此生产 Service 的最大能力是：

```text
Service 显式业务 Tool
  union 经 Service 确认保留的 Deep Agents 内置 Tool
  intersect RuntimePolicy
  intersect Subagent 自身限制
```

具体版本支持时，优先通过官方 `HarnessProfile.excluded_tools` 或显式
`FilesystemMiddleware(tools=[...])` 隐藏不需要的内置 Tool：

- 非 Sandbox Agent 默认排除 `execute`；
- 不使用 Subagent 的 Agent 关闭默认 General-purpose Subagent 和 `task`；
- 只读 Agent 不暴露 `write_file`、`edit_file` 等写 Tool；
- 保留写 Tool 时仍必须用 `FilesystemPermission` 约束路径。

这不是新建 Tool Registry，而是对 Deep Agents 自带能力做显式安全配置。最终名称和排除方式
必须以项目锁定版本的 API 与契约测试为准。

## 5. Workspace 定义与路径约定

Workspace 不引入公共实体类。它的定义是：

> 当前 Agent 通过 Backend 被允许访问的任务文件路径空间及其生命周期绑定。

首期只规定两个稳定路径：

```text
/workspace/  任务工作区，可读写
/skills/     Service Bundled Skills，只读
```

暂不单独定义 `/artifacts/`。当平台确实需要产物上传、下载、保留、发布和权限控制时，再把
Artifact 作为独立契约设计；首期产物仍位于 `/workspace/` 中，由具体 Service 返回明确路径。

如果只需要真实文件、不需要 Shell，可以采用官方推荐组合：

```python
CompositeBackend(
    default=StateBackend(),
    routes={
        "/workspace/": workspace_backend,
        "/skills/": skills_backend,
    },
)
```

这样 Deep Agents 的 `/large_tool_results/`、`/conversation_history/` 等内部文件仍留在
`StateBackend`，不会混入业务工作区。

需要 Sandbox `execute` 能力时，具体 Sandbox 通常作为默认 Backend，Skills 仍走独立只读路由。
最终组合方式必须依据锁定版本的 Sandbox/CompositeBackend 协议做契约测试，不能假设任意路由
都能承接 `execute`。

## 6. Workspace 生命周期

### 6.1 默认绑定范围

有状态 Workspace 默认绑定 Thread，而不是单个 Run：

```text
thread_id -> sandbox_id / workspace binding
```

原因是同一 Thread 的后续 Run、interrupt/resume 和 checkpoint 恢复通常需要继续访问相同文件。
一次性批处理如果明确不需要恢复，可以由具体 Service 使用 Run-scoped 临时资源，但它不是公共
默认值。

### 6.2 事实源和缓存

- Sandbox/Workspace ID 持久化在可跨进程恢复的 Thread metadata 或等价持久化记录中；
- 进程内对象缓存只用于降低重连成本；
- worker 重启后必须能从持久化 ID 重建连接；
- 不把 Python 全局字典作为资源事实源；
- 不在 RuntimeContext、Prompt、Checkpoint message 或客户端参数中传递 Backend Credential。

### 6.3 创建和失败语义

```text
无绑定
  -> 创建并完成初始化
  -> 初始化成功后持久化 ID

有绑定且健康
  -> 重连并复用

确认已删除
  -> 允许重建并原子更新绑定

存在但不可达
  -> 明确失败，不静默替换
```

只有资源内容能够从可信来源完全重建，且 Service 明确声明 `allow_replacement` 时，才允许替换
暂时不可达的 Workspace。

### 6.4 清理

TTL、配额、空闲回收和 Provider 删除由具体 Sandbox Provider 或部署层负责。Runtime Service
需要记录资源关联和清理结果，但首期不建设通用 Workspace GC。等真实 Provider 和资源成本
确定后，再设计清理任务及 orphan reconciliation。

## 7. Skills 接入规范

### 7.1 首期来源

首期只支持随 Service 代码发布的 Bundled Skills：

```text
services/<service_name>/skills/
├── research/
│   ├── SKILL.md
│   └── references/
└── report/
    └── SKILL.md
```

`skills` 参数指向包含多个 Skill 子目录的容器路径，而不是某一个 `SKILL.md`：

```python
skills=["/skills/"]
```

Skill frontmatter 的名称和描述在启动时用于发现，完整内容仅在相关任务中按需加载。Skills 是
上下文工程资源，不是 Tool，也不是权限载体。

### 7.2 只读规则

Service Bundled Skills 必须只读：

```python
permissions = [
    FilesystemPermission(
        operations=["write"],
        paths=["/skills/**"],
        mode="deny",
    ),
]
```

规则如下：

- Agent 不能修改随代码发布的 Skill；
- Skill 不能因为被加载而获得额外 Tool、Backend 或身份权限；
- Skill 路径由 Service 代码声明，RuntimeContext 不接受任意路径；
- Skill 内容不允许携带 Secret；
- 修改 Skill 走代码发布流程，而不是 Agent 自修改；
- 只读约束必须由 Permission 或 Backend 强制，不能只写在 Prompt 中。

### 7.3 User / Organization Skills

首期不实现 User Skills 和 Organization Skills。只有平台出现以下完整需求时才增加：

- Skill 创建、审核、版本、发布和回滚；
- tenant/user namespace 隔离；
- 共享 Skill 的 prompt injection 和内容治理；
- 平台管理 API 和审计；
- StoreBackend 的生产持久化与迁移。

届时优先通过 `CompositeBackend + StoreBackend` 增加显式路径，不改变 Service 的
`get_agent()` 组合根，也不引入动态 Skill 插件系统。

## 8. Subagent 接入规范

### 8.1 目录和定义

Subagent 是 Top-level Agent 的内部委派单元，不进入 `langgraph.json`：

```text
services/<service_name>/
├── agent.py
├── subagents.py       # 1～3 个简单 Subagent
└── subagents/         # 数量较多或实现复杂时才改用目录
```

简单 Subagent 使用 Deep Agents `SubAgent` 描述；需要已有 `create_agent` 或 `StateGraph` 时使用
`CompiledSubAgent`，不再创建第二套封装协议。

### 8.2 显式最大能力

每个生产 Subagent 显式声明：

- `name` 和可操作的 `description`；
- 完整 `system_prompt`；
- 最大 Tool 列表；
- Skill 来源；
- Subagent 自己需要的 Middleware；
- 高风险场景的 filesystem permissions / interrupt 规则；
- 只有确有成本、性能或能力差异时才覆盖 Model。

```python
def research_subagent(model: BaseChatModel) -> SubAgent:
    return {
        "name": "researcher",
        "description": "Research the requested topic and return cited findings.",
        "system_prompt": RESEARCH_PROMPT,
        "model": model,
        "tools": [web_search, read_document],
        "skills": ["/skills/research/"],
        "middleware": [ModelCallTimeoutMiddleware(...)],
        "permissions": RESEARCH_PERMISSIONS,
    }
```

生产代码不通过省略字段来隐式获得父 Agent 的全部业务能力。`tools` 字段仍不代表 Deep Agents
内置文件、`execute` 和 `task` Tool 的完整集合，Subagent 必须结合 Harness、Filesystem
Middleware 和 Permission 一并审计。

### 8.3 Deep Agents 继承语义

锁定版本实现前必须用契约测试确认，当前官方 Python 文档给出的规则是：

| 能力 | 自定义 Subagent 默认行为 | 本项目规则 |
| --- | --- | --- |
| Prompt | 不继承 | 必须显式声明 |
| Tools | 未填写时继承父 Agent | 生产代码显式填写完整子集 |
| Model | 默认继承 | 无差异时允许继承 |
| Middleware | 不继承父 Agent 自定义栈 | 显式声明必要项 |
| Skills | 不继承 | 显式声明所需来源 |
| Permissions | 默认继承，子配置可替换 | 高风险 Subagent 显式收缩 |

Deep Agents 内置 General-purpose Subagent 会继承主 Agent Skills。使用内置行为时必须通过锁定
Python 版本的契约测试确认；自定义命名 Subagent 不依赖该隐式行为。

### 8.4 权限关系

```text
Service 代码声明父 Agent 最大能力
        intersect
RuntimePolicy / 本次 Run 允许能力
        intersect
Subagent 显式业务 Tool、内置 Tool、Skill 和 Workspace 权限
        =
Subagent 本次实际能力
```

Subagent 只能缩小父 Agent 的有效能力，不能通过自己的定义重新获得父 Run 已被 Policy 禁止的
Tool、Workspace 路径或管理权限。授权既要影响模型可见 Tool，也要在 Tool 执行前复核。

高风险 Subagent 默认使用更小 Tool 集和只读 Workspace。父 Agent 专属的通知、Thread 管理、
管理员、Secret 管理和外部写操作不能因为“方便”传给通用 Subagent。

## 9. Subagent 运行语义

Deep Agents 通过内置 `task` Tool 调用 Subagent。默认语义是：

- 每次委派使用新的临时上下文；
- Subagent 完成后向父 Agent 返回一次最终结果；
- Subagent 名称进入消息 metadata 和 stream namespace，可用于展示调用细节；
- Subagent 仍属于同一个父 Run；
- cancel、checkpoint、interrupt 和 resume 由父 Run 统一管理；
- Subagent 没有独立的平台 Run ID、版本、SLA 或资源生命周期。

Deep Agents 当前也提供远程/后台 `AsyncSubAgent`，但它会引入启动、查询、更新、取消和远程
Graph 的另一套任务生命周期。首期不采用 `AsyncSubAgent`，避免与平台 Durable Run 和控制面
形成两个事实源。后续若出现真实后台委派需求，必须单独比较官方 AsyncSubAgent 与提升为
Top-level Service 两种方案。

如果内部 Agent 需要被独立查看、恢复、中断、授权、扩缩容或发布，必须提升成新的 Top-level
Service，而不是继续作为 Subagent：

```text
需要独立 Run 生命周期
  -> 新 Service
  -> 新 graph_id
  -> 独立 Assistant / Version / Policy
```

这与 11 号文档的“单入口、多智能体 Service”保持一致。

## 10. Agent Service 装配示例

不需要 Sandbox 的 Deep Agent：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    runtime = await resolve_runtime_config(config, defaults=DEFAULTS)
    tools = [web_search, read_document]

    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": FilesystemBackend(
                root_dir=SKILLS_DIR,
                virtual_mode=True,
            ),
        },
    )

    return create_deep_agent(
        model=runtime.model,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        backend=backend,
        skills=["/skills/"],
        subagents=[research_subagent(runtime.model)],
        middleware=service_middleware(runtime),
        permissions=FILESYSTEM_PERMISSIONS,
        context_schema=RuntimeContext,
    )
```

需要 Thread Sandbox 的 Agent 只增加一处动态资源解析：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    runtime = await resolve_runtime_config(config, defaults=DEFAULTS)
    sandbox = await get_thread_sandbox(config)
    backend = CompositeBackend(
        default=sandbox,
        routes={"/skills/": bundled_skills_backend()},
    )

    return create_deep_agent(
        model=runtime.model,
        tools=[read_workspace, run_tests],
        backend=backend,
        skills=["/skills/"],
        subagents=[reviewer_subagent(runtime.model)],
        middleware=service_middleware(runtime),
        permissions=FILESYSTEM_PERMISSIONS,
        context_schema=RuntimeContext,
    )
```

伪代码中的 `get_thread_sandbox`、`bundled_skills_backend` 和 `service_middleware` 都是 Service
私有普通函数，不是公共 Builder。若 schema/introspection 请求不是一次真实执行，它不得创建
Sandbox 或建立外部连接；具体判断方式必须结合锁定 Agent Server 版本验证。

## 11. 公共 Runtime 的责任边界

公共 Runtime 继续负责：

- 解析可信 actor、tenant、project、thread 和 RuntimePolicy；
- 提供不可伪造的 Service 配置快照；
- 在模型调用和 Tool 执行阶段收缩 Tool 能力；
- 传播 request/run/thread/trace 关联信息；
- 对资源解析失败形成稳定错误分类和最终 Run 状态。

公共 Runtime 不负责：

- 根据字符串创建任意 Backend；
- 扫描或注册 Workspace Provider；
- 从 RuntimeContext 接收 Skill 路径或 Subagent 定义；
- 自动把父 Agent 的全部 Tool 复制给 Subagent；
- 为所有 Service 创建 Sandbox；
- 管理具体仓库 checkout、Git 身份或编译命令；
- 把临时 Subagent 伪装成独立 Durable Run。

## 12. 静态与动态 Agent Factory

Backend 设计不改变 11 号文档已经确定的 factory 原则：

- 仅使用 `StateBackend`、固定 Bundled Skills 和静态 Subagents 时，Graph 可以静态编译并缓存；
- 每个 Thread 必须创建或重连独立 Sandbox 时，`get_agent(config)` 可以动态装配该资源并返回图；
- 动态 Model、Prompt 和 Tool 可见性仍应通过 Runtime resolver / Middleware 处理，不足以成为
  每次重编译 Graph 的理由；
- 动态 factory 不允许改变公开 graph ID、输入 schema 或安全边界；
- schema/introspection 路径不得产生昂贵或有副作用的资源。

## 13. 验证要求

实施时至少验证：

1. `StateBackend` 文件在同一 Thread 跨 Turn 保留，不同 Thread 互相隔离；
2. worker 重启后可从持久化 ID 重连同一 Sandbox；
3. 暂时不可达的 Workspace 不会被静默替换；
4. 已删除 Workspace 的重建会原子更新绑定；
5. `/skills/**` 的写入和编辑被代码级权限拒绝；
6. RuntimeContext 不能注入任意 Backend、Skill 路径或 Subagent；
7. Deep Agent 和 Subagent 的业务 Tool 与内置 Tool 都符合显式允许范围；
8. Subagent 的 Middleware、Skills 和 Permission 行为与锁定 Deep Agents 版本一致；
9. 父 Run cancel、interrupt/resume 和 stream 能正确覆盖 Subagent 调用；
10. stream event 能通过 namespace/name 区分父 Agent 和 Subagent；
11. schema/introspection 不创建 Sandbox 或建立外部连接；
12. 多租户生产链路不使用宿主机 LocalShellBackend。
13. 非 Sandbox Agent 不向模型暴露可执行的 `execute` 能力；
14. 不需要委派的 Agent 不暴露默认 General-purpose Subagent 或 `task`。

## 14. 首期明确不设计

- Backend Registry 或 Backend 配置 DSL；
- Workspace Manager、Workspace Registry 或通用 GC；
- Skill Provider 插件系统；
- User/Organization Skill 管理和动态发布；
- RuntimeContext 动态上传 Skill 或 Subagent；
- Subagent Registry、自动扫描或动态安装；
- 首期使用远程/后台 `AsyncSubAgent`；
- 独立 Subagent Run 状态机；
- 所有 Agent 默认 Sandbox；
- 通用 Repository、Git、PR 或 CI 抽象；
- 为单个 Service 提前提取公共 Sandbox Factory。

## 15. 后续实施触发条件

只在真实重复出现后增加公共代码：

| 触发证据 | 可以评审的最小抽取 |
| --- | --- |
| 两个 Service 使用相同 Sandbox Provider 和恢复语义 | `runtime/sandbox.py` 的具体连接 helper |
| 平台正式支持 User/Organization Skills | StoreBackend 路由和 namespace helper |
| 多个 Service 重复同一只读 Skills 装配 | 一个返回 Backend/Permission 的小函数 |
| Subagent 需要独立恢复、取消、版本和 SLA | 提升为 Top-level Service，不扩展 Subagent |

没有这些证据时继续在 `get_agent()` 中直接使用 Deep Agents 官方能力。

## 17. R4 Harness 对齐审核（2026-08-31）

本表只审计 R4 在本文定义的 Backend、Workspace、Skills 和 Subagent 边界。`✅` 只表示该行要求
已有代码和可失败验证；`StateBackend`、fake model 和进程内 graph 只能证明 local/composition，
不能证明跨 Worker Durable、真实 Sandbox 或生产租户隔离。

| Requirement | 要求 | 是否实现 | 实现位置 | 测试/验证位置 | 真实调用案例与缺口 | Open SWE 取舍 |
| --- | --- | --- | --- | --- | --- | --- |
| `20-R4-001` | Deep Agent 显式使用 `create_deep_agent`、Bundled Skill 和 `StateBackend` | ✅ | `services/deep_agent_demo/agent.py:46-51`；`skills/runtime-notes/SKILL.md` | `tests/services/test_r4_capability_demos.py:27-30,48-50`；R4 定向测试 `10 passed` | graph 真实编译并出现 `SkillsMiddleware.before_agent`；未执行真实 Skill 任务 | 复用 Deep Agents 官方构造，不建公共 Deep Agent Factory |
| `20-R4-002` | Subagent 显式声明 prompt、model、Tool 子集，不继承父 Agent 全部业务能力 | ❌ | `services/deep_agent_demo/agent.py:39-45` 有 `tools=[]` 声明 | 当前测试未断言 Subagent 配置、调用结果或工具集合 | 代码看似缩权，但没有真实委派案例和失败断言，不能把它算完成 | 借鉴 Open SWE 的显式缩权；不复制其 coding-agent Subagent 业务 Tool |
| `20-R4-003` | 真实 graph 覆盖 `stream_subgraphs`、namespace 和 Subagent 事件投影 | ❌ | 当前无事件投影或专项 stream 适配 | 当前无 Subagent graph invocation/stream 测试 | 只验证 graph 节点存在，未证明子图事件可区分 | 保留 Deep Agents 原生 namespace；需要真实展示需求后再加最小适配 |
| `20-R4-004` | 同一 Thread 跨 Turn 保留 StateBackend 文件，不同 Thread 互相隔离 | ❌ | `services/backend_demo/agent.py:37-40` 每次构图创建进程内 `StateBackend` | `tests/services/test_r4_capability_demos.py:72-75` 只断言 graph 对象不同；无文件跨 Turn 测试 | 没有实际读写、thread_id、checkpoint 或跨 Thread 断言 | 借鉴 Open SWE Thread 绑定语义；不把进程内对象误当持久化事实源 |
| `20-R4-005` | Bundled Skills 挂载在受控路径并由代码级权限禁止写入 | ❌ | `deep_agent_demo/agent.py:29,49` 只传 Skill 目录，无 `FilesystemPermission`/只读 Backend | 当前无 `/skills/**` 写入、编辑拒绝测试 | 路径存在不等于只读；Agent 仍可能通过内置文件 Tool 改写，需锁定版本契约测试 | 借鉴 Open SWE `ReadOnlyBackend` 原则，优先使用官方 Permission |
| `20-R4-006` | Backend 按 Thread 动态创建/重连 Workspace，失败不静默切换目录 | ❌ | `backend_demo/agent.py:31-46` 无 thread-scoped binding、workspace path 或 reconnect | `tests/services/test_r4_capability_demos.py:78-86` 只模拟 `create_deep_agent` 抛错 | 初始化异常会传播，但真实 Backend 不可达、已删除和替换语义没有实现 | 借鉴 `ensure_sandbox_for_thread()` 的失败分类，不复制全局 Sandbox cache |
| `20-R4-007` | worker 重启后按持久化资源 ID 重建 Workspace，并有清理/TTL 证据 | ❌ | 当前无 `backend.py`、持久化 binding 或 cleanup owner | 当前无 worker restart、TTL、quota 或 cleanup 测试 | `StateBackend` 不能证明跨进程重建；该能力需要真实 Backend/Durable 边界 | 只在真实 Provider 重复出现后抽取最小连接 helper |
| `20-R4-008` | RuntimeContext 不能注入任意 Backend、Skill 路径或 Subagent 定义 | ❌ | R4 `get_agent()` 仅读取 test model，未接公共 Runtime Policy | 当前无恶意 context/configurable 注入测试 | 代码未读取这些字段只是局部事实，不等于 fail-closed 合同 | 不复制动态插件/Skill Provider；需把拒绝边界接入 Service |
| `20-R4-009` | Deep Agent 和 Subagent 的业务/内置 Tool 均符合显式允许范围 | ❌ | `deep_agent_demo/agent.py:46-51` 未配置内置 Tool 排除或 Permission | 当前无模型可见 Tool 列表和伪造 Tool Call 测试 | `tools=[]` 只约束业务 Subagent Tool，不能覆盖内置 filesystem/execute/task | 借鉴 Open SWE 显式排除，按当前 Deep Agents 版本补 `HarnessProfile`/middleware 契约 |
| `20-R4-010` | 本地 Deep/Backend Demo 构图不依赖 Platform 或外部资源 | ✅ | `deep_agent_demo/agent.py:46-51`；`backend_demo/agent.py:37-40` | `tests/services/test_r4_capability_demos.py:27-30`；本地 `get_agent({})` graph probe 通过 | Deep/Backend 构图不连外部服务；MCP 单独使用本地 stdio fake；正式 introspection 端点仍未专项验证 | 不引入生产 Sandbox；保留本地可运行 Demo |
| `20-R4-011` | 不建设 Backend/Workspace/Skill/Subagent Registry、Manager 或通用 Builder | ✅ | R4 源码无公共管理层，能力均在 Service `agent.py` 显式装配 | `tests/services/test_r4_capability_demos.py:33-45`；源码目录静态检查 | 当前没有第二份资源事实源；属于设计性“不实现” | 遵守 Open SWE 取舍，只借鉴组合根显式声明 |
| `20-R4-012` | User/Organization Skills、真实 Sandbox、独立 Subagent Run 按设计后置 | ❌ | 本文 §7.3、§9、§14 | 当前无对应测试；文档明确列为首期不实现 | 这是后置项，不计入 R4 缺陷，但不能计入 R4 已实现能力 | 不提前搬入 Open SWE 的 StoreBackend、Sandbox 和 AsyncSubAgent 复杂度 |

### 17.1 本文 R4 判定

```text
Deep Agent/Skill/Subagent skeleton = local partial
Backend/Workspace isolation = not implemented
Cross-worker resource recovery and cleanup = deferred/blocked by missing provider evidence
```

当前可以确认 Deep Agent、Bundled Skill、显式 `tools=[]` Subagent 和进程内 StateBackend 的构图
骨架；不能确认 Skill 只读、Thread 文件跨 Turn、动态 Workspace、跨 Worker 重连、内置 Tool 收缩
或资源清理。因此本文对应能力不能标记为无条件完成。

## 16. 参考依据

- Open SWE `agent/server.py:ensure_sandbox_for_thread()`：Thread Sandbox 创建、重连和替换语义；
- Open SWE `agent/server.py:get_agent()`：`CompositeBackend`、Skills 和 Subagents 显式组合；
- Open SWE `agent/utils/read_only_backend.py`：Backend 层只读保护；
- Open SWE `agent/tools/user_skills.py`、`organization_skills.py`：Skill 管理与读取路径分离；
- Deep Agents Backends：`/oss/python/deepagents/backends`；
- Deep Agents Skills：`/oss/python/deepagents/skills`；
- Deep Agents Subagents：`/oss/python/deepagents/subagents`；
- Deep Agents Permissions：`/oss/python/deepagents/permissions`。

本轮只形成设计文档，不创建 Runtime 源码、不接入 Sandbox、不迁移 Legacy、不修改依赖，也不
调用 OpenSpec。

## 18. R4 Apply Evidence Update (2026-09-01)

以下表格覆盖第 17 节的旧审计结论。`StateBackend + InMemorySaver` 只证明 local 协议，不能升级为跨 Worker Durable 或 Sandbox 证据。

| Requirement | 是否实现 | 实现位置 | 测试/验证位置 | 结论与缺口 |
| --- | --- | --- | --- | --- |
| `20-R4-004` 同 Thread 跨 Turn、不同 Thread 隔离 | ✅ | `services/backend_demo/agent.py` 的 `StateBackend` + test-only checkpointer | `test_backend_workspace_survives_graph_rebuild_for_same_thread`；`test_backend_workspace_isolated_between_threads` | 同 `InMemorySaver`、重建 graph 后同 Thread 可读；不同 Thread 为 not found |
| `20-R4-005` Bundled Skill 只读边界 | ✅ | `deep_agent_demo/agent.py` 的 `/skills/**` deny Permission 和只读 Tool surface | `test_deep_agent_rejects_skill_write_before_backend_execution` | 写调用在 Runtime Tool Policy 前置拒绝，Permission 同时是代码级纵深防御；未向模型暴露 write/edit Tool |
| `20-R4-006` Backend 失败不 fallback | ✅ | `services/backend_demo/agent.py` | `test_backend_demo_does_not_fallback_after_initialization_failure` | 初始化错误传播；未切换宿主机目录或替代 Backend |
| `20-R4-009` Deep Agent 内置 Tool 受限 | ✅ | `deep_agent_demo/agent.py`；`backend_demo/agent.py`；`RuntimeConfigMiddleware` | 真 graph Tool surface、`execute`/`task` forged-call 测试 | Deep Agent 只保留 `ls/read_file/glob/grep/task`；Backend 不保留 `execute/task` |
| `20-R4-002` Subagent 实际缩权委派 | ✅ | `deep_agent_demo/agent.py` 的 `summarizer` Subagent | `test_deep_agent_performs_explicit_subagent_delegation`、`test_deep_agent_streams_subagent_namespace_and_projection` | 真实 `task` 委派、显式工具缩权和 namespace stream 证据已通过；独立 detached Subagent Run 仍不建设 |
| `20-R4-007` 跨 Worker 资源恢复、TTL/cleanup | ❌ | `workspace_demo`、`scripts/r6_workspace_acceptance.py`、`scripts/r6_workspace_cleanup.py` | Thread Workspace 跨 Worker 验收和 TTL cleanup policy 测试已通过；生产 Backend/Sandbox provider 的清理、配额和完整资源矩阵仍 blocked |

本轮状态：`R4 local-complete / production-chain-blocked`；Thread Workspace 的 durable 恢复和隔离
已由 R6 真实链路补齐，生产 Sandbox、provider-wide cleanup、配额原子性和任意远程资源恢复仍未完成。

## 19. R6 Harness 对齐更新（2026-09-02）

本节覆盖前述 R4 历史审计中的过时结论。`✅` 只表示当前行有对应代码和可失败验证；外部 Provider
和 Platform 生产切换仍按证据边界单独判断。

| Requirement | 是否实现 | 实现位置 | 测试/验证位置 | 当前证据与未覆盖边界 |
| --- | --- | --- | --- | --- |
| `20-R6-001` Thread Workspace 按 tenant/project/thread 隔离并跨 Worker 恢复 | ✅ | `services/workspace_demo/agent.py`；`runtime/resource_bindings.py`；GraphHarbor workspace binding | `scripts/r6_workspace_acceptance.py`；`tests/services/test_workspace_demo.py` | 真实 API、替代 Worker、PostgreSQL/Redis 下同 Thread 读回成功，双 Thread/tenant 隔离和不可用根 fail-closed 通过 |
| `20-R6-002` Workspace 单文件、文件数量、总字节数、路径和符号链接边界 | ✅ | `services/workspace_demo/policy.py`；部署 env/Compose | `tests/services/test_workspace_policy.py`：大小、数量、总配额、越界、符号链接、并发写入 | Runtime 侧策略和同一 Thread 共享卷上的锁内配额 mutation 通过；跨主机 provider 原子配额记账仍依赖 Backend 能力 |
| `20-R6-003` Workspace TTL/cleanup 只清理过期非活跃 Thread | ✅ | `services/workspace_demo/policy.py`；`scripts/r6_workspace_cleanup.py` | `test_cleanup_removes_only_expired_inactive_threads`；cleanup CLI dry-run/apply | 只接受持久化 Thread 事实源提供的 active IDs，默认 dry-run；生产任务的调度、租约和 provider 删除仍属部署层 |
| `20-R6-004` MCP binding 跨 Worker/provider 重启恢复并失败闭合 | ✅ | `services/mcp_demo/loader.py`；`graphs/mcp_probe.py` | `scripts/r6_mcp_acceptance.py`；`tests/services/test_resource_reconnect.py` | 独立 Streamable HTTP provider 的 discovery、调用、Worker 替换、provider 重启及缺 binding/不可达失败通过；任意远程 provider SLA/凭据矩阵按 owner 决策 `deferred` |
| `20-R6-005` Deep Agent Subagent 实际委派且能力不扩大 | ✅ | `services/deep_agent_demo/agent.py`；`summarizer` SubAgent | `test_deep_agent_performs_explicit_subagent_delegation`；`test_deep_agent_streams_subagent_namespace_and_projection`；观测 callback 测试 | 官方 `task` 真实返回子 Agent 结果，子 Agent 使用显式缩权配置；v2 stream 暴露非空 namespace 和 `summarizer` 事件；跨进程 detached Subagent 未实现 |
| `20-R6-006` Sandbox 按 Thread binding 恢复并失败闭合 | ❌ | 无实现 | 无可执行验收 | 不保留 LangSmith 专用 Adapter；真实 Provider 选型、Thread binding、跨 Worker/cleanup/quota 验收按 owner 决策 `deferred` |
| `20-R6-007` Backend/MCP/Sandbox 资源成功、异常、取消、超时和 shutdown 后释放 | ❌ | Runtime adapter 与 GraphHarbor 生命周期 | 当前仅本地 MCP provider 和缺资源失败证据 | MCP 本地连接生命周期已有验收；真实远程 MCP/Sandbox provider 的释放、租约和清理按 owner 决策 `deferred` |

当前 R6 结论：`Workspace/MCP/Subagent = chain-evidenced`；`Sandbox/provider-wide cleanup = deferred_external_provider`。
不能将前述历史表中的 R4 skeleton 缺口继续当成代码不存在，也不能将外部 Provider 未验收写成生产完成。

## 20. 四类资源与 GraphHarbor 的责任边界（2026-09-02）

本设计把 Workspace、Backend、Sandbox、MCP 拆成四个不同问题。GraphHarbor 是通用 Agent
Server 和 Durable 执行面，不是当前项目的资源 Provider、Tool Registry 或 Workspace Manager。

| 资源 | 定义 | 对 GraphHarbor 的影响 | 应由谁解决 | 当前证据 |
| --- | --- | --- | --- | --- |
| Workspace | Thread 可访问的受控文件路径空间，默认边界为 `tenant/project/thread` | 需要保留不透明 binding，保证同 Thread 跨 Worker 恢复且事件不串线 | Runtime Service + Backend/Sandbox Provider | Runtime Workspace chain 已有跨 Worker/隔离证据；生产 cleanup/provider 配额按 owner 决策 `deferred` |
| Backend | Agent 进行 `ls/read/write/edit/glob/grep/execute` 的文件操作适配器 | 需要按 Run 调用 graph factory、保留 `RunnableConfig`、释放 graph 级资源 | Service `agent.py` 组合根 + Deep Agents 官方 Backend | `StateBackend`、Bundled Skills 和 Tool surface 已有本地/链路证据；不建设公共 Registry |
| Sandbox | 带隔离文件系统、Shell、网络和资源限制的外部执行环境 | 只需让 Worker 替换后重连同一 binding，并把 provider 不可用映射成唯一失败 | Runtime adapter + 外部 Sandbox Provider | 目前只有 adapter fail-closed；真实 provider、cleanup、quota 和跨 Worker 恢复未通过 |
| MCP | Agent 连接外部 Tool Server 的协议和 session 生命周期 | 需要支持 per-Run factory、binding 恢复和 Tool/MCP 失败事件 | Runtime MCP loader + Provider | 独立 Streamable HTTP provider 的 discovery、Worker/provider 重启和失败闭合已通过；任意远程 SLA 未验收 |

### 20.1 哪些内容不要放进 GraphHarbor

- 不在 GraphHarbor 中决定 `tenant/project/thread` 目录命名、TTL、配额或清理调度。
- 不在 GraphHarbor 中实现当前项目的 `Backend Registry`、`Sandbox Provider Registry`、MCP
  凭据中心或 Tool Policy。
- 不把 Backend credential、MCP token、Sandbox client、绝对路径或 Python 对象写进
  `RuntimeContext`、Checkpoint message 或客户端 payload。
- GraphHarbor 只保存和传递通用的、经过签名或持久化保护的 opaque resource binding，并负责
  Run、Checkpoint、事件、Worker lease 和终态语义。

### 20.2 Open SWE 对本设计的直接参考

Open SWE 的 `agent/server.py:ensure_sandbox_for_thread()` 和
`agent/utils/sandbox_state.py` 可直接借鉴 Thread metadata 绑定、进程缓存仅加速、Worker
重建重连，以及“已删除”与“暂时不可达”分开的失败语义。`CompositeBackend` 和
`ReadOnlyBackend` 可借鉴 Workspace/Skills 分路和只读保护；`agent/utils/langfuse.py` 可借鉴
graph 入口 Callback、脱敏和 exporter fail-soft；`MultiServerMCPClient` 可借鉴 async session
关闭。

不复制 Open SWE 的 GitHub/Slack/Linear/PR/CI 工具、全局 Sandbox Provider、任意 Shell、
User/Organization Skill 管理和 detached Subagent Run。当前项目的资源选择和安全策略仍在
各 Service 的 `get_agent()` 组合根内显式声明。
