## MODIFIED Requirements

### Requirement: Service 必须显式装配并限制 Tool

Agent Service SHALL 在自身组合根直接声明 Tool 列表，Runtime Policy MUST 同时约束模型可见 Tool
与执行前 Tool 名称。该约束 MUST 覆盖 Service 业务/MCP Tool 和 Deep Agents 由 middleware 注入的
内置 Tool。未声明、未授权或名称冲突的 Tool MUST 在产生外部副作用前失败；RuntimeContext 不得
注入 Tool 实现、MCP connection 或替代 Backend。

#### Scenario: 只读 Tool 正常执行
- **WHEN** Service 显式装配一个已在 Policy allowlist 中的只读 Tool，且该 Tool 在 RuntimeContext 中被允许
- **THEN** 模型可以看到该 Tool，执行边界允许调用并返回结果

#### Scenario: 未授权 Tool 被拒绝
- **WHEN** 模型请求未在 Service Policy 中的业务、MCP 或 Deep Agents 内置 Tool
- **THEN** Runtime 在 Tool handler 前拒绝调用，且不切换到其他同名实现

#### Scenario: 内置 Tool 通过真实 graph 被收缩
- **WHEN** Deep Agent Service 构图并声明只读或受限的内置 Tool 集合
- **THEN** 真实 graph 的模型 Tool surface 不包含未声明的 `execute`、写文件或 `task`，伪造调用也在执行前失败

### Requirement: MCP Tool 必须在 Service 内显式加载

MCP tools SHALL 在 Service 组合根构图前通过 `MultiServerMCPClient.get_tools()` 加载并过滤；凭据
MUST 只在服务端解析；MCP Tool 名称冲突 MUST 立即失败，不能静默覆盖。MCP 连接失败、必需/可选
MCP 的选择和关闭责任 MUST 有明确结果，不得回退到不同 Tool 集合。

#### Scenario: MCP Tool 被加载
- **WHEN** Service 通过 MCP Adapter 从 MCP Server 获取工具
- **THEN** 工具被显式传给 Agent，且不需要 Platform API

#### Scenario: MCP 名称冲突
- **WHEN** 两个 MCP 来源返回相同暴露名称
- **THEN** 构图失败并返回稳定错误，不创建部分 Agent

#### Scenario: 客户端不能注入 MCP 连接
- **WHEN** RuntimeContext 或普通 configurable 提供 MCP URL、command、headers、token 或 Tool 实现
- **THEN** Service 拒绝该输入，不建立该连接，也不把凭据写入 graph、checkpoint 或 trace

### Requirement: Deep Agent 能力必须保持显式边界

使用 `create_deep_agent` 的 Service SHALL 显式声明 Backend、Skills、Subagents、内置 Tool surface
和 Permission。Subagent MUST 由父 Service 明确提供工具、模型、Skill 和必要 Middleware，不得因
默认继承扩大权限。生产 Thread Workspace MUST 使用 Agent Server durable checkpointer 支撑的
Thread-scoped `StateBackend`；宿主机 `FilesystemBackend`/`LocalShellBackend` 不得作为 Web/API 生产
默认 Backend。

#### Scenario: Thread Backend 隔离
- **WHEN** 两个 Thread 使用同一 Agent Server durable checkpointer 运行 Deep Agent
- **THEN** 每个 Thread 只能读取和写入自己的 Backend 状态，Worker 重启后仍恢复各自状态

#### Scenario: Skill 按需可见且只读
- **WHEN** Service 声明 bundled Skill source
- **THEN** Skill 元数据可被 Agent 发现，完整内容按 Deep Agents 机制按需加载，Agent 写入或编辑 `/skills/**` 被代码级 Permission 拒绝

#### Scenario: Subagent 缩权
- **WHEN** 父 Agent 委派给显式 Subagent
- **THEN** 子 Agent 只能使用声明的模型、工具、Skill、Middleware 和 Permission，不能调用父级未授予能力

#### Scenario: Backend 失败不静默替换
- **WHEN** Thread Workspace 的 checkpointer/backend 不可用、scope 不一致或初始化失败
- **THEN** Service 返回稳定错误并终止构图或调用，不切换到空目录、其他 Thread 或宿主机路径

### Requirement: 能力 Demo 必须保持标准 Service 入口

每个能力 Demo SHALL 提供 `async def get_agent(config: RunnableConfig) -> Pregel`、README、独立测试
和 `graphs/<graph_id>.py` 导出。introspection 和 fake model 测试 MUST 不连接真实 Sandbox、外部
MCP 或 Platform；生产入口缺少已验证 Auth facts 时 MUST fail-closed，不能启用匿名 fake adapter。

#### Scenario: Demo Graph 可加载
- **WHEN** LangGraph 从 Demo 配置导入任一能力 Graph
- **THEN** 返回 `Pregel` 且 graph ID 与导出路径一致

#### Scenario: 资源失败关闭
- **WHEN** Backend 或 MCP 初始化失败
- **THEN** Service 返回明确错误，不切换到其他 Thread、目录或工具集合

#### Scenario: 匿名生产入口被拒绝
- **WHEN** 生产配置调用 R4 Demo `get_agent({})` 且没有显式测试 adapter
- **THEN** Service 返回 `runtime.auth.missing_principal`，不创建可执行 graph
