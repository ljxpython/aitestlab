## Context

R4 当前的三个 Service Demo 能编译，但 `deep_agent_demo`、`mcp_demo` 和 `backend_demo` 没有消费
同一套 Runtime Policy；`create_deep_agent(tools=...)` 还是追加业务 Tool，默认文件 Tool、
`task` 和可能的 `execute` 仍由 Deep Agents 组合。`backend_demo` 使用的 `StateBackend` 只有在
Agent Server 的 durable checkpointer 存在时才具有跨 Worker 的生产意义，单独在进程内构图不能作为
生产 Workspace 证据。

本变更的 owning locus 是 `apps/runtime-service`，affected chain 为：Agent Server Auth -> Service
`get_agent()` -> Runtime Resolver/Middleware -> Deep Agents/MCP Tool -> Agent Server checkpointer。
这是 B3 Governed Change，因为它改变 Tool 授权、租户隔离、持久化和 Worker 恢复语义。已加载根
`AGENTS.md`、`docs/standards/01-ai-execution-system.md`、19/20/23/24/25 号设计文档，以及锁定
`deepagents==0.7.8` 的 `create_deep_agent`、`FilesystemMiddleware`、`HarnessProfile`、
`StateBackend` API reference。

## Goals / Non-Goals

**Goals:**

- R4 三个 Demo 的组合根显式解析已验证 Runtime facts，并让同一份 resolved tool allowlist 同时约束模型可见 Tool 和执行前 Tool Call。
- 使用官方 Deep Agents 机制将内置 filesystem Tool 收缩到 Service 声明的集合；非 Sandbox Agent 不向模型暴露 `execute`，不需要委派时不暴露可执行的 `task`。
- 为 Bundled Skills 使用代码级只读约束；Subagent 明确声明自己的 Tool、Skill、Permission 和必要 Middleware。
- 将 `backend_demo` 的虚拟文件 Workspace 绑定到 LangGraph Thread：生产由 Agent Server 提供 durable checkpointer，Service 显式使用 `StateBackend`；本地用显式 `InMemorySaver` 只验证同一 Thread 跨 Turn 和不同 Thread 隔离。
- 对生产资源缺失、Backend 初始化失败、Thread scope 不一致和权限收缩失败使用 fail-closed 语义，不静默切换目录、Tool 实现或身份。
- 为真实 Agent Server/PostgreSQL/Redis/Sandbox 条件保留可执行验证入口，并在外部 entitlement 或 Provider 不可用时诚实标记 blocked/not-executed。

**Non-Goals:**

- 不使用 `FilesystemBackend` 或 `LocalShellBackend` 作为 Web/API 生产 Workspace；它们只允许受控本地开发。
- 不新增公共 Tool Registry、Backend Manager、Workspace Registry、Capability DSL、通用 Builder 或第二套 Run Coordinator。
- 不在本变更实现真实 Shell/Git/Repo 执行 Sandbox；没有已选定、隔离且可重连的 Sandbox Provider 时，代码执行能力保持关闭。
- 不把 `InMemoryStore`、`InMemorySaver` 或进程内全局字典标记为生产持久化。
- 不实现 User/Organization Skills、独立 Subagent Run、Workspace GC/配额平台或 Platform 配置 API。

## Decisions

### 1. R4 Service 复用 Runtime facts，但不引入万能构建器

每个 Service 继续在自己的 `agent.py` 中显式定义 `AgentDefaults`、Tool 名单、内置 Tool 名单、
Middleware 和 Backend。可以提取只负责解析已验证 Auth facts 的小型纯 helper，但不得把模型、Tool、
Backend、MCP 和 graph 拓扑藏进公共 Factory。`RuntimeConfigMiddleware` 的 `required_tool_names`
和 `optional_tool_names` 将包含该 Service 实际允许的业务/MCP/Deep Agent 内置 Tool；Resolver 的
交集结果是唯一的本次可见/可执行 allowlist。

生产 `get_agent` 没有 verified server user 时立即返回 `runtime.auth.missing_principal`。本地 fake
model、local facts、checkpointer 只有在带有明确 `_runtime_test_*` 标记的测试配置下可用，且这些
字段在返回 graph 前移除，不进入生产 graph 配置。

### 2. Deep Agent 内置 Tool 使用官方收缩路径

`create_deep_agent` 的 `tools=` 是追加项，不能用它排除内置 Tool。Service 将显式传入官方
`deepagents.middleware.filesystem.FilesystemMiddleware`：

- `deep_agent_demo` 只保留 `ls`、`read_file`、`glob`、`grep`，并将 `/skills/**` 的写操作拒绝；
- `backend_demo` 只在其明确需要虚拟 Workspace 写入时保留 `ls`、`read_file`、`write_file`、
  `edit_file`、`delete`、`glob`、`grep`，不接 Sandbox，因此不保留 `execute`；
- 两个 Demo 的 Subagent 都显式设置 `tools=[]`，并用自身 `FilesystemMiddleware` 和 Permission
  配置，不依赖父 Agent 默认工具继承；
- `RuntimeConfigMiddleware` 仍作为最后一道模型可见和执行前检查，防止 fake Tool Call 或恢复旧
  Run 绕过 Deep Agents 的模型侧过滤。`task` 即使由 Deep Agents 内部 middleware 构造，也必须在
  Service Policy 不允许时被 Runtime 检查拒绝。

用 `HarnessProfile` 只做 Deep Agents 默认工具/默认 general-purpose subagent 的版本兼容配置；
不使用全局注册副作用作为唯一安全边界。真正安全边界是 Service 的显式 middleware + Runtime
Policy。

### 3. Thread Workspace 使用 StateBackend + durable checkpointer

R4 的 Workspace 定义为 Deep Agents 虚拟文件状态，不是宿主机目录。`backend_demo.get_agent()`
显式传入 `StateBackend()`。生产部署不传进程内 checkpointer，由 Agent Server 统一注入已配置的
durable checkpointer；本地组合测试显式注入 `InMemorySaver`，仅用于验证协议。

因此：

```text
same thread + same Agent Server checkpointer -> same virtual Workspace
different thread -> different StateBackend state
worker restart -> Agent Server durable checkpoint reloads files
missing/mismatched thread scope -> fail-closed
```

不能用 `FilesystemBackend(root_dir=...)` 代替这条链，因为官方文档明确警告它直接暴露机器文件系统，
不适合 Web/API 多租户生产。真实文件、Shell、Git 或编译需求另需 Sandbox Provider；没有 Provider
就让 `execute` 不可见并明确报告能力未启用。

### 4. MCP 凭据和生命周期保持 Service 私有

`mcp_demo` 只从服务端固定配置构造 MCP connection，客户端 Context 不得提交 command、URL、headers
或 token。测试用本地 stdio fake 验证工具加载和名称冲突；生产 MCP 只有在凭据存储、连接超时、
required/optional 语义和关闭责任人明确后才可启用。MCP Tool 进入同一 Runtime allowlist，并在
Tool handler 前再次检查。

### 5. Workspace 生产验证分层

- **local**：`InMemorySaver` + fake model 驱动真实 Deep Agent graph，验证文件写入、同 Thread 第二
  次 Run 可读、不同 Thread 不可见、写 Skill 被拒绝、伪造 `execute/task` 被拒绝。
- **chain**：真实本地 Agent Server 使用 durable checkpointer，验证 graph 重建后同 Thread 文件仍在，
  两 Thread 隔离，服务重启不丢状态。
- **production-like**：Docker Compose 的 PostgreSQL/Redis/Worker restart、SIGTERM、备份恢复、
  TTL/清理和资源告警；若 Agent Server entitlement 或真实 Sandbox Provider 不可用，证据为 blocked，
  不以 local 结果替代。

## Risks / Trade-offs

- [Deep Agents 版本改变默认内置 Tool] -> 锁定 `deepagents==0.7.8`，直接检查 middleware tool surface，并在升级时让契约测试先失败。
- [Runtime middleware 过滤掉 Deep Agents 必需内部 Tool] -> 只允许 Service 显式声明的内置工具，测试真实 graph 的成功路径；未声明工具必须失败。
- [StateBackend 被误认为独立数据库] -> 文档、README 和验证记录明确它依赖 Agent Server checkpointer；生产测试必须走外部持久化链。
- [共享宿主机目录导致跨租户泄漏] -> 禁止生产 Filesystem/LocalShell Backend；无 Sandbox Provider 时关闭执行能力。
- [MCP client 在构图后泄漏进程资源] -> 保持 Service 私有 loader，补充 success/error/cancel/shutdown 生命周期测试；在责任人未明确前不启用远程 MCP。
- [Runtime Policy 不包含内置 Tool 名称] -> 每个 Service 的 defaults/policy/test fixture 同时列出完整允许集合，缺项在构图或 Tool handler 前失败。

## Migration Plan

1. owner 审阅 proposal、spec、design、tasks，并记录批准后才 apply。
2. 先补真实 graph 的 Policy、内置 Tool surface、伪造调用和 Skill 写入失败测试，让当前 Demo 明确失败。
3. 实现三个 Service 的 Runtime/Auth/Policy 接线和 Deep Agents 官方 Tool 收缩。
4. 实现 `backend_demo` 的 StateBackend + checkpointer 本地合同测试，再接 Agent Server durable chain 测试。
5. 运行 local、shortest chain、production-like 检查，更新 19/20/31 号文档和 `verification.md`。
6. 回滚时移除 R4 Service 接线即可；已有 checkpoint schema 不改变，若发现 schema/资源绑定不兼容则停止部署，不自动降级到宿主机目录。

## Open Questions

- 当前 Agent Server entitlement 是否能提供 R4 Demo 所需的 durable checkpointer/store 真实环境仍需 R6 环境确认。
- R4 需要真实文件/Shell 时选择哪一个 Sandbox Provider、其 Thread 绑定 API、删除/不可达分类和 TTL 所有权尚未冻结；在此之前只能完成虚拟 StateBackend Workspace。
- Deep Agents `HarnessProfile` 的 provider/model key 是否覆盖当前中转模型对象，需要以实际模型构造和契约测试确认；不能依赖猜测注册全局 profile。
