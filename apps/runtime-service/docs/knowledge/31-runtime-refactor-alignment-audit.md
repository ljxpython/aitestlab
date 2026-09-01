# Runtime 重构设计与 R0-R5 实现对齐审计

> 审计日期：2026-08-31
>
> 审计范围：`apps/runtime-service/docs/knowledge/10-30`、`apps/runtime-service/src/`、
> `apps/runtime-service/tests/`、部署配置和 R0-R6 OpenSpec 验证记录。
>
> 本文是实现对齐审计，不替代领域 Current Standard。当前
> `apps/runtime-service/docs/standards/` 为空，因此不能把 `knowledge/` 下的 Draft
> 直接当成已批准规范。

## 1. 结论先行

当前不能把 R0-R5 统称为“完成”。更准确的状态是：

| 阶段 | 计划状态 | 审计状态 | 结论 |
| --- | --- | --- | --- |
| R0 | 已完成并归档 | **部分完成** | 新包、Graph 入口、本地启动、阶段隔离和配置同步门禁存在；真实模型 E2E、启动失败闭环和生产运行证据仍不完整。 |
| R1 | 已完成并归档 | **local Agent Server chain 完成，Platform/Durable 后置** | Contracts、Resolver、JWT scope/context_hash、Actor 权限交集、Modeling 和 Agent Server Auth 到真实 DeepSeek Model 的 HTTP 链路已有证据；Platform 正式签发链和 R6 Durable 后置。 |
| R2 | 已完成并归档 | **local Agent Server chain 基本完成，生命周期仍有缺口** | `reference_agent` 组合根和真实模型链成立；`workflow_demo` 的条件分支、Interrupt/Resume、专属测试和 demo Server chain 已补齐。当前仍需完成 active spec sync，且 `reference_agent` 仍未满足静态/动态生命周期规则。 |
| R3 | 已完成并归档；R3 closure active | **local/组合完成，生产 fallback 未完成** | 限次、Runtime 配置复核、单次模型超时、Tool Error/Retry 已进入 `reference_agent` 真实 graph 并有组合测试；Model fallback/retry 目前仅 test-only adapter，Run deadline、PrepareRun、Finalizer 等按设计后置。 |
| R4 | 已完成并归档 | **local-complete，生产链阻塞** | R4 定向闭合测试 `44 passed`；Tool Policy、内置 Tool 收缩、MCP required/optional、Skill 只读和同 Thread 本地 Workspace 已有证据。`InMemorySaver`、进程内 `StateBackend`、本地 fake MCP 不能证明 Durable、跨 Worker 重连、清理或真实 Sandbox。 |
| R5 | closure 已 apply | **Runtime 闭环完成，生产 exporter 部分完成** | Langfuse lifespan、metadata allowlist、可信 Service 接线、真实 Model/Tool/Subagent callback、诊断和真实 smoke 已有证据；SDK queue drop 的 Runtime Counter、生产容器 SIGTERM/drain 和跨服务传播仍未闭合。 |
| R6 | 实施中 | **阻塞** | 默认 Durable 测试全部跳过；本地 `langgraph dev` 不是 Durable 证据，正式 Agent Server 被 LangGraph entitlement 的 403 阻塞。 |

因此，P1 Platform 整合不能开始。当前最重要的不是再加抽象，而是把认证接线、
Workflow 恢复语义和真实 Durable 证据补齐。

R2 的范围已由 owner 批准为：Workflow 条件分支和本地 Interrupt/Resume 纳入 R2；
`get_agent({})` 在缺少 Auth facts 时保持 fail-closed，仅允许显式 local test adapter。
归档 OpenSpec 保留历史，不修改；active spec 通过当前变更完成迁移。

## 2. 证据规则

本次按以下规则判定：

- **实现**：源码中存在对应责任边界，并有能失败的测试。
- **部分实现**：只有局部实现、演示实现、假依赖、单元测试，或没有接入真实调用链。
- **未实现**：设计要求有明确能力，但源码和测试均没有承担该责任。
- **明确后置**：文档已经声明本阶段不做，不作为本阶段缺陷，但不能计入已实现能力。
- **阻塞**：代码和测试可能存在，但完成所需的真实外部证据不可用。
- OpenSpec 的 `tasks.md` 勾选只能说明任务记录被勾选，不能单独证明能力成立。
- `pytest` 的 skip 不是 pass；尤其不能用 skip 的 Durable 测试给 R6 结案。

### 2.1 Harness 对齐协议

这套逐文档审计正式纳入仓库 Harness，但不新增第二套生命周期。职责固定为：

```text
设计文档
  -> 原子 Requirement ID
  -> 源码/配置责任边界
  -> 可失败测试
  -> 实际命令、输入、结果
  -> 当前状态与缺口
```

每个设计文档在文末维护自己的“实现对齐目录”；本文维护跨文档索引和阶段结论。
`.harness/templates/design-implementation-alignment.md` 只提供表格模板，不能成为
领域政策或 shadow standard。需要把协议提升为 runtime-service Current Standard 时，
应按 B3 创建 OpenSpec change，完成 owner pre-apply review 后再写入
`apps/runtime-service/docs/standards/`。

各矩阵的 `是否实现` 只有设计要求整体满足时才填 `✅`；`partial`、`missing`、`deferred`、
`blocked` 和 `not-executed` 一律填 `❌`，用于快速查阅，不替代状态和证据字段。

每条完成记录至少包含：

| 字段 | 判定要求 |
| --- | --- |
| Requirement ID | 稳定、原子、不可用一行塞多个能力 |
| Design source | 文档和章节可定位 |
| Phase / normative level | 区分当前阶段、后置和非本阶段要求 |
| Implementation | 源码、配置或部署文件的具体路径和符号/行 |
| Test | 能在实现破坏时失败的测试 |
| Verification | 命令、输入、结果和证据路径 |
| Status | `implemented-local`、`implemented-chain`、`partial`、`missing`、`deferred`、`phase-contaminated`、`blocked` 或 `not-executed` |
| Gap / next action | 缺口责任人或下一阶段动作 |

完成门槛：

1. 代码存在不等于完成，测试存在不等于完成，OpenSpec task 勾选也不等于完成。
2. fake、mock、in-memory 只能证明 local/composition，不能证明生产、Durable 或跨 Worker 能力。
3. 真实外部条件未满足时必须标 `blocked` 或 `not-executed`，不能把 skip 记为 pass。
4. 后续阶段能力标 `deferred`；后续产物进入当前阶段门槛标 `phase-contaminated`，两者都不能
   计入当前阶段完成率。
5. 阶段只能在所有 mandatory rows 不含 `partial`、`missing`、`blocked`、
   `not-executed` 或 `phase-contaminated` 时，才允许使用无条件 `complete`。

当前本地验证结果：

| 检查 | 结果 |
| --- | --- |
| `uv run pytest tests -m "not integration and not durable and not e2e" -q` | `90 passed, 13 deselected` |
| `uv run pytest tests/services/test_r4_capability_demos.py -q` | `10 passed`；覆盖三类 R4 graph 构图、fake MCP、名称冲突和 Backend 初始化失败传播 |
| `RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -m e2e -q` | `1 passed`，真实 DeepSeek E2E |
| `RUNTIME_E2E=1 uv run pytest tests/integration/test_agent_server_auth.py -q` | `2 passed`，local Agent Server Auth -> Context -> Resolver -> Model |
| `uv run pytest tests/e2e -m e2e -q` | `1 skipped`，未设置真实 E2E 条件 |
| `uv run pytest tests/durable -m durable -q` | `9 skipped`，未设置 `RUNTIME_DURABLE_URL` |
| `uv lock --check` | 通过 |
| `uv run python -m compileall -q src tests scripts` | 通过 |
| R6 真实 Docker Agent Server | 阻塞：LangSmith auth 请求返回 HTTP 403，要求 LangGraph Cloud-accessible key 或 license key |

## 3. 逐文档对齐矩阵

### 3.1 总路线、目录和 Runtime 基础

| 文档 | 设计要求 | 当前证据 | 判定 | 是否实现 |
| --- | --- | --- | --- | --- |
| `10-production-agent-platform-roadmap.md` | R0 -> R6 分阶段；Runtime 不复制 Platform 状态机；真实边界需要真实证据。 | 阶段表把 R0-R5 全标为完成，但 R1 Auth、R2 Workflow、R3 完整边界、R4 真实资源和 R6 Durable 证据都不完整。职责边界本身基本保持。 | **部分实现，状态过度乐观** | ❌ |
| `11-agent-service-directory-architecture.md` | `graphs/` 只做稳定导出；Service 以 `agent.py` 为组合根；五个 Demo 分别覆盖 workflow、Deep Agent、MCP、Backend。 | `graphs/` 入口确实只重导出；五个 Service 和 README 存在。R2 的 `reference_agent` 真实模型链成立；`workflow_demo` 不含条件分支/Interrupt/Resume，workflow 专属 README/测试和静态/动态生命周期门禁不完整。 | **部分实现** | ❌ |
| `12-runtime-context-and-local-debug-architecture.md` | Server Auth -> Principal/Policy -> Context -> Resolver；Context 严格拒绝未知字段；本地调试复用正式链路。 | `parse_runtime_context`、Resolver、Auth adapter 和 `RuntimeConfigMiddleware` 已闭合；真实 local Agent Server 测试验证合法 JWT、`temperature=0` Context 和 DeepSeek Model 链。Platform 正式签发链后置。 | **local Agent Server chain 完成，Platform 后置** | ❌ |
| `13-runtime-service-target-code-layout.md` | 新代码位于 `src/runtime_service`；需要 `auth/platform.py`；Graph 注册单一真源；Legacy 不再进入导入链。 | `src/runtime_service`、`graphs/`、`services/` 结构已落地；`auth/` 目录不存在，JWT 代码放在 `runtime/auth.py`；`docs/standards/` 为空；Dockerfile 注册表已与生产配置建立同步门禁。 | **部分实现，目录目标与实际边界仍有漂移** | ❌ |

### 3.2 Contracts、Middleware 和观测

| 文档 | 设计要求 | 当前证据 | 判定 | 是否实现 |
| --- | --- | --- | --- | --- |
| `14-runtime-contracts-and-resolution-design.md` | 五类不可变类型、严格 Context/Auth 校验、纯 Resolver、稳定 hash、已授权配置才能建模。 | 14 号文档逐条目录显示：类型、Context/Resolver、JWT scope/context_hash、Actor Tool 权限交集、snapshot 和 Modeling 均有本地证据；Agent Server Auth 到真实 DeepSeek Model 的 local HTTP 链路也已通过。 | **local Agent Server chain 完成，Platform/Durable 后置** | ❌ |
| `15-runtime-middleware-lifecycle-and-failure-semantics.md` | 显式 Middleware 顺序；Runtime 配置在 Model/Tool 边界复核；按需使用官方限次、Tool Error/Retry；明确取消和错误传播。 | `RuntimeConfigMiddleware`、`ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、`ToolErrorMiddleware`、`ToolRetryMiddleware`、`ModelCallTimeoutMiddleware` 已接入 `reference_agent`；组合测试覆盖 Tool 重试成功、预算耗尽后脱敏错误、未知异常传播、test-only fallback/retry。生产 fallback/retry 策略、Run deadline、PrepareRun、Finalizer 仍未完成或后置。 | **local/组合完成，生产可靠性部分完成** | ❌ |
| `16-runtime-observability-and-langfuse-design.md` | Langfuse fail-soft；metadata allowlist；敏感数据脱敏；诊断日志/指标；Trace 与 Run 状态分层。 | `observability/langfuse.py` 有 lazy client、allowlist、脱敏、诊断 callback、bounded flush；单元测试覆盖隔离和失败降级，归档记录声称有真实 smoke。当前缺少所有 Demo 的完整 Trace 证据、可信 Resolver metadata 自动传播、队列丢弃/延迟等部署指标。 | **部分实现，有条件成立** | ❌ |

### 3.3 Open SWE 借鉴、Tool、Backend 和生命周期

| 文档 | 设计要求 | 当前证据 | 判定 | 是否实现 |
| --- | --- | --- | --- | --- |
| `18-open-swe-to-runtime-event-and-run-explorer-design.md` | 借鉴命令/观察分离、服务端重建可信配置、稳定事件游标；平台事件不能直接等同上游 SSE 或 Trace。 | 当前没有 Runtime Event Store、平台 Run Explorer 或平台 SSE 适配实现。R6 测试调用 Agent Server SDK，但没有自己的 `event_id/sequence` 事件事实源。 | **明确后置，当前未实现** | ❌ |
| `19-runtime-tool-capability-mcp-and-side-effect-design.md` | Tool 显式装配；模型可见与实际执行同时受 Policy 约束；MCP 构图前加载；副作用需要幂等、审批和审计。 | 本地 fake MCP 的显式加载、allowlist 和名称冲突有测试；19 号文档 R4 Harness 已细分。R4 Demo 尚未接入统一 Runtime Policy，缺少写 Tool、审批、幂等、超时、未知结果和 Deep Agents 内置 Tool 复核。 | **部分实现** | ❌ |
| `20-runtime-backend-workspace-skills-and-subagents-design.md` | Thread-scoped Workspace/Sandbox；Skills 只读；Subagent 显式缩权；重启后按持久化 ID 重建资源；不同 Thread/tenant 隔离。 | Deep Agent 的 StateBackend、Bundled Skill、`tools=[]` 声明和 Backend graph 骨架存在；20 号文档 R4 Harness 已细分。没有 Skill 只读、真实文件跨 Turn、Thread Workspace、跨 Worker 重连、内置 Tool 收缩、cleanup 或 namespace 证据。 | **部分实现，只有演示级隔离** | ❌ |
| `22-platform-runtime-contract-design.md` | Platform 生成快照和 Delegation Token；Runtime 验签；命令、事件、幂等、取消和权限边界一致。 | Platform/Runtime 新契约没有在当前 Runtime 链路实现；R6 明确不修改 Platform，P1 才做。 | **明确后置，当前未实现** | ❌ |
| `23-graph-thread-backend-checkpoint-lifecycle-design.md` | Agent Server 持有 Thread/Run/Checkpoint；真实 PostgreSQL/Redis 验证恢复；Backend 不能静默换线程或宿主机目录。 | 本地 `langgraph dev` 能证明部分 Thread/Run/Checkpoint 协议；真实 PostgreSQL/Redis Agent Server 被 entitlement 阻塞；Backend Demo 不是生产 Backend。 | **部分实现，Durable 边界阻塞** | ❌ |
| `24-package-langgraph-startup-shutdown-design.md` | `langgraph.json` 是 Graph 真源；启动失败闭合；Agent Server 管 Queue/Run/Checkpoint/shutdown；动态资源明确释放。 | 本地启动、生产配置和 Docker Graph 注册同步门禁存在；没有正式 Agent Server drain/lease/recovery 证据；启动失败闭环和 MCP client 生命周期也没有明确验证。 | **部分实现** | ❌ |

### 3.4 测试、模型路由、整合和研究

| 文档 | 设计要求 | 当前证据 | 判定 | 是否实现 |
| --- | --- | --- | --- | --- |
| `25-runtime-testing-and-cross-service-contract-design.md` | Unit/Composition/Integration/Durable/E2E 分层；真实模型 E2E 不静默降级；Durable 不能用内存替代。 | 测试目录和 markers 已建立，快速测试和真实模型门槛基本遵守；没有当前可执行的跨服务契约 fixtures；Durable 默认全 skip，真实部署链未通过。 | **部分实现** | ❌ |
| `26-runtime-custom-routes-and-model-config-design.md` | 不建设 Custom Route；Platform 管模型目录和快照，Runtime 只做本地能力校验与 Model 构造。 | 没有 Custom Route，符合“不建设”；Runtime 本地 Modeling 已实现。Platform 管理、快照绑定和正式 Gateway 尚未开始，属于 P1 前置缺口。 | **按设计不建设 Custom Route；整条配置链未完成** | ❌ |
| `27-platform-runtime-integration-phased-design.md` | 先完成独立 Runtime，再通过 Gateway/Token/快照进入 Platform 阶段。 | Runtime 尚未通过 R6；没有进入 Platform Gateway 实施。文档的分阶段方向正确，但前置条件未满足。 | **未完成，按计划后置** | ❌ |
| `28-runtime-refactor-development-plan.md` | 每阶段有最小门槛；只有真实证据通过才能进入下一阶段；R0-R5 已归档、R6 实施中。 | R1 矩阵已同步为 local Agent Server chain complete；R0 真实 DeepSeek E2E 已通过；R6 verification 仍记录真实 Docker entitlement 阻塞和 Durable 测试环境门槛。 | **R1 已同步，R6 仍阻塞** | ❌ |
| `29-runtime-service-demo-examples-design.md` | 内容并入 28 号文档，不再产生第二份规范。 | 已明确只保留跳转说明，没有产生额外实现要求。 | **已正确收口** | ✅ |
| `30-agent-server-replacement-research.md` | 替换 Agent Server 只能按完整 R6 硬门槛验证；候选替换不能用 SDK 连接或 mock 冒充 Durable。 | 研究文档对 per-Run factory、Durable、Replay、HITL、Policy 和回滚门槛定义清楚；Aegra 仍是 Spike，不能替代正式 R6。 | **研究结论成立，生产能力未实现** | ❌ |

## 4. 当前真正已经实现的能力

以下能力可以认定为当前代码真实拥有，但要限定在“本地/单进程/单元或组合测试”范围：

1. `src/runtime_service` 新包、稳定 `graphs/<graph_id>.py` 导出和 `get_agent(config) -> Pregel` 入口。
2. 五类 frozen dataclass Runtime 类型。
3. 严格 Context、Principal、Policy 解析，未知字段和身份字段拒绝。
4. 纯函数 Runtime 配置合并、Tool allowlist、Prompt hash 和 config hash。
5. 本地 JWT 验签函数，包含 issuer、audience、时间、类型和 tenant/project 一致性校验；这不等于
   完整 scope 或 Context hash 校验。
6. DeepSeek/OpenAI 中转模型的显式构造，缺少凭据时不自动降级 fake。
7. `reference_agent` 的显式只读 Tool、模型可见过滤和 Tool 执行前名称检查。
8. 模型/Tool 调用上限和单次异步模型超时。
9. `workflow_demo` 的最小 Typed `StateGraph`。
10. Deep Agent、Bundled Skill、显式声明但尚无真实委派证据的 Subagent、fake MCP 和进程内 StateBackend Demo。
11. Langfuse lazy 初始化、metadata allowlist、脱敏、诊断 callback、指标计数和 bounded flush。
12. R6 测试脚手架、Compose、版本锁定和本地 smoke 命令。

这些能力足以支撑本地学习和继续开发，但不足以声明“生产 Runtime 框架已完成”。

## 5. 未实现或没有证据的关键能力

### P0：必须先修，否则不能进入 P1

1. **Platform 签发链**：当前 shortest chain 使用 local signer fixture；Platform Gateway、快照签发和正式
   Gateway payload 不属于本 change，不能用 Runtime 单测代替。
2. **Workflow 恢复样例**：`workflow_demo` 需要最小真实 Interrupt/Resume 和至少一个条件
   分支，否则 11 号文档对 Demo 的描述是假的。
4. **真实 Durable 证据**：需要可用的正式 Agent Server entitlement/license，或经过批准的
   等价替换方案，跑通 PostgreSQL、Redis、Worker 重启、SIGTERM、Checkpoint、Replay、
   cancel、timeout、Tool failure 和唯一终态。
5. **测试语义修正**：Durable 缺环境时必须在报告中明确为 blocked/not executed；不能让默认绿色
   CI 被误读为 R6 通过。

### P1：进入 Platform 整合前必须冻结

1. RuntimeContext、Delegation claims、Policy version 和配置快照的真实 HTTP 位置。
2. Platform Run ID 与 Runtime Run ID 的关联方式。
3. `event_id/sequence/since` 的事实源和 cursor-expired 行为。
4. Deep Agent 内置 Tool 的 Capability Policy 和执行前复核。
5. Backend/Sandbox 的 Thread 绑定、跨 Worker 重连、资源清理和失败闭合。

### 本阶段明确不应提前实现

- 公共 Builder、Factory、Registry、Provider 插件框架；
- Runtime 内第二套 Run Coordinator、事件总线或自定义 Checkpointer；
- Custom Route、模型配置 CRUD、Platform API 复制实现；
- 为尚无真实需求的 Tool 审批平台、通用 Sandbox 抽象或独立 Subagent Run 状态机。

## 6. 最小收敛顺序

1. **先修状态和真源**：把 10、28、`docs/README.md`、部署 README 的阶段状态统一为
   `partial/blocked`；明确 `docs/standards/` 尚未生成；移除或生成 Dockerfile 中重复的
   Graph 注册来源，不能两边各写一份。
2. **补 Workflow 最小能力**：只改 `workflow_demo`，增加一个真实条件分支和一个可恢复
   Interrupt/Resume 节点，配一条失败测试。不要借此创建通用 workflow framework。
4. **取得 R6 真实环境**：完成 entitlement/license 或正式批准的替换 Server 选择，再执行现有
   Durable 测试；测试本身先修正“中间 cursor、两次 interrupt、恢复 checkpoint、唯一终态”
   的断言，避免只等 terminal status。
5. **R6 通过后再做 P1**：Platform Gateway、配置快照、Run Event 投影、Run Explorer 和跨服务
   契约另起 governed change，不把 Platform 代码提前塞进 Runtime。

## 7. 接受标准

本审计建议将“阶段完成”改成下面的可判定状态：

| 状态 | 允许含义 |
| --- | --- |
| `local-complete` | 本地代码、单元/组合测试和最小启动证据成立，不代表生产或跨进程能力。 |
| `chain-complete` | 最短真实调用链成立，包括真实 Agent Server 和必要外部依赖。 |
| `blocked` | 代码可能存在，但所需外部条件未满足，不能宣称通过。 |
| `deferred` | 设计明确后置，本阶段不计入缺陷，但后续阶段必须重新验收。 |

按这个定义，当前建议状态为：

```text
R0 capability-local-complete / alignment-partial
R1 capability-chain-complete-local-agent-server / platform-durable-deferred
R2 capability-local-complete-local-agent-server / reference-lifecycle-incomplete
R3 reliability-core-local-complete / provider-fallback-production-incomplete
R4 demo-local-complete / production-resources-deferred
R5 adapter-local-complete / full-propagation-incomplete
R6 blocked
P1 deferred
```

在 R6 真实证据出现前，任何 README、路线图或 OpenSpec 归档记录都不应使用无限定的
“R0-R5 全部完成，因此 Runtime 可作为 Platform 执行面”的表述。

## 8. R4 Apply 对齐目录（2026-09-01）

本节是总审计对 R4 apply 的覆盖记录。`是否实现` 只表示该行在 local harness 范围有代码和可失败
验证；生产 Durable、跨进程资源和真实副作用必须看证据等级，不能由本地测试升级。

| Requirement | 是否实现 | 实现位置 | 测试/验证位置 | 证据与未覆盖边界 |
| --- | --- | --- | --- | --- |
| Tool Policy 同时约束模型可见与执行前调用 | ✅ | `src/runtime_service/middlewares/runtime_config.py`；R4 三个 Service `agent.py` | `tests/services/test_r4_capability_demos.py` | `44 passed`；伪造 `execute/task` 被拒绝 |
| MCP 显式加载、名称冲突、required/optional 失败 | ✅ | `services/mcp_demo/loader.py` | `tests/services/test_r4_capability_demos.py` | 本地 stdio fake；无远程凭据、重连、取消证据 |
| Bundled Skill 只读 | ✅ | `services/deep_agent_demo/agent.py` | `test_deep_agent_rejects_skill_write_before_backend_execution` | `/skills/**` 写入在 handler 前失败；未实现 User/Organization Skill |
| Thread Workspace 本地隔离与 graph rebuild | ✅ | `services/backend_demo/agent.py` | `test_backend_workspace_survives_graph_rebuild_for_same_thread`；`test_backend_workspace_isolated_between_threads` | `InMemorySaver` 仅证明本地协议，不证明 Worker/服务重启恢复 |
| Subagent 实际缩权委派 | ❌ | `deep_agent_demo/agent.py` 有 `tools=[]` 配置 | 无真实 delegation/事件隔离测试 | OpenSpec `3.4` 未完成 |
| Backend scope mismatch、资源清理、跨 Worker Durable | ❌ | 尚无生产资源 binding/cleanup 实现 | OpenSpec `5.4/5.5/5.6` 未执行 | Agent Server entitlement、PostgreSQL/Redis、Sandbox 前置条件缺失，状态为 `blocked/not-executed` |

结论：R4 为 `local-complete / production-chain-blocked`；R6 在真实 Durable 证据出现前不得结案，
P1 Platform 整合仍以后置为准。

## 9. R5 Harness 对齐目录（2026-09-01）

本节汇总 [16 号文档](./16-runtime-observability-and-langfuse-design.md) 的逐项审计；详细实现位置和
测试位置以 16 号文档第 15 节为准。

| 能力 | 是否实现 | 实现位置 | 测试/验证位置 | 结论 |
| --- | --- | --- | --- | --- |
| Langfuse 开关、缺失配置失败、lazy adapter | ✅ | `observability/langfuse.py`、`webapp.py` | `uv run pytest tests/observability -q`：`25 passed`；dev server 和目标镜像均加载 custom app | 本地 lifespan 成立；目标镜像被 entitlement `403` 阻断在 application startup 前 |
| 五个 Demo 统一接入 Callback | ✅ | 五个 `services/*/agent.py` 返回边界 | `tests/services/test_r4_capability_demos.py`；Runtime 全量测试 | 统一接线成立，workflow 保持匿名技术 Trace |
| metadata allowlist、身份信任和 tag 边界 | ✅ | `_approved_metadata()`、`_trusted_metadata()`；四个解析 Service trusted 摘要 | `tests/observability/test_langfuse.py`；Graph tests | 未验证身份不会生成 `langfuse_user_id` |
| 脱敏与正文丢弃 | ✅ | `_redact()`、`_mask()` | 观测专项和真实 smoke | 仅局部 DLP，不等于完整业务 secret 检测 |
| Run/Tool/Token/取消/超时诊断 | ✅ | `_RuntimeDiagnosticsCallback` 与 Counter | 观测专项、真实 Agent/Deep Agent graph tests | Runtime 字段契约成立，远端 exporter 不由 Runtime 自建 |
| fail-soft、bounded flush、队列丢弃 | ❌ | `_FailSoftCallback`、`close_langfuse()` | callback failure、flush error/timeout 和原始异常语义已通过 | SDK queue 有界但 `event_dropped` 未接入 Runtime Counter；生产 SIGTERM 未证明 |
| Model/Tool/Subagent Trace 层级和真实 Langfuse smoke | ✅ | 统一 callback；`tests/e2e/test_langfuse_real.py` | `test_graph_tracing.py`；真实 Langfuse smoke `1 passed`；真实 DeepSeek `1 passed` | 已证明本地传播和真实 client/flush，未查询服务端最终 observation 树 |
| Cross-service trace propagation | ❌ | 仅消费调用方传入 metadata | Platform/Gateway 传播按设计后置 |

R5 当前状态：`runtime complete-local / production-exporter partial`。本地生命周期、callback 传播和
Langfuse smoke 已成立；目标镜像只证明 custom app import 和 PostgreSQL/Redis 连接，entitlement `403`
阻止了 application startup 与 SIGTERM 验证。queue drop、目标生产容器生命周期和跨服务传播仍保持
未完成，不能因为 R6 已在实施就跳过这些缺口。
