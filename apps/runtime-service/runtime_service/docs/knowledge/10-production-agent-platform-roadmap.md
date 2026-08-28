# 生产级 Agent 平台架构结论与演进路线

- 文档类型：`Supporting`
- 适用范围：`apps/runtime-service`、`apps/platform-api` 及二者最短正式链路
- 结论确认日期：2026-08-28
- 权威边界：本文记录已确认的架构方向和后续讨论顺序，不替代 leaf standard、
  OpenSpec change 或具体实现评审

## 1. 目的

本文固化对当前项目与 Open SWE 的架构对照结论，并给出后续逐项讨论、设计、实现和
验收的顺序。

本文确认的是演进方向，不代表已经授权：

- 修改公开 runtime contract；
- 执行数据库迁移；
- 升级共享环境依赖；
- 切换 staging 或生产流量；
- 删除 legacy 路径；
- 引入 Sandbox、GitHub、PR 等高副作用能力。

上述动作仍按仓库执行分级和 OpenSpec 流程单独评审。

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

- `langgraph.json` 统一注册 Graph 和 HTTP app。
- 静态 `create_agent(...)`、`create_deep_agent(...)` 和显式 `StateGraph` 已有清晰适用边界。
- `RuntimeRequestMiddleware` 已统一动态模型、Prompt 和工具选择。
- 动态工具已同时覆盖模型可见性和实际执行绑定。
- `tools/registry.py` 已作为公共工具目录真源。
- `platform-api` 已具备 project scope、delegation、runtime gateway、operation 和审计基础。
- 当前 Durable Run change 已实现 Coordinator、幂等记录、单 active Run、operation 映射和
  Protocol v2 前端 transport 的主要本地能力。

### 4.2 需要优先解决的缺口

1. **运行契约口径不完全一致**：代码中的 `RuntimeContext`、`RuntimeOptions` 与部分文档描述
   仍需统一，尤其是可信身份、业务选项和 `configurable` 的边界。
2. **缺少共享可靠性内核**：尚未形成统一的模型调用限额、单次超时、Run deadline、Fallback、
   ToolMessage 错误、空结束保护和 finalizer。
3. **Thread 资源隔离未完全证明**：部分 Deep Agent backend 使用模块级目录或实例，并发 thread、
   多 worker 和进程恢复语义需要单独验证。
4. **工具只有目录，缺少完整策略**：尚未统一表达副作用、幂等性、权限、超时、重试、审批和
   审计级别。
5. **Durable Run 仍缺真实运行时证据**：worker restart、checkpoint 恢复、事件 replay、多
   interrupt、重复 completion webhook 和真实 PostgreSQL/Redis 链路尚未全部验收。
6. **观测和质量门槛不足**：还不能稳定回答某次 Run 使用了哪个 Agent 版本、模型、Prompt、
   工具策略，失败发生在哪一层，以及新版本是否应回滚。

## 5. 目标架构

```text
Platform governance
  actor / project / policy / audit / operation
        |
        v
Single Durable Run Coordinator
  idempotency / config snapshot / lifecycle / safe summary
        |
        v
LangGraph Agent Server
  thread / run / sync checkpoint / replay / interrupt
        |
        v
Versioned static Graph
  RuntimeContext + RuntimeOptions
        |
        v
Shared reliability middleware
  prepare / limit / timeout / fallback / tool error / finalizer
        |
        v
Capability policy
  registered tools
    intersect assistant profile
    intersect project policy
    intersect actor permissions
    intersect approval state
        |
        v
Business tools / MCP / specialist agents
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
证据；不把五个阶段塞进一次大重构。

### 阶段 0：运行契约与配置快照

先讨论：

- `RuntimeContext`、`RuntimeOptions`、`RunnableConfig.configurable` 的最终字段归属；
- Assistant / Graph / Prompt / Tool Profile 的版本标识；
- Thread 与业务对象的稳定索引；
- Run 状态、错误码和幂等语义；
- Thread、Run、Trace 分别保存哪些安全配置摘要。

验收：

- 客户端不能伪造身份和项目范围；
- 同一幂等键不会创建第二个 Run；
- 历史 Run 可解释实际模型、Prompt 和工具策略；
- 配置默认值变化不会改写历史 Run；
- 不在 metadata 中保存完整 Prompt、Token 或密钥。

### 阶段 1：共享可靠性内核

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

### 阶段 2：Durable Run 与恢复闭环

本阶段复用现有 `add-react-agent-web` OpenSpec change，不创建第二套 Coordinator、Run API 或
事件协议。

重点完成其尚未覆盖的 runtime 和真实链路边界：

- 固定 Agent Server 镜像、SDK、CLI 和锁文件组合；
- 隔离 PostgreSQL / Redis；
- sync checkpoint 和 worker restart；
- Protocol v2 `run.start` / `input.respond`；
- POST SSE `since` replay；
- 多 interrupt 精确恢复；
- cancel、终态、operation 和 audit 收敛；
- 重复 completion webhook 幂等。

验收必须来自真实部署的最短链，mock upstream 和 in-memory runtime 只能作为辅助证据。

### 阶段 3：Capability Policy 与副作用隔离

先定义最小 Tool Policy：

```text
side_effect
idempotent
project_scoped
timeout_seconds
retry_policy
requires_approval
audit_level
```

实施顺序：

1. 只读工具；
2. 需要审批的写工具；
3. 外部副作用工具；
4. 只有明确 Coding Agent 需求时，才引入 Workspace / Sandbox / Git / PR capability。

普通 SQL、Testcase、Research Agent 默认不得获得 repo execution 或任意 shell 能力。

### 阶段 4：观测、评测与发布门槛

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

之后再建设领域数据集、轨迹断言、质量反馈、灰度和回滚门槛。

## 7. 后续逐项讨论顺序

后续每次只讨论一个决策单元，推荐顺序：

1. `RuntimeContext` 与 `RuntimeOptions` 最终契约。
2. 配置快照、Agent 版本和 Run metadata。
3. 最小可靠性 middleware 及其执行顺序。
4. 工具 policy、权限、审批、超时和重试。
5. Deep Agent backend 的 thread 隔离与恢复。
6. 现有 Durable Run change 的真实 E2E 收口。
7. Run / Model / Tool / Subagent 观测字段。
8. Assistant 级评测数据集与发布门槛。

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
- 不在真实 Durable Run E2E 通过前切生产或删除旧路径。
- 新行为先选择一个基准 Agent 验证，再推广到其他 Agent。

第一轮基准建议使用 `assistant`：依赖少、已有 HITL、多模态和动态工具样板，适合先证明公共
可靠性内核。涉及 Deep Agent backend 的能力应在公共内核稳定后，再用 `research_agent` 做第二轮验证。

## 9. 相关资料

- [LangGraph 生态优秀仓库调研与 runtime-service 对照](./07-langgraph-ecosystem-repository-research.md)
- [官方 LangGraph Runtime 升级与事件流迁移记录](./09-langgraph-runtime-upgrade-and-event-migration.md)
- [runtime-service 当前架构标准](../standards/02-architecture.md)
- [Agent 开发 Playbook](../standards/03-agent-development-playbook.md)
- [Middleware 开发 Playbook](../standards/08-middleware-development-playbook.md)
- [platform-api Runtime Gateway 标准](../../../../platform-api/docs/standards/runtime-gateway-interface-standard.md)
- [现有 React Agent Web / Durable Run change](../../../../../openspec/changes/add-react-agent-web/proposal.md)
- [Open SWE](https://github.com/langchain-ai/open-swe)

外部 `agent-engineering-learning` 分析资料用于形成本文结论，但不作为本仓库 current standard；
后续实现必须以当前锁文件、官方文档、活代码和真实验证结果为准。
