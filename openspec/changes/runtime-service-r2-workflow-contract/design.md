## Context

当前 `runtime-agent-service-integration` active spec 只描述 `reference_agent` 的 Runtime
组合根，没有描述 11 号目录设计中 `workflow_demo` 的条件分支和恢复行为。R2 归档记录因此
把一个只有 `START -> respond -> END` 的静态图标成已完成，无法作为 Workflow 能力的可靠合同。

当前 `reference_agent` 已按 R1 的 fail-closed 规则从 Agent Server Auth facts 获取 Principal
和 Policy；没有可信身份时会拒绝。归档 R2 的 `get_agent({})` 默认成功场景与这个边界冲突。

## Goals / Non-Goals

**Goals:**

- 在 active spec 中冻结 `workflow_demo` 的 Typed StateGraph、条件分支和本地 Interrupt/Resume
  可观察行为。
- 用本地、无外部服务的 checkpointer 验证暂停、恢复和已完成节点不重复执行。
- 让生产 `reference_agent` 在缺少已验证 Auth facts 时稳定失败。
- 保留显式 local test adapter，支持 fake model 和本地组合测试，但不让它成为生产默认路径。
- 明确 R2 本地恢复证据与 R6 真实 PostgreSQL/Redis、Worker 重启证据的边界。

**Non-Goals:**

- 不在本变更中实现代码、修改 Platform API 或引入新的公共 Workflow Builder。
- 不让 `get_agent({})` 通过隐式 Principal、Policy 或 Provider 凭据补全而成功。
- 不把 in-memory checkpointer、单进程恢复测试当作 R6 Durable Run 证据。
- 不修改已归档 OpenSpec 文件的历史内容；历史冲突通过 active delta 和对齐审计处理。

## Decisions

### 1. 用现有 Agent Service integration 能力承载 Workflow 合同

Workflow 是 Agent Service 的一种构造形态，不另建公共 Workflow capability。delta spec 在
现有 `runtime-agent-service-integration` 下新增 Workflow Requirement，并保留
`graphs/<graph_id>.py` 仅重导出入口的边界。

替代方案是新建通用 Workflow spec 或 Builder。拒绝：当前只有一个参考 Workflow，新增公共
抽象会把 Demo 的局部语义提前扩散到所有 Service。

### 2. R2 只冻结本地可观察恢复语义

`workflow_demo` 使用 Service 私有 Typed StateGraph 和一个本地 checkpointer。条件分支必须
有两条可执行路径；Interrupt 必须暴露服务端声明的恢复点；Resume 必须从该点继续，并由
节点执行计数或等价事件断言证明之前完成的节点没有重复执行。

R2 不规定 PostgreSQL/Redis、Worker lease、SIGTERM handoff 或跨进程恢复；这些属于 R6，
由真实 Agent Server 部署测试单独验收。

### 3. 空配置不再代表本地可信身份

`reference_agent.get_agent({})` 在没有 Agent Server Auth facts 时返回稳定的
`runtime.auth.missing_principal`。本地测试必须显式提供 test-only model/identity adapter，
现有 `_runtime_model` fake 注入路径可以继续作为实现载体；生产 `langgraph.json`、真实
Agent Server 请求和普通 `RunnableConfig` 不得启用该 adapter。

替代方案是在所有空配置请求中补本地 Principal。拒绝：这会把匿名调用与本地调试混为一谈，
破坏 R1 的 fail-closed Auth 边界，也无法区分 Agent Server introspection 和开发者直接调用。

### 4. 不把业务 Context 当作 Auth fallback

`RuntimeContext` 继续只承载模型、生成参数和工具候选值；Principal、Policy、凭据和 local
debug 身份不从 `context`、metadata、state 或用户消息读取。Workflow 的恢复输入只进入
服务声明的 State/Resume value，不改变 Runtime Auth 事实。

## Risks / Trade-offs

- [本地 checkpointer 可能掩盖生产 Durable 问题] -> verification 明确标记为 R2 local；R6 必须
  使用真实 PostgreSQL/Redis 和 Worker 证据。
- [显式 local adapter 增加本地调用样板] -> 接受该成本，换取生产认证边界不可绕过；只在测试
  helper 中集中构造，不增加公共 Builder。
- [interrupt API 或 checkpoint schema 随 LangGraph 版本变化] -> 锁定当前依赖，测试使用
  当前官方 API；不能凭版本外文档猜字段。
- [Workflow 分支状态字段过早固定] -> spec 只冻结两条可观察路径和恢复语义，具体私有 State
  字段由 Service 自己维护。

## Migration Plan

1. owner 审核 proposal、delta spec、design、tasks 和 verification。
2. owner 批准后实现 `workflow_demo` 的分支、Interrupt/Resume、专属测试和 README。
3. 修正/补强 `reference_agent` 的 local test adapter 测试，确保空配置继续 fail-closed。
4. 运行 local/minimal、Agent Server demo chain；R6 继续独立验证真实 Durable。
5. 接受后将 delta spec sync 到 `openspec/specs/`，再归档本变更。

回滚只移除本变更实现和 active spec 增量，不删除 Thread、Checkpoint 或其他持久化数据。

## Open Questions

- owner 是否接受 11 号 Draft 将 Workflow 条件/恢复能力纳入 R2，而不是将其整体后移到 R6。
- owner 是否接受 `get_agent({})` 在生产和普通调用中 fail-closed，仅允许显式 local test adapter。
