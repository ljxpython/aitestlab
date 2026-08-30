# Agent、Graph、Prompt、Tool Policy 版本与发布设计（Draft）

> 文档类型：Draft
>
> 状态：延期方案，不属于当前实施范围，也不替代 `docs/standards/` 下的现行规范
>
> 当前决策：本项目暂不建设 Agent Release、灰度发布、自动回滚、Run Snapshot 或进行中
> Run 的版本锁定。本文仅保留未来出现多部署、多租户和独立发布需求后的候选设计，当前
> Runtime 以稳定 `graph_id`、部署系统回滚和 LangGraph 自身的 Thread/Run/Checkpoint 语义为准。
> 本文中的旧版本兼容、迁移、保留旧产物和旧 Thread 恢复方案均不属于当前绿色开发目标。
> 本文后续章节全部是待未来重新讨论的非规范草稿，当前实施一律忽略，不得据此增加兼容层、迁移
> 逻辑或旧版本路由。
>
> 关联文档：`10-production-agent-platform-roadmap.md`、
> `11-agent-service-directory-architecture.md`、
> `14-runtime-contracts-and-resolution-design.md`、
> `18-open-swe-to-runtime-event-and-run-explorer-design.md`、
> `19-runtime-tool-capability-mcp-and-side-effect-design.md`、
> `20-runtime-backend-workspace-skills-and-subagents-design.md`
>
> 冻结范围：Agent Release、Graph/Prompt/Tool Policy 版本、灰度、回滚和进行中 Run 绑定
>
> 暂不展开：具体数据库表、部署编排实现、完整评测平台、生产发布审批页面

## 1. 未来为什么可能需要这部分

Agent 进入生产后，Graph 代码、Prompt、模型和 Tool Policy 都会持续变化。如果只保存一个
`assistant_id` 或只读取当前最新配置，会出现四类问题：

1. 同一个 Run 在 interrupt/resume 后使用了不同 Prompt 或 Tool Policy；
2. 无法回答历史 Run 实际使用了哪个 Graph、模型和工具权限；
3. 新版本一次性影响所有租户，错误无法控制在小范围内；
4. 回滚只改了“当前版本”指针，却无法恢复进行中的 Thread 或旧 checkpoint。

本设计的目标不是建设四个版本 Registry，而是让每个 Run 在开始时确定一份不可变的执行组合：

```text
Agent Release
  -> Graph Ref + Prompt Ref + Tool Policy Ref + Model/Skills/Subagents refs
  -> Run Snapshot
  -> 后续 stream / interrupt / resume / retry 始终使用该 Snapshot
```

## 2. Open SWE 和 LangGraph 的真实做法

### 2.1 Open SWE 自身没有建设发布控制面

Open SWE 的稳定入口仍然是 `langgraph.json -> agent/graphs/* -> get_agent()`。业务组合逻辑在
`agent/server.py`，而不是写进部署注册文件。

Open SWE 的调用链使用 `assistant_id` 选择 Graph，但源码中没有实现独立的 Agent Release 表、
灰度规则或回滚控制器。它运行所依赖的 LangGraph Deployment 提供 Assistant 配置版本能力：

- 一个 Graph 可以对应多个 Assistant；
- Assistant 可以保存不同 Prompt、模型和其他配置；
- 更新 Assistant 会创建新的配置版本；
- 任意历史版本都可以被设为 active；
- 新创建的 Run 使用 active 版本。

这套机制适合 Prompt、模型等配置版本，但不能把 LangGraph Deployment 的平台能力误写成
Open SWE 自己的 Agent 架构。我们借鉴的是稳定 Graph 入口和官方 Assistant version，不复制一个
Open SWE 并不存在的 Release Manager。

### 2.2 Open SWE 的 Graph 版本边界

Open SWE 将 Graph 作为部署代码，通过稳定的 Graph ID 暴露。它没有在 `get_agent()` 中为每次
请求创建一套版本化 Graph Registry；代码版本由部署产物和 Agent Server 管理。

这带来一个必须正视的事实：LangGraph 默认会让最新部署的 Graph 作用于旧 Thread。Assistant
版本本身不能锁住 Graph Python 代码。

如果 Graph 的节点、State Schema 或恢复语义不兼容，必须使用以下方式之一：

- 保持旧 Graph 代码兼容一段 drain 周期；
- 为新行为注册新的 Graph ID，并只把新 Thread 路由过去；
- 在 State 中记录行为版本，用条件边兼容旧 Thread；
- 在部署层保留旧版本运行产物并把旧 Run 路由回去。

### 2.3 值得借鉴和不能照搬的内容

借鉴：

- Stable Graph ID 与内部组合根分离；
- Assistant 配置版本化；
- 更新创建新版本，而不是原地覆盖历史配置；
- active pointer 支持快速切换和回滚；
- 运行时和部署配置由服务端管理，不信任客户端任意改版本；
- 使用 checkpoint、Thread 状态和 Trace 判断旧版本是否仍在使用。

不照搬：

- 不把 LangSmith Assistant API 当成我们平台唯一的控制面契约；
- 不假设 Assistant version 自动锁定 Graph 代码；
- 不为当前项目引入 Open SWE 的 Slack、GitHub、Sandbox 发布流程；
- 不为当前需求提前建设独立的版本 Registry、插件市场或复杂策略 DSL。

## 3. 版本对象和最小模型

### 3.1 Agent Release

平台只需要一个面向发布的组合对象，不需要四个互相独立的 Manager：

```text
AgentRelease
  release_id                 不可变 ID
  agent_id                   Top-level Agent 身份
  deployment_ref             graph_id + immutable artifact/image revision
  assistant_ref              assistant_id + Assistant config version
  runtime_contract_ref       Runtime contract 版本
  component_hashes           prompt / tool config / model / skills / subagents
  status                     draft | canary | active | retired
  created_by / created_at
```

`AgentRelease` 一旦进入可运行状态不可原地修改。任何 Prompt、Tool Policy、Graph 或模型关键
配置变化都创建新的 Release。未来如果重新启用本方案，也不为 Prompt、Tool、Skills 和 Subagents 分别建设版本表：

- 代码内 Prompt、Tool/Middleware 配置、Bundled Skills 和 Subagents 由不可变部署产物覆盖；
- Assistant 管理的 Prompt、模型等配置由 `assistant_id + assistant_version` 覆盖；
- `component_hashes` 用于审计和对比，不形成另一套 Registry。

`deployment_ref` 必须能追溯到可运行代码，而不能只记录 Git branch。推荐记录 immutable image
digest、构建版本或等价不可变产物标识；Git commit 只作为辅助来源信息。

### 3.2 Run Snapshot

Run 创建时，Platform API 将选中的 Release 和可信运行参数解析成快照：

```text
RunSnapshot
  run_id
  release_id
  deployment_ref
  assistant_ref
  component_hashes
  resolved_runtime_config_hash
  workspace_binding
  runtime_contract_ref
  snapshot_hash
  selected_at
```

Snapshot 是 Run 的事实依据。它可以记录摘要和引用，不应保存完整 Secret、完整 Prompt 或
大型工具结果。

`RunSnapshot` 是 Platform Run 的持久化投影名称，不新增第六个公共 Runtime Python 类型。
Runtime 内部继续使用 14 号文档的五类契约和 `ResolvedRuntimeConfig`；平台快照只补充
`release_id`、部署/Assistant 引用、资源绑定以及这些决议结果的安全 hash。

### 3.3 两类 Policy 不能混为一谈

本文的 Tool Policy 版本表示 Release 的能力行为，例如：

- Service 显式装配哪些业务 Tool；
- Deep Agents 保留哪些内置 Tool；
- 哪些调用需要 HITL；
- 哪些 Tool 允许 retry。

它仍按 19 号文档落在 Service 代码、`AgentDefaults` 和独立 Middleware 配置中，不新增 Tool
Policy DSL。

14 号文档的 `RuntimePolicy` 是 Platform API 针对当前 actor、tenant、project 签发的授权快照。
权限撤销和安全阻断不能被旧 Release 固化。每次真实执行或 resume 都必须取得有效的授权，并
与 Release 能力求交集：

```text
Release Tool 能力
  intersect 当前签名 RuntimePolicy
  subtract 紧急 deny / 已撤销权限
  = 本次实际 Tool 能力
```

因此行为版本可锁定，权限不能越权回放。紧急 deny 可以立即影响进行中的 Run；该安全收缩必须
记录 Event 和 Audit，但不修改历史 Snapshot。

### 3.4 Rollout Rule

灰度规则也保持最小：

```text
RolloutRule
  agent_id
  release_id
  selector              tenant / project / user / environment
  percentage            可选固定比例
  priority
  status
```

只由 Platform API 维护。Runtime Service 不自行计算“当前 active release”。

## 4. 版本边界

| 对象 | 变化示例 | 是否创建新 Release | 进行中 Run 规则 |
| --- | --- | --- | --- |
| Agent 身份 | 改变产品能力或服务边界 | 是 | 继续使用旧 Snapshot |
| Graph | 节点、State、Subagent 拓扑变化 | 是；不兼容时新部署 revision | 旧 Run 必须兼容或回到旧产物 |
| Prompt | 系统指令、输出规范变化 | 是 | 继续使用旧 Prompt 引用 |
| Tool Policy | 工具 allowlist、审批、重试变化 | 是 | 保留旧行为配置，但仍叠加当前授权和紧急 deny |
| Model | 模型 ID、关键采样参数变化 | 是 | 继续使用旧模型配置 |
| Bundled Skills | Skill 内容或来源版本变化 | 是 | 继续使用旧 Skill 版本摘要/产物 |
| Workspace | Thread Sandbox 绑定变化 | 通常不是 Release | 继续使用旧 Workspace binding |

Workspace 是运行资源绑定，不应因为每次创建 Sandbox 就产生一个新的 Agent Release；但它的
绑定 ID 和恢复状态必须写入 Run Snapshot 或关联资源记录。

## 5. 发布和灰度流程

```text
开发/评测
  -> 创建 immutable AgentRelease(draft)
  -> 契约测试、工具权限测试、恢复测试
  -> 发布 canary
  -> Platform API 按 selector / hash 选择 Release
  -> Run 创建时生成 RunSnapshot
  -> 观察成功率、延迟、成本、工具错误和业务质量
  -> 扩大灰度或 promote active
```

灰度规则：

1. 只影响新创建的 Run；
2. 使用稳定 hash 选择比例；有状态 Thread 默认以 `thread_id` 作为粘滞键，避免跨 Turn 抖动；
3. 选择结果在 Run 创建事务中持久化；
4. 客户端只能请求 Agent 身份，不能提交任意 `release_id`；
5. 内部测试可以显式指定已授权 Release，但必须经过 Platform API 权限校验；
6. 灰度命中信息写入 Run Event、Audit 和 Trace metadata。

灰度不要求同时运行两套 Python 包。配置变化可以复用同一 Graph；Graph 不兼容时优先使用
独立不可变部署产物，部署系统无法按 revision 路由时才临时使用版本化 Graph ID。

## 6. 回滚语义

回滚只切换 Agent 的默认 active Release：

```text
active: release-v3
发现问题
active: release-v2
```

回滚规则：

- 新 Run 使用 release-v2；
- 已创建的 Run 继续使用自己的 RunSnapshot；
- release-v3 不删除，只标记 retired 或 blocked；
- 历史 Run 仍然能查询到 release-v3；
- 如果是安全事故，立即执行 Run cancel / 紧急 Tool deny，而不是假设 rollback 会停止当前执行；
- 只有旧 Graph 产物、Prompt 引用和 Tool Policy 仍可解析时，回滚才真正可用。

删除或清理 Release 前，必须确认没有 `busy`、`interrupted` 或可恢复的 Run 仍依赖它。

## 7. 进行中 Run 锁定

### 7.1 必须锁定什么

Run 开始时至少锁定：

```text
release_id
deployment_ref
assistant_ref
component_hashes
resolved_runtime_config_hash
workspace_binding
```

这里的 Run 指 Platform API 管理的一次逻辑 Durable Run。Agent Server 的 interrupt/resume 可能
产生后续执行请求，但仍属于同一个逻辑任务，必须复用原 Snapshot。

后续以下操作都不得重新读取 active Release：

- interrupt 后 resume；
- SSE 断线重连和事件补发；
- worker 重启后的 checkpoint 恢复；
- Tool 审批后继续；
- 受控 retry。

同一 Thread 上的新用户消息通常会创建新的 Run，可以选择新的 Release。但如果该 Thread 保存了
有版本含义的 State，新 Release 必须声明与旧 checkpoint 兼容；否则继续绑定原 Release，或者
创建新 Thread。Run 锁定解决执行一致性，Thread 的 `flow_version` 解决跨 Run 的业务兼容性，
二者不能混成一个概念。

### 7.2 Graph 代码锁定的现实方案

仅保存 `deployment_ref` 不够。如果所有版本都部署在同一个 Graph ID 下，LangGraph Server 可能会
用最新代码恢复旧 Thread。因此按风险分三档：

#### 兼容变更

保持同一 Graph ID，但遵守 LangGraph 的 checkpoint 兼容要求：

- 不删除或重命名旧节点；
- 不删除旧 State 字段；
- 新字段使用可选值或默认值；
- 旧 Thread 经过 drain 后再清理兼容代码。

#### 行为不兼容但可在同一代码中兼容

在 State 或持久化 Thread metadata 中记录 `flow_version`，由条件边选择旧/新行为。版本必须
在 Thread 开始时写入，不能在恢复后临时推断。

#### 代码或 State Schema 不兼容

优先保留独立部署产物并将旧 Run 路由回原 revision；部署系统无法按 revision 路由时，临时注册
新的 Graph ID：

```text
research_v1 -> 旧 Thread / 旧 Snapshot
research_v2 -> 新 Thread / 新 Snapshot
```

这是首期最可靠的 Graph 回滚方式。版本化 Graph ID 是兼容窗口，不代表一个 Service 永久暴露
多个 Top-level Agent；旧 Thread drain 完成后移除旧入口。不要为了让一个 Graph ID 看起来
“永远不变”，把所有历史分支塞进一个无限增长的条件图。

### 7.3 Snapshot 失效

如果 Run Snapshot 引用的 Graph、Prompt、Policy 或 Skills 已经无法加载，Runtime 必须明确
失败并记录 `snapshot_unavailable`。不允许静默切换到 active Release。

只有经过显式迁移并保留审计记录，才能把旧 Thread 转换到新 Release；迁移不是普通 resume。

## 8. Platform API 与 Runtime Service 责任

### Platform API

- 创建和校验 Agent Release；
- 管理 active、canary、retired 状态；
- 计算并持久化灰度命中；
- 在 Run 创建时生成或签发 Run Snapshot；
- resume 时重新签发当前 actor/project 的授权，且不得改变 Release 行为快照；
- 记录发布、回滚、阻断和迁移 Audit；
- 保留旧 Release 和进行中 Run 的引用关系。

### Runtime Service

- 接收可信的 Release/Snapshot 引用和当前有效 RuntimePolicy；
- 解析指定 Graph、Prompt、Tool Policy 和模型；
- 校验 Snapshot hash、租户范围和 Runtime Contract；
- 在模型、Tool、MCP、Backend、Skills、Subagent 执行前使用 Snapshot；
- 将实际版本写入 Trace、Run Event 和错误摘要；
- Snapshot 无法恢复时失败，不自行换版本。

Runtime Service 不负责灰度决策，不把客户端的 `release_id` 当成授权，不在每个 Service 内实现
一套 active-version 查询。

## 9. `get_agent()` 接入规范

`get_agent()` 仍然是 Service 的组合根，但不负责选择生产 Release：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    snapshot = await resolve_run_snapshot(config)
    runtime = await resolve_runtime_config(config, snapshot=snapshot)

    return create_deep_agent(
        model=runtime.model,
        system_prompt=runtime.system_prompt,
        tools=[search_project, read_document],
        backend=await get_service_backend(config),
        skills=["/skills/"],
        subagents=service_subagents(runtime.model),
        middleware=[RuntimeConfigMiddleware(runtime)],
        context_schema=RuntimeContext,
    )
```

对于静态 Graph，`graph_ref` 由部署入口和运行环境保证；`get_agent()` 只消费 Snapshot 中的
Prompt、Policy、Model 和必要资源绑定。示例中的 Tools、Skills 和 Subagents 仍由 Service 显式
声明，不从 Snapshot 动态上传实现。不要因为版本治理就把所有 Agent 改成通用动态 Builder。

## 10. 与现有 Runtime Contract 的衔接

客户端可提交的仍是业务输入和允许的 Runtime 选项，不能提交：

- 任意 Graph 路径；
- 任意 Prompt 内容作为系统身份替换；
- 任意 Tool Policy；
- 任意 Skill / Subagent 定义；
- 未授权的 Release ID；
- Backend Credential。

可信字段由 Platform API 注入或签发：

```text
client input
  + trusted actor / tenant / project
  + selected release snapshot
  -> RuntimeContext + config.configurable
```

`RuntimeContext` 可以携带本次 Run 的快照引用和业务选项，但不能让模型或客户端重新解析
Release。`config.configurable` 只传线程、Assistant/Run 标识及少量服务私有字段；完整版本事实
以 Platform Run Snapshot 和 Runtime 校验结果为准。

Runtime 不再新增 `RunSnapshot` dataclass。`resolve_run_snapshot()` 是伪代码，表示验证 Platform
传入的快照引用并将其投影到既有 `RuntimePolicy`、`AgentDefaults` 和
`ResolvedRuntimeConfig`，最终 API 仍以 14 号文档为准。

## 11. 观测和查询要求

每个 Run 的安全摘要至少包含：

```text
run_id
release_id
deployment_ref
assistant_id + version
component_hashes
resolved_runtime_config_hash
workspace_binding_id
rollout_bucket
```

Langfuse Trace、Runtime Run Event、Platform Audit 和 Run Explorer 必须使用同一 `release_id`
和 `snapshot_hash` 关联。完整 Prompt、凭据和大型工具输入仍遵守 16、17、18 号文档的数据
脱敏规则。

## 12. 未来候选范围（延期）

未来重新评估时可能实现以下能力：

1. Agent Release 组合记录；
2. 复用 Assistant version，并记录 Prompt、Tool 配置、Model、Skills、Subagents 的安全 hash；
3. Run 创建时生成 Run Snapshot；
4. 新 Run 的 canary / active 选择；
5. active Release 回滚；
6. interrupt/resume 使用原 Snapshot；
7. 版本摘要进入 Run Event、Trace 和 Explorer；
8. Graph 不兼容变更保留旧部署 revision，必要时临时使用新 Graph ID。

即使重新评估，也不优先实现：

- 全自动多指标发布控制器；
- 自动根据 Langfuse 质量分数回滚；
- 任意 Graph 旧版本的热加载插件系统；
- Prompt 在线编辑器；
- 跨版本 Thread 自动迁移；
- 旧 Release 的立即物理删除；
- 独立 Subagent 版本 Registry。

## 13. 验证要求

至少覆盖以下场景：

1. Prompt v2 发布后，新 Run 使用 v2，进行中的 Run 仍使用 v1；
2. Tool Policy v2 发布后旧 Run 保留原行为配置，但权限撤销和紧急 deny 立即收缩能力；
3. 灰度按固定 selector/hash 稳定命中，命中结果可查询；
4. 回滚只影响新 Run，不修改历史 Run Snapshot；
5. interrupt/resume、SSE reconnect 和 worker restart 保持同一个 Snapshot hash；
6. Snapshot 引用失效时明确报错，不回退到 active Release；
7. Graph 不兼容变更保留旧部署 revision 或临时使用新 Graph ID，旧 Thread 仍可恢复；
8. State `flow_version` 在 Thread 初始执行时写入，旧 Thread 不被错误导入新分支；
9. 普通客户端不能伪造 Release、Graph、Policy 或 Prompt 引用；
10. Run Explorer 能展示 release、graph、prompt、policy、model 和 rollout 摘要；
11. Release 进入 retired 前能查出仍依赖它的 busy/interrupted Run；
12. 安全阻断可以单独 cancel/deny，不依赖 rollback 停止当前 Run。
13. 同一 Thread 的新 Run 只有在 checkpoint 兼容时才能采用新 Release。

## 14. 参考依据

- Open SWE `agent/graphs/*` 与 `agent/server.py`：稳定 Graph 入口和运行时组合根；
- Open SWE `docs/agent-root-files-guide-zh.md`：Graph 注册与 `get_agent()` 分层；
- LangGraph Deployment Assistants：同一 Graph 多 Assistant、配置版本、active version 和回滚；
- LangGraph Backward Compatibility：最新 Graph 对旧 Thread 的影响、State/节点兼容和
  `flow_version` 条件边模式；
- LangGraph Agent Server：Assistant 配置与 Graph 执行边界。

本轮不实施本文设计，不创建 Release 表、不接入灰度控制器、不修改 Platform API、不迁移
Legacy，也不调用 OpenSpec。当前横向契约以 `22-platform-runtime-contract-design.md` 为准。
