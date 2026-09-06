# Platform Runtime Integration 专项

- 文档类型：Draft Supporting Navigation
- 状态：总体方案已确认；L1/L2 本机闭环已完成，L3 已完成服务端真实 HITL 链和浏览器页面冒烟，完整浏览器 E2E 与 owner UAT 仍保留门禁（2026-09-05）
- Owning loci：`apps/platform-web`、`apps/platform-api`
- Execution band：B3 Governed
- OpenSpec 真源：[`redesign-platform-runtime-integration`](../../../../../openspec/changes/redesign-platform-runtime-integration/)

## 1. 专项要解决什么

本 README 是整个专项的总体规划和导航，不是单独的 P0 任务清单。当前实施阶段统一使用
`L1/L2/L3`：`L1` 等同于当前 P0 的模型配置基础闭环；旧“P0 外部生产模型代理门禁”已经废弃，
只保留在 OpenSpec verification 中用于历史追溯。

Runtime R0-R6 已经把执行面重构为 GraphHarbor API + Worker + PostgreSQL + Redis，并由 Worker
加载 `runtime-service` graphs。旧 Platform Runtime 设计早于这条边界，当前前端、平台后端、文档
和测试仍混有旧 payload、多套 Assistant/Graph 标识、重复 Thread/Run 状态和未统一的治理入口。

本专项先把架构、处置范围、任务和验收门槛讨论清楚，再进入实现。它不复用旧结论冒充新设计，也
不因旧代码存在就默认必须保留。

## 2. 关于 LangGraph SDK 与 GraphHarbor 的结论

对平台上层来说，两者本来就应该配合使用：

```text
LangGraph SDK = 浏览器客户端
GraphHarbor    = LangGraph-compatible Agent Server
```

目标链路是：

```text
platform-web
  -> @langchain/vue / @langchain/langgraph-sdk
  -> platform-api /api/langgraph
  -> GraphHarbor API
  -> Redis
  -> GraphHarbor Worker
  -> runtime-service graph
  -> GraphHarbor PostgreSQL
```

因此前端不得出现 GraphHarbor 专用分支。但“上层无感”必须由 Compatibility Profile 证明，不能只
看路由名相似。当前锁定 SDK 的 Protocol v2 使用 `/commands`、`/stream/events` 和 `/state`；
GraphHarbor 必须对这些路径、envelope、SSE、取消、重连和失败语义兼容。

## 3. 阅读顺序

1. [现状与退役审计](./01-current-state-and-retirement-audit.md)：哪些旧内容可保留、应重写或拟归档。
2. [目标架构与契约](./02-target-architecture-and-contract.md)：前端、平台后端、GraphHarbor 和 Runtime 如何交互。
3. [模块迁移与验收 Harness](./03-module-migration-and-acceptance.md)：阶段、改造点、测试矩阵和最终确认清单。
4. [推荐基线与未决问题](./04-recommended-baseline-and-open-decisions.md)：逐项讨论顺序、推荐方案、拒绝方案和验收门槛。
5. [Open SWE 模型代理分析与本项目设计](./05-open-swe-model-proxy-analysis-and-design.md)：参考实现和 V1 最小模型配置。
6. [模型配置实施约束最佳实践基线](./06-implementation-constraint-recommended-baseline.md)：字段、加密、脱敏、校验和验证落点。
7. [本地三阶段实施与验收计划](./07-local-three-stage-delivery-plan.md)：把本地合同闭环、最短真实链和生产形状模拟拆开，逐项记录概念、代码落点、验证和状态。
8. [DeepSeek Harness 模型录入借鉴与最小方案](./08-deepseek-harness-model-entry-reference.md)：URL、Key、Model、协议字段、存储和脱敏边界。
9. [Compatibility Profile](./09-compatibility-profile.md)：锁定 SDK、GraphHarbor、Runtime 版本和 allowlist。
10. [实施状态与验证记录](./10-implementation-status.md)：按 Harness 记录功能点、代码落点、验证命令、结果和未覆盖边界。
11. [Agent/Thread 统计与保留策略](./11-agent-thread-statistics-retention.md)：当前事实源、统计口径、保留边界和历史数据清理门槛。
12. [模型目录与前端信息架构简化方案](./12-simplified-model-and-ui-plan.md)：移除 profile/E2E 门禁，收敛 Agent、Graph、Models 和 Runtime Policy 的产品边界。
13. [OpenSpec proposal](../../../../../openspec/changes/redesign-platform-runtime-integration/proposal.md)：Why、范围和 capability。
14. [OpenSpec design](../../../../../openspec/changes/redesign-platform-runtime-integration/design.md)：完整技术取舍与 open questions。
15. OpenSpec `specs/`、`tasks.md`、`verification.md`：批准后的规范、执行任务和唯一证据记录。

项目级 Harness 文档见 [`docs/platform-runtime-integration/`](../../../../../docs/platform-runtime-integration/README.md)：
其中记录完整的项目 intake、owner 决策、实施阶段、证据矩阵和开放约束；本目录继续保留 Runtime 侧的详细技术材料。

平台 Chat 文字 Harness 见 [`apps/platform-web/docs/chat-frontend-harness.md`](../../../../platform-web/docs/chat-frontend-harness.md)：这是 send/stream/reopen/HITL/cancel 的人工执行卡和证据真源。

## 4. Harness Intake

| 字段 | 本专项答案 |
| --- | --- |
| Goal | Platform Web 通过标准 LangGraph SDK，经 Platform API 治理后稳定使用 GraphHarbor |
| Locus | `platform-web` + `platform-api`；GraphHarbor 只承担通用兼容修复 |
| Chain | Web -> Gateway -> GraphHarbor API -> Redis -> Worker -> Runtime graph -> PostgreSQL |
| Authority | 两个 Platform leaf standards、Runtime contracts、GraphHarbor Compatibility Profile、active OpenSpec specs |
| Band | B3 Governed：公开契约、权限、数据所有权、migration 和跨仓库兼容均受影响 |
| Evidence | local contracts -> Platform API/GraphHarbor shortest chain -> 浏览器真实链与 owner UAT |
| Acceptance | owner 批准全部 artifacts 后才能 apply；真实链和 UAT 通过后才能清理/归档 |

## 5. 当前决策台账

| ID | 决策 | 状态 |
| --- | --- | --- |
| `P1-D01` | GraphHarbor 是 Agent Server，Platform API 是控制面 Gateway | Accepted by owner |
| `P1-D02` | Platform Web 只使用官方 LangGraph SDK，不识别 upstream 类型 | Accepted by owner |
| `P1-D03` | 平台产品统一使用 Agent；`agent_key = graph_id`，SDK 的 `assistantId` 只作为兼容参数名 | Accepted by owner |
| `P1-D04` | GraphHarbor 持有 Thread/Run/Checkpoint/Event 事实；Platform 只持治理记录 | Accepted by owner |
| `P1-D05` | 所有 Run create 入口进入同一个 Platform application use case | Accepted by owner |
| `P1-D06` | Agent Server 边界使用标准顶层 `context`，不把身份或配置写入 graph state | Accepted by owner |
| `P1-D07` | Protocol v2 缺少 `context` 时选择 Gateway server-side promotion，不 fork 官方 SDK | Accepted by owner |
| `P1-D08` | Gateway 只暴露产品需要的 Agent Server endpoint allowlist | Accepted by owner |
| `P1-D09` | Langfuse/OTLP、生产灰度、性能 SLO 和自动回滚不属于当前 P1 | Deferred |
| `P1-D10` | 旧资料先解除权威；处置矩阵批准后才物理 archive/delete | Accepted by owner |
| `P1-D11` | 模型由平台录入；七字段最小化管理，密钥只写不读并服务端加密 | Accepted by owner |
| `P1-D12` | Tools 不提供平台前端配置；Runtime Agent 和服务端策略负责决定可用 Tools | Accepted by owner |
| `P1-D13` | `ChatDebugPage` 删除，调试使用 Runtime Web、测试工具或独立后续专项 | Accepted by owner |
| `P1-D14` | Run Explorer 不属于 P1，后续按 GraphHarbor 事实源重新设计 | Deferred |
| `P1-D15` | 历史 Thread 只为真实且必须保留的数据维护读取 fixture；无需求的 fallback 删除 | Inventory complete; owner deletion gate completed; legacy column/code cleanup remains separate |
| `P1-D16` | Platform canary 灰度不实施，相关 change 标记 Abandoned 后归档 | Deferred |
| `P1-D17` | Thread 创建先绑定 Project，第一次 Run 绑定 `agent_key`，之后不可切换；切换 Agent 创建新 Thread | Accepted by owner |
| `P1-D18` | 生产 delegation 使用 RS256/JWKS 的方案 | Superseded/Rejected；另立 change 才能重新讨论 |
| `P1-D19` | Run intent/outbox、Idempotency-Key 和 reconciliation 处理超时与重复创建 | Accepted by owner |
| `P1-D20` | 模型使用服务端保存的逻辑 `model` 配置到达 Runtime | Accepted by owner |
| `P1-D21` | Runtime `context` 只使用现有字段；浏览器不提交 Tools；缺失、空列表和服务端子集语义分离；未知字段 fail closed | Accepted by owner |
| `P1-D22` | 生产模型代理、Secret Store、revision、JWKS 和 workload identity | Superseded/Rejected；不进入当前实现 |
| `P1-D23` | Agent/Thread 统计与保留 | Agent catalog 以 `langgraph.json`/GraphHarbor graph catalog 为源；Thread/Run 以 GraphHarbor 为事实源；Platform 只保留治理关联；active/HITL 不自动清理；旧 Assistant 数据需 owner 确认后删除 | Accepted baseline; destructive cleanup pending |

### 当前对象与统计口径补充

- `apps/runtime-service/langgraph.json` 是可执行 Agent 的发布注册表；当前正式 graph 为 `reference_agent`。
- GraphHarbor graph catalog/API 是运行时读取入口；Platform 的 `agents` 只表示某个 project 是否绑定、启用并配置了该 graph，不能反向生成不存在的 graph。
- 当前 `dev` 项目已绑定 `reference_agent`、`workflow_demo`；没有 catalog 同步权限或项目绑定时，Agent 数可以为 0，这不是把历史 Assistant 自动改名为 Agent 的理由，也不能用 fake/mock 数据填充验收。
- Thread、Run、Checkpoint、Event 只以 GraphHarbor PostgreSQL 为事实源；Platform `runtime_runs` 只做治理投影、幂等和审计关联。
- active、HITL waiting、reconciliation 未收敛的 Run 都算 active；SSE 断开不取消，只有显式 Stop/Cancel 才改变状态并释放 Thread。
- 已完成数据的清理窗口由 GraphHarbor retention 配置决定；未明确窗口前本地不自动 prune。旧 `graph_id=assistant` 记录/profile 已获 owner 确认并删除，不级联 GraphHarbor Thread/Run。
- 用户通过 `/workspace/models` 维护 `provider`、`display_name`、`base_url`、`protocol`、`model`、`api_key`、`enabled` 七字段；API key 只写不读并由 Platform API 加密保存。模型目录是 Runtime 执行配置的唯一来源。
- `RUNTIME_MODEL_PROFILE` 和 `RUNTIME_E2E` 已从启动示例和测试门禁移除。五个本地服务启动后默认就是完整链路，Provider smoke 使用独立测试目录或 pytest marker。

## 6. 状态纪律

- 本目录是 supporting knowledge，不覆盖 leaf current standard 或 OpenSpec spec。
- 本目录的清单用于导航，不记录实施勾选和命令结果；唯一执行状态在 `tasks.md`，唯一证据在
  `verification.md`。
- [推荐基线与未决问题](./04-recommended-baseline-and-open-decisions.md)保存推荐基线、已接受决策和剩余
  讨论顺序；owner 接受后同步为 OpenSpec contract，实施状态仍以 `tasks.md` 和 `verification.md` 为准。
- 当前状态为 `L1 local-complete; L2 local-complete; L3 partial`；实现和证据仍以 `tasks.md`、`verification.md` 为准。
- 旧文件出现 `Superseded` 只表示禁止继续作为新实现依据，不表示已经移动、删除或完成 migration。
- 2026-09-05 实施记录：Gateway 已收窄为正式 Chat allowlist；旧 ChatDebugPage/debug service、Chat 与 Assistant 创建页的 Tools 选择入口、Runtime Tools 管理页路由和导航已删除；Runtime target ownership 优先使用 `(project_id, graph_id)`，Agent CRUD 不再触发 upstream Assistant mutation，历史 assistant id 仅作读取兼容；Platform API 实现已迁移到 `app/modules/agents`，旧 `assistants` 仅保留兼容导出；L2 smoke 已覆盖 Thread search/count/get、State/History、标准 Runs 选项和 API/Worker restart，workflow_demo HITL respond 已通过。模型配置现在经 Gateway 签发短期 opaque reference，Runtime 通过内部端点读取解密连接；Platform API 定向 29 项、Runtime 8 项和 Web typecheck 通过。完整实施状态仍以 OpenSpec `tasks.md` 与 `verification.md` 为准。
