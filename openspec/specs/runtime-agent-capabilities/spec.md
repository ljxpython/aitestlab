# runtime-agent-capabilities Specification

## Purpose

定义 Runtime Agent Service 对 Tool、MCP、Backend、Skills 和 Subagents 的最小显式接入边界。

## Requirements

### Requirement: Service 必须显式装配并限制 Tool

Agent Service SHALL 在自身组合根直接声明 Tool 列表，Runtime Policy MUST 同时约束模型可见 Tool 与执行前 Tool 名称。未声明、未授权或名称冲突的 Tool MUST 在产生外部副作用前失败。

#### Scenario: 只读 Tool 正常执行
- **WHEN** Service 显式装配一个已在 Policy allowlist 中的只读 Tool
- **THEN** 模型可以看到该 Tool，执行边界允许调用并返回结果

#### Scenario: 未授权 Tool 被拒绝
- **WHEN** 模型请求未在 Service Policy 中的 Tool
- **THEN** Runtime 在 Tool handler 前拒绝调用

### Requirement: MCP Tool 必须在 Service 内显式加载

MCP tools SHALL 在 Service 组合根构图前通过 `MultiServerMCPClient.get_tools()` 加载并过滤；凭据 MUST 只在服务端解析；MCP Tool 名称冲突 MUST 立即失败，不能静默覆盖。

#### Scenario: MCP Tool 被加载
- **WHEN** Service 通过 MCP Adapter 从 MCP Server 获取工具
- **THEN** 工具被显式传给 Agent，且不需要 Platform API

#### Scenario: MCP 名称冲突
- **WHEN** 两个 MCP 来源返回相同暴露名称
- **THEN** 构图失败并返回稳定错误，不创建部分 Agent

### Requirement: Deep Agent 能力必须保持显式边界

使用 `create_deep_agent` 的 Service SHALL 显式声明 Backend、Skills 和 Subagents。Subagent MUST 由父 Service 明确提供工具和模型，不得因默认继承扩大权限。

#### Scenario: Thread Backend 隔离
- **WHEN** 两个 Thread 使用 Backend
- **THEN** 每个 Thread 只能读取和写入自己的 Backend 状态

#### Scenario: Skill 按需可见
- **WHEN** Service 声明 bundled Skill source
- **THEN** Skill 元数据可被 Agent 发现，完整内容按 Deep Agents 机制按需加载

#### Scenario: Subagent 缩权
- **WHEN** 父 Agent 委派给显式 Subagent
- **THEN** 子 Agent 只能使用声明的模型、工具和 Skill，不能调用父级未授予能力

### Requirement: 能力 Demo 必须保持标准 Service 入口

每个能力 Demo SHALL 提供 `async def get_agent(config: RunnableConfig) -> Pregel`、README、独立测试和 `graphs/<graph_id>.py` 导出。introspection 和 fake model 测试 MUST 不连接真实 Sandbox、外部 MCP 或 Platform。

#### Scenario: Demo Graph 可加载
- **WHEN** LangGraph 从 Demo 配置导入任一能力 Graph
- **THEN** 返回 `Pregel` 且 graph ID 与导出路径一致

#### Scenario: 资源失败关闭
- **WHEN** Backend 或 MCP 初始化失败
- **THEN** Service 返回明确错误，不切换到其他 Thread、目录或工具集合
