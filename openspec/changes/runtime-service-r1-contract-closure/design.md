## Context

当前 Runtime 的 `runtime/auth.py` 能校验基础 JWT，并且 `resolver.py` 能完成本地 Context、Policy 和 Defaults 合并，但 `reference_agent` 仍把 Principal/Policy 固定在模块级常量中。这样单元测试可以通过，真实 Agent Server 却无法证明每个请求使用了该请求自己的可信身份和策略。

本变更只负责 `apps/runtime-service` 的 R1 合同闭合。LangGraph 当前锁定版本提供 `langgraph_sdk.Auth`、`langgraph.json.auth.path`、`runtime.server_info.user` 和 `request.runtime.context`，这些是 Auth 和 Runtime 接线的官方边界。Runtime 不访问 Platform API，不创建第二套授权服务。

## Goals / Non-Goals

**Goals:**

- 让短期 Delegation JWT 的 scope、policy snapshot 和 Context hash 可验证、可审计、fail-closed。
- 让 Required/Optional Tool 同时受 Service 声明、Policy allowlist 和 Actor permissions 约束。
- 让 Resolver 的输入不可变、边界校验和安全 snapshot 有可失败测试。
- 让 Agent Server Auth 输出的可信用户事实进入同一条 Principal -> Policy -> Context -> Resolver 链。
- 保留 local signer 和 fake model 作为显式测试输入，不把测试旁路带进生产路径。

**Non-Goals:**

- 不实现 R2 的 Workflow 条件分支、Interrupt/Resume。
- 不实现 R3 完整 Middleware 可靠性栈、R4 真实 Sandbox/MCP、R5 新观测能力或 R6 Durable。
- 不修改 Platform API，不新增 Policy 查询、Capability Registry、Provider Registry 或公共 Builder。
- 不让 Auth handler 读取请求体，也不把 Principal、Policy、JWT 或 secret 放入模型 Prompt。

## Decisions

### 1. 保留纯验证核心，新增薄 Agent Server 适配层

继续使用 `runtime/auth.py` 承担纯 JWT 解码、claim 类型检查和 `RuntimePrincipal`/`RuntimePolicy` 构造；新增 `runtime_service/auth/platform.py` 作为 `langgraph_sdk.Auth` 适配器，并在 `langgraph.json` 通过 `auth.path` 注册它。适配器只负责读取 Authorization、调用纯验证核心并返回 Agent Server 用户字典。

返回的用户字典包含 `identity` 和内部 runtime facts：`runtime_principal`、`runtime_policy`、`runtime_scope`、`runtime_context_hash`。这些字段只供 Runtime middleware 读取，不进入模型消息或 Prompt。Auth handler 无法可靠读取 invoke body，因此 Context hash 在 Model/Tool 边界由 middleware 使用同一 canonical 算法复核。

### 2. 冻结最小 claims 结构

Delegation JWT 保留现有 claims，并增加：

```json
{
  "scope": {
    "tenant_id": "tenant-a",
    "project_id": "project-a",
    "assistant_id": "assistant-a",
    "thread_id": "thread-a"
  },
  "context_hash": "sha256:..."
}
```

`scope.tenant_id` 和 `scope.project_id` 必须与 Principal 一致；如果 token 带有 `assistant_id` 或 `thread_id`，必须与当前 `runtime.execution_info` 对应值一致。Context hash 使用已规范化、仅包含执行事实的 Context snapshot 计算，不包含 JWT 生命周期字段、完整 Prompt、secret 或请求消息。缺少 hash、scope 结构错误或 hash 不一致均拒绝执行。

### 3. 在 Resolver 中执行三方 Tool 交集

Required Tool 必须同时存在于 AgentDefaults、RuntimePolicy allowlist 和 Actor permissions 映射的允许集合；缺任何一项直接失败。Optional Tool 使用 `tools=None` 继承 Defaults，`tools=()` 禁用 Optional，再对请求集合执行同样的三方交集检查。Actor permission 到 Tool 的映射保持 Service 私有显式配置，不创建公共 Registry；本次 `reference_agent` 只为 `read_reference` 声明一个最小映射。

### 4. Principal/Policy 按 Run 从 Auth user 解析

`RuntimeConfigMiddleware` 在 `abefore_agent`、`awrap_model_call` 和 `awrap_tool_call` 统一从 `runtime.server_info.user` 读取已认证的 runtime facts，并调用现有 parser/resolver。缺少 Agent Server user 时 fail-closed。为保持单元测试和 `langgraph dev` 的可测性，测试通过显式构造的 Auth user fixture 注入；生产 Service 不再使用模块级固定 Principal/Policy。

`get_agent` 只保留 Service Defaults、显式 Tool、Context schema 和 Middleware 顺序。模型构造仍只能接收 `ResolvedRuntimeConfig`；需要 per-run model 时由 middleware 在模型边界按解析结果构造。

### 5. Snapshot 只保存执行事实

为 `ResolvedRuntimeConfig` 增加显式 `to_snapshot()` / `from_snapshot()` 或等价的模块函数，使用 JSON-safe primitive 和固定 schema marker。round-trip 后 hash 必须相同；snapshot 中不得出现完整 Prompt、JWT、secret、模型实例或任意 callback。若新增字段会影响执行语义，必须改变 schema/hash 并补充测试。

### Alternatives considered

- **让 Resolver 查询 Platform API**：拒绝。违反 R1 无 I/O 约束，并把控制面延迟和故障带进每次 Run。
- **继续使用模块级 `_PRINCIPAL` / `_POLICY`**：拒绝。只能证明 local demo，不能证明真实请求隔离。
- **在 `RuntimeContext` 中携带身份和权限**：拒绝。Context 是不可信候选值，会破坏认证边界。
- **新增通用 Capability Registry**：拒绝。当前只有一个参考 Tool，Service 私有显式映射足够。

## Risks / Trade-offs

- [Auth user 字段名受锁定 Agent Server 版本影响] -> 在实现前用当前依赖版本做最小 Auth 集成测试；不匹配时标记 `blocked`，不得猜测字段位置。
- [Context hash 需要调用方与 Runtime 使用同一 canonical 输入] -> 固定 `runtime-context/v1` 规范化函数，测试等价输入、语义变化和篡改输入；不兼容时拒绝而不是静默重算。
- [permissions 到 Tool 的映射可能逐步增加] -> 只允许 Service 私有显式映射，映射缺失 fail-closed；出现第二个真实 Service 重复需求时再评估公共抽象。
- [Graph 构建阶段可能早于 per-run Auth facts] -> graph 只声明 Defaults 和 middleware，模型在模型调用边界使用已验证 Runtime facts；没有 facts 时请求失败。

## Migration Plan

1. 先完成 owner 对 proposal、specs、design、tasks 的整体 review，并记录到 `verification.md`。
2. 先补失败测试，再实现 claims/parser、snapshot、Resolver 权限交集和 Agent Server Auth 适配。
3. 运行 R1 local tests，再运行带 local JWT 的 Agent Server shortest-chain 集成测试。
4. 若 Auth 入口或真实环境不可用，保留代码的本地证据并把 chain 状态标为 `blocked`，不更新为 complete。
5. 回滚时移除 `langgraph.json.auth` 和适配层注册，保留纯 local verifier；不得恢复生产固定 Principal/Policy 作为兼容方案。

## Open Questions

- 当前锁定的 Agent Server 对 `runtime.server_info.user` 暴露的字段形状，以及 `runtime.execution_info` 是否同时提供 `assistant_id` 和 `thread_id`，必须由集成测试确认。
- `scope` 中是否需要 `assistant_id`/`thread_id` 由实际 Gateway token payload 决定；在未确认前，tenant/project 是必须项，额外 scope ID 只能按存在时校验。
