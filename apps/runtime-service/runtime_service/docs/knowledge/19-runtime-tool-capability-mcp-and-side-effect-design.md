# Runtime Tool 显式装配、Capability Policy、MCP 与副作用隔离（Draft）

> 文档类型：Draft
>
> 状态：讨论结论，暂不替代 `docs/standards/` 下的现行规范
>
> 关联文档：`11-agent-service-directory-architecture.md`、
> `13-runtime-service-target-code-layout.md`、
> `14-runtime-contracts-and-resolution-design.md`、
> `15-runtime-middleware-lifecycle-and-failure-semantics.md`、
> `20-runtime-backend-workspace-skills-and-subagents-design.md`
>
> 冻结范围：Tool 装配方式、运行时能力收缩、MCP 接入和副作用隔离
>
> Backend、Workspace、Skills、Subagents 的生命周期和装配见 20 号文档；本文不重复其设计，
> 也不展开代码实现

## 1. 本轮结论

Runtime Service 首期不建设公共 Tool Registry，不定义 `ToolSpec`、`ToolRegistration`、
`CapabilityProfile`、Tool 插件系统或通用 MCP Manager。

每个 Agent Service 采用最直接的方式：

1. 在 `tools.py` 或 `tools/` 中实现普通 Tool；
2. 在 `agent_server.py/get_agent()` 中显式导入并列出该 Agent 使用的业务 Tool；
3. 将这份列表直接传给 `create_agent`、`create_deep_agent` 或显式 `StateGraph`；使用
   `create_deep_agent` 时另行显式审计和收缩框架内置 Tool；
4. `RuntimeConfigMiddleware` 只对已经装配的 Tool 做本次可见性过滤和执行前授权复核；
5. MCP Tool 由 Service 私有 `mcp.py` 加载，在创建 Agent 前加入同一工具列表；
6. 写操作、外部副作用、管理员能力和 Sandbox 能力通过不同 Agent 的显式工具列表、HITL、
   明确 retry 名单和 Tool 自身的范围校验隔离。

一句话概括：

```text
Tool 定义归 tools.py
Tool 选择归 get_agent()
Tool 授权归 RuntimePolicy + RuntimeConfigMiddleware
Tool 执行安全归 Tool 自身 + 官方 Middleware
MCP 连接归 Service 私有 mcp.py
```

## 2. `BaseTool` 是什么

`BaseTool` 是 LangChain 提供的工具基础类型。普通函数、`@tool` 函数、`StructuredTool` 和 MCP
适配器返回的工具，最终都可以被框架作为 Tool 调用。

它是框架内部统一调用接口，不是本平台需要再封装的业务架构：

- Service 开发者通常只写普通函数或 `@tool`；
- `create_agent(..., tools=[...])` 和 `create_deep_agent(..., tools=[...])` 接受这些工具；
- 只有类型标注或框架适配代码确有需要时才直接引用 `BaseTool`；
- 本项目不围绕 `BaseTool` 再创建 Wrapper、Registration 或 Registry。

因此，文档中的架构术语统一使用“Tool”或“显式工具列表”，不把 `BaseTool` 提升为平台契约。

## 3. Open SWE 的真实做法

Open SWE 没有通用 Tool Registry。它的主要做法是：

```text
agent/tools/*.py
  -> 实现普通 Python Tool

agent/server.py:get_agent()
  -> 显式构造 static_tools
  -> 根据 local/admin/stop-summary 等场景增删工具
  -> 传给 create_deep_agent(tools=static_tools)
```

`agent/tools/__init__.py` 的延迟导入映射是大型项目的导入性能优化，不是权限 Registry，也不应
复制到首期 Runtime。我们的 Service 工具数量较少时，直接导入最容易理解。

Open SWE 的 `DynamicToolMiddleware` 是后期针对可选集成和 MCP 握手成本增加的专项优化。它让
模型先调用 `load_integration_tools`，随后才加载并绑定真实 Tool。这个机制有价值，但同时增加
Agent state、额外 Tool Call、缓存和恢复语义。首期没有测量证据，不引入。

本项目借鉴以下原则：

- Tool 显式装配，不扫描目录；
- MCP 凭证只在服务端解析；
- Tool 名称冲突立即失败；
- 写操作、管理员能力和 Sandbox 能力不进入普通 Agent；
- Tool Retry 只列出已确认可以重试的 Tool；
- 如果未来真正动态注册 Tool，模型可见性和实际执行必须同时处理。

## 4. 为什么不需要 Registry

Registry 只有在下面情况真实出现时才可能有价值：

- 多个独立 Service 必须共享并独立发布大量 Tool；
- Tool 需要在不修改 Agent 代码的情况下安装或卸载；
- Tool 来自独立远程目录，且必须统一做发现、版本和生命周期管理。

当前没有这些需求。现在引入 Registry 只会制造第二份事实源：

```text
tools.py 有一份 Tool
Registry 注册一份 Tool
AgentDefaults 再声明一份 Tool name
get_agent() 又选择一份 Tool
```

首期只保留必要的两层：

```text
get_agent() 显式工具列表        # Agent 实际具备什么能力
RuntimePolicy.allowed_tool_names # 当前调用方最多允许请求什么能力
```

`AgentDefaults.required_tool_names` 和 `optional_tool_names` 只用于运行时决议、版本摘要和严格
校验，不保存 Tool 对象，也不形成 Registry。

## 5. Capability Policy

Agent 的最大能力边界由 Service 代码决定：

```python
tools = [search_project, read_document, create_test_case]
```

对 `create_agent`，该列表就是业务 Tool 集。对 `create_deep_agent`，`tools=` 只会追加业务 Tool；
Deep Agents 还会组合文件 Tool、`execute` 和 `task`。Service 必须通过锁定版本支持的官方
`HarnessProfile.excluded_tools`、`FilesystemMiddleware(tools=[...])`、Subagent 配置和
`FilesystemPermission` 明确保留或排除这些内置 Tool。非 Sandbox Agent 默认排除 `execute`，
不使用委派的 Agent 关闭默认 General-purpose Subagent 和 `task`。

平台不能通过请求让 Agent 获得列表之外的 Tool。运行时只做收缩：

```text
get_agent() 已装配的业务 Tool + 明确保留的 Deep Agents 内置 Tool
  ∩ AgentDefaults 声明
  ∩ RuntimePolicy.allowed_tool_names
  ∩ RuntimeContext 本次 Optional Tool 选择
  = 本次模型可见 Tool
```

规则如下：

- Required Tool 不在 Policy allowlist：Run 直接失败；
- 请求了 Agent 未装配或未声明的 Optional Tool：Run 直接失败；
- 请求了 Policy 不允许的 Tool：Run 直接失败；
- 不静默裁剪非法请求，避免调用方误以为能力已经启用；
- `wrap_tool_call` 在执行前按名称再次检查，防止伪造 Tool Call 或恢复旧 Run 绕过限制；
- `RuntimeContext` 只表达“本次希望使用什么”，不能携带身份、权限或 Tool 实现。
- Runtime Policy 和执行前复核必须覆盖 Deep Agents 内置 Tool，不能只检查 Service 业务 Tool。

审批不属于 Tool allowlist。allowlist 表示调用方有资格请求 Tool；HITL 根据实际 Tool Call 和
参数决定这一次调用是否执行。

## 6. Agent Service 接入规范

基线目录保持不变：

```text
services/<service_name>/
├── agent_server.py
├── prompts.py
├── tools.py
├── schemas.py
└── README.md
```

简单 Agent 直接装配：

```python
from .tools import read_document, search_project


async def get_agent(_config: RunnableConfig) -> Pregel:
    tools = [read_document, search_project]
    return create_agent(
        model=BOOTSTRAP_MODEL,
        tools=tools,
        middleware=[
            RuntimeConfigMiddleware(defaults=DEFAULTS),
            ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT),
            ToolCallLimitMiddleware(run_limit=TOOL_CALL_LIMIT),
        ],
        context_schema=RuntimeContext,
    )
```

这是目标范式，不额外调用 `register_tools()`、`build_tool_catalog()` 或
`create_capability_profile()`。

`tools.py` 负责：

- Tool 函数和参数 schema；
- 从可信 Runtime 获取项目、用户和租户范围；
- 调用领域服务；
- 把可恢复业务错误转换为稳定结果。

`tools.py` 不负责：

- 修改 Agent 的工具列表；
- 解析 Policy；
- 创建 Middleware；
- 扫描其他模块；
- 保存全局用户身份、凭据或连接。

## 7. MCP 接入

使用 MCP 时按需增加一个 Service 私有文件：

```text
services/<service_name>/
├── agent_server.py
├── tools.py
└── mcp.py
```

`mcp.py` 只负责：

- 从服务端配置或可信凭据存储解析连接信息；
- 使用官方 `langchain-mcp-adapters` 加载 Tool；
- 只保留 Service 明确允许的远端 Tool；
- 配置连接超时并返回明确错误。

`agent_server.py` 在真实执行路径中加载并直接装配：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    mcp_tools = await load_service_mcp_tools(config)
    tools = [search_project, *mcp_tools]
    require_unique_tool_names(tools)
    return create_deep_agent(
        model=BOOTSTRAP_MODEL,
        tools=tools,
        middleware=[RuntimeConfigMiddleware(defaults=DEFAULTS)],
        context_schema=RuntimeContext,
    )
```

伪代码中的 `require_unique_tool_names` 表示组合时必须检查重名，不要求首期创建公共 helper；
一个 Service 用几行局部检查即可。第二个 Service 出现完全相同逻辑后再提取。

MCP 规则：

- 客户端不得提交 MCP URL、command、headers、token 或任意 Server 配置；
- Credential 不进入 Prompt、Tool 参数、RuntimeContext、Checkpoint 或 Trace；
- 未配置的可选 MCP 可以不加入 Tool 列表；
- Agent 必须依赖的 MCP 加载失败时，`get_agent` 明确失败；
- MCP 返回未知 Tool 时不暴露；
- 探测/schema 调用不得连接 MCP；动态 `get_agent` 必须区分真实执行路径；
- 首期不做跨 Run MCP Tool 或连接缓存；
- 首期不设计通用动态 Tool Middleware。

如果以后有证据表明 MCP 握手显著影响首 Token，或者工具数量导致模型上下文膨胀，再单独
评审 Open SWE 的 `DynamicToolMiddleware`。一旦采用真正的运行时 Tool 注册，必须同时在
`wrap_model_call` 暴露 Tool、在 `wrap_tool_call` 绑定实际执行对象。

## 8. 副作用隔离

首期不创建通用 `side_effect` 元数据模型。副作用通过代码边界和明确配置表达：

| Tool 类型 | 首期规则 |
| --- | --- |
| 只读查询 | 可以进入普通 Agent；仅对明确临时错误配置重试 |
| 项目内写操作 | 从可信 Runtime 获取 project scope；按需 HITL；默认不重试 |
| 外部写操作 | 必须考虑幂等键；通常 HITL；超时后结果不明时禁止自动重试 |
| 管理员操作 | 只装配到管理员专用 Agent 或受控运行模式 |
| Shell、Git、任意代码执行 | 只属于明确启用 Workspace/Sandbox 的专用 Agent |

执行安全不能只写在 Prompt：

- 项目、租户和用户 ID 不能信任模型参数；
- Secret 只在服务端 client/MCP 连接中注入；
- `HumanInTheLoopMiddleware` 显式列出需要审批的 Tool；
- `ToolRetryMiddleware` 显式列出确认幂等的 Tool 和可重试异常；
- `ToolErrorMiddleware` 只转换模型可以处理的预期错误；
- 写操作超时且无法确认结果时返回 `outcome=unknown`，不能假定失败后自动重试；
- Service README 记录每个写 Tool 的副作用、审批、幂等和恢复方式；
- 测试直接断言普通 Agent 的工具列表不包含管理员、Sandbox 或其他高副作用 Tool。

等至少两个 Service 出现相同、稳定且人工维护容易漂移的副作用配置后，再决定是否增加小型
数据结构。当前不为假设中的未来问题创建框架。

## 9. Middleware 边界

首期继续使用独立 Middleware，不创建 Tool Policy Builder：

```text
RuntimeConfigMiddleware
  -> 过滤模型可见 Tool
  -> Tool 执行前复核 allowlist

HumanInTheLoopMiddleware
  -> 处理指定 Tool 的具体调用审批

ToolCallLimitMiddleware
  -> 限制调用次数

ToolRetryMiddleware
  -> 只重试显式名单中的 Tool

ToolErrorMiddleware
  -> 只归一化预期可恢复错误
```

以上语义顺序已确定，最终 Middleware 列表顺序必须在锁定 LangChain 版本上通过契约测试，
不能只凭数组位置推断嵌套顺序。

## 10. Subagent 规则

Subagent 复用相同原则，但工具列表必须单独显式声明：

```python
main_tools = [search_project, create_test_case]
reviewer_tools = [search_project]
```

Subagent 不因 RuntimeContext 可以传播就自动继承父 Agent 的所有 Tool，也不需要独立 Registry。
Backend、Workspace、Skills 和 Subagent 的完整生命周期在下一专题讨论。

## 11. 验证要求

实施时至少验证：

1. Agent 未显式装配的 Tool 无法通过 RuntimeContext 注入；
2. Policy 禁止的 Tool 对模型不可见，伪造调用也被执行前检查拒绝；
3. Required Tool 被 Policy 禁止时 Run 明确失败；
4. Tool 名称冲突在 Agent 创建阶段失败；
5. 未配置的可选 MCP 不泄漏 Credential，也不产生不存在的 Tool；
6. 必需 MCP 不可用时 Run 明确失败；
7. 写 Tool 不在默认 retry 名单；
8. 普通 Agent 不包含管理员、Sandbox、Shell 或 Repo Execution Tool；
9. schema/introspection 不连接 MCP 或创建外部资源；
10. Subagent 只能调用自己显式声明的 Tool。

## 12. 首期明确不设计

- 公共 Tool Registry；
- `ToolSpec` / `ToolRegistration`；
- `CapabilityProfile` 或 Policy DSL；
- 自动扫描和插件发现；
- 公共 MCP Manager 或 MCP Provider Registry；
- 通用 `DynamicToolMiddleware`；
- 通用副作用事务框架；
- 根据 Tool 名称前缀猜测权限或副作用。

## 13. 参考依据

- Open SWE `agent/server.py`：`get_agent()` 显式构造工具列表并传给 `create_deep_agent`；
- Open SWE `agent/tools/`：业务 Tool 按文件组织，未建设通用 Registry；
- Open SWE `agent/middleware/dynamic_tools.py`：仅针对可选集成的延迟加载优化；
- Open SWE `agent/integrations/*_mcp.py`：服务端凭据、超时和远端 Tool 白名单；
- LangChain Dynamic Tool Selection：`/oss/python/langchain/tools#dynamic-tool-selection`；
- Deep Agents MCP Tools：`/oss/python/deepagents/tools#mcp-tools`；
- LangChain Human-in-the-loop：`/oss/python/langchain/human-in-the-loop`。

本轮只形成设计文档，不创建 Runtime 源码、不迁移 Legacy、不修改依赖，也不调用 OpenSpec。
