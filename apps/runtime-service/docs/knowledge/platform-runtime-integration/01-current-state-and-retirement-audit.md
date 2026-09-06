# P1 现状与退役审计

- 文档类型：Draft Supporting Audit
- 状态：owner 已批准处置方向；实施与归档进行中
- 审计日期：2026-09-03
- 规范真源：[`redesign-platform-runtime-integration`](../../../../../openspec/changes/redesign-platform-runtime-integration/)

## 1. 审计标准

这里的“过时”不是指文件老，而是命中下列任一项：

1. 假设 upstream 是旧 `runtime-service/langgraph dev`，没有 GraphHarbor API/Worker 边界；
2. 让前端或 Platform API 使用当前 RuntimeContext 不接受的字段；
3. 同一 Thread/Run/Agent 在多个数据库拥有可写真相；
4. 绕过统一 IAM、Project Policy、Context hash、delegation 或审计入口；
5. 复制官方 SDK 已经负责的 live stream 状态；
6. 仍宣称已完成，但真实最短链或 owner 产品验收不成立。

处置词义：

| 处置 | 含义 |
| --- | --- |
| Keep | 目标职责正确，可在 characterization test 保护下复用 |
| Rewrite | 文件/模块位置可保留，但行为契约必须按新 spec 重写 |
| Delete after proof | SDK/新路径覆盖且兼容 fixture 证明无需保留后删除 |
| Superseded | 立即停止作为新实现依据，暂留原位供讨论追溯 |
| Archive after acceptance | owner 批准矩阵并完成必要信息迁移后物理移动 |
| Absorb | 有效需求并入本 P1 change，再结束原 change |

## 2. 已确认的实现偏差

| ID | 当前位置 | 当前事实 | 目标判断 | 是否满足目标 |
| --- | --- | --- | --- | --- |
| `AUD-WEB-01` | `apps/platform-web/src/services/runtime/runtime-contract.ts` | 正式 Chat 仍生成 `platform_runtime/system_prompt/enable_tools` | Runtime 不接受后两项；旧字段不得直达 Runtime | ❌ |
| `AUD-WEB-02` | 同上 | `enableTools=false` 会删除 `tools` | 缺失与 `tools: []` 语义不同，可能恢复默认工具 | ❌ |
| `AUD-SDK-01` | `@langchain/vue 1.0.29` | v2-native `useStream` 使用 `/commands`、`/stream/events`、`/state` | 路径选择正确，应保留 SDK owner | ✅ |
| `AUD-SDK-02` | `@langchain/protocol 0.0.18`、SDK `StreamSubmitOptions` | v2 `run.start` 不声明/转发顶层 `context` | 必须先选择 Context transport，不可假设已支持 | ❌ |
| `AUD-API-01` | `runtime_gateway/presentation/http.py` | service dependency 初始化时签发空 Context hash 通用 token | 应在目标/Context 决议后按操作签发 | ❌ |
| `AUD-API-02` | `runtime_gateway/application/service.py` | create/stream/wait/batch/cron 多入口分别注入 scope/default model | Run create 没有唯一治理用例 | ❌ |
| `AUD-API-03` | `runtime_gateway/infra/sqlalchemy/models.py` | `runtime_runs` 缺 Agent key、Graph、Policy、Context snapshot/hash | 不能证明 Run 使用的不可变治理输入 | ❌ |
| `AUD-API-04` | `assistants/application/service.py` | Platform 产品记录同时创建/更新 upstream Assistant | 三套 ID 和双库同步，不符合单一 owner | ❌ |
| `AUD-API-05` | `runtime_catalog`、`RuntimeToolsPage.vue`、`ChatRunOptionsDialog.vue` | Platform 暴露 Tools 目录和每次运行 Tools 选择 | Tools 应由 Runtime Agent/服务端策略决定，浏览器不能修改 | ❌ |
| `AUD-API-06` | `runtime_catalog`、`RuntimeModelsPage.vue` | 当前模型目录主要是 upstream 只读同步，没有平台录入和安全凭据引用闭环 | 管理员录入的模型必须能通过受信 resolver 到达 Runtime，且密钥不出服务端 | ❌ |
| `AUD-GH-01` | GraphHarbor `libs/langhost/src/langhost/protocol_api.py` | v2 只将协议已有少数字段转入 `runs_create` | v2 本身可用；标准 Runs API Context/选项仍需 Profile 实测 | 部分 |
| `AUD-DATA-01` | Thread project metadata 检查 | 当前 Gateway 主要依赖 metadata 判断归属 | metadata 只能辅助，不能是唯一授权依据 | ❌ |

## 3. Platform Web 代码处置矩阵

| 表面 | 目标职责 | 处置 | 实施前证明 |
| --- | --- | --- | --- |
| `src/modules/chat/pages/ChatPage.vue` | Chat workspace 页面编排 | Keep + thin rewrite | 页面路由、空态、错态、响应式 characterization |
| `components/BaseChatTemplate.vue` 与已验收展示组件 | 视觉/交互展示 | Keep | component tests 与 owner UAT；不得重做另一套壳 |
| `composables/usePlatformChatStream.ts` | 唯一 SDK stream binding | Rewrite | 真实 SDK request fixture、Thread switch、HITL、cancel |
| `composables/useChatWorkspace.ts` | 页面级组合，不拥有 Runtime state | Rewrite/keep thin | 状态所有权测试，不得镜像 SDK writable state |
| `composables/useChatThreadWorkspace.ts` | Product thread list/search/selection | Rewrite | 只经 Platform API；与 live Thread state 分离 |
| `composables/platform-chat-stream/actions.ts` | 旧 send/retry/resume/cancel 编排 | Delete after proof | SDK selectors/actions 覆盖矩阵逐项通过 |
| `composables/platform-chat-stream/helpers.ts` | 旧 Runtime payload/状态辅助 | Delete or shrink | 无调用者、无兼容 fixture 需求 |
| `branching.ts`、`history-view-model.ts`、`interrupt.ts` | 只读展示或 SDK 参数映射 | Characterize then keep/delete | SDK checkpoint/interrupt API 真实测试 |
| `runtime-contract.ts` | Product DTO 与模型/生成参数归一化 | Split/rewrite | 删除非法字段和浏览器 Tools 输入，未知字段 fail closed |
| `runtime.service.ts` | Platform product API 与允许的 Thread 查询 | Keep + narrow | 不拼 upstream URL，不含 legacy fallback |
| `ChatDebugPage.vue` | 独立 debug 工作台 | Delete after proof | owner 已同意删除；调试转移到 Runtime Web/测试工具 |

不做整目录删除。SDK 已覆盖的状态机必须删除，但只有逐项 characterization 才能判断哪些 view model
仍承担产品展示职责。

## 4. Platform API 代码处置矩阵

| 模块/表面 | 目标职责 | 处置 | 实施前证明 |
| --- | --- | --- | --- |
| `modules/assistants` domain/repository/API | 迁移为 Agent 产品目录和 `(project_id, agent_key)` 策略 | Rewrite/rename | Agent scope、唯一 `agent_key`、disabled target denial |
| `adapters/langgraph/assistants_client.py` | 当前 upstream Assistant CRUD | Delete after migration | Platform 不再镜像 upstream Assistant；旧数据已回填 |
| `modules/runtime_catalog` | 已部署 Agent/model 的只读 snapshot；Tool 只作内部安全数据 | Keep + narrow | refresh source、revision、stale/failure 行为；不向前端开放 Tool 编辑 |
| `modules/runtime_policies` | Project allowlist/default/limit | Keep + tighten | deny-first、revision、模型决议和 Runtime 内部 Tool 三态 |
| `runtime_gateway/presentation/http.py` | 显式 SDK endpoint allowlist | Rewrite/shrink | 路由清单、读写权限、SSE pre-auth |
| `runtime_gateway/application/service.py` | Thread ownership + Run governance use cases | Rewrite | 所有 Run create caller 进入统一入口 |
| `runtime_gateway/infra/sqlalchemy/models.py` | 最小 Run governance ledger | Forward migration | snapshot/hash/ID/idempotency 不可变约束 |
| `adapters/langgraph/*_sdk_adapter.py` | 标准 Agent Server client mapping | Keep where needed | SDK/Profile contract tests；重复 raw client 删除 |
| `adapters/langgraph/runtime_client.py` | Protocol v2 HTTP/SSE transport | Keep or merge after caller audit | cancellation、error body、header redaction |
| `core/security/tokens.py` | delegation primitive | Keep | 调用点移到决议后的 application use case |
| Cron/Batch/Store/System gateway routes | 尚未确认的产品 surface | Pending decision | 没有产品 owner 和测试不得进入正式 allowlist |
| `runtime_run_interrupts` | interrupt 与 governance Run 的最小关联 | Keep only if needed | GraphHarbor 仍是 interrupt payload 事实源 |

## 5. 文档生命周期矩阵

| 文档 | 当前问题 | 拟处置 | 现在是否物理移动 |
| --- | --- | --- | --- |
| `apps/runtime-service/docs/knowledge/22-platform-runtime-contract-design.md` | 混合旧 Runtime 直连与新 v2 讨论，已不再是 P1 真源 | Superseded -> archive | 否 |
| `apps/runtime-service/docs/knowledge/27-platform-runtime-integration-phased-design.md` | 阶段原则有价值，但 payload/Assistant/数据设计已变化 | Superseded -> archive | 否 |
| `apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md` | R0-R6 历史仍有效，P1 细节不应继续膨胀 | Keep，只保留 P1 入口/顺序/门槛 | 否 |
| `apps/platform-web/docs/chat-langchain-vue-migration-blueprint.md` | 迁移计划和 2026-04 联调事实已过期，部分 SDK 原则仍有效 | 提取仍有效原则后 archive | 否 |
| `apps/platform-web/docs/chat-frontend-refinement-plan.md` | 混合历史联调状态与仍有效 UX 规则 | UX 规则并入 leaf standard，计划 archive | 否 |
| `apps/platform-api/docs/decisions/chat-use-stream-contract.md` | 依赖旧 Runtime payload，未覆盖 GraphHarbor Context 冲突 | 新 design 批准后 Superseded/archive | 否 |
| `apps/platform-api/docs/handbook/architecture.md` | Current 架构图仍写 Platform API 直达 Runtime | Update，不能 archive | 否 |
| `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md` | 核心边界正确，但需把 compatible Agent Server/GraphHarbor 写清 | Update，不能 archive | 否 |
| `apps/platform-api/docs/diagrams/agent-chat-flow.svg` | 需要与新时序一致 | Regenerate after contract freeze | 否 |
| `apps/platform-api/docs/delivery/runtime-contract-*.md` | 历史联调 checklist，不能继续当 P1 完成依据 | 验证是否已有历史价值后 archive | 否 |

建议归档到各自 leaf 的 `docs/archive/`，保留原 owner，而不是把所有历史资料搬到根目录形成新的垃圾堆。

## 6. Active OpenSpec 处置矩阵

| Change | 已知状态/重叠 | 拟处置 | 依据 |
| --- | --- | --- | --- |
| `add-react-agent-web` | owner UAT 已明确 Rejected | archive without sync | 不再继续该产品实现；技术证据仅作历史参考 |
| `runtime-run-event-contract-and-run-explorer` | 与 P1 ledger/audit/UI 重叠 | Deferred：P1 后按 GraphHarbor 事实源重新设计 | Run Explorer 不是 P1 验收门槛，不同步与新事实源冲突的旧设计 |
| `platform-runtime-graphharbor-canary-routing` | 与 owner 已 deferred Platform 灰度冲突 | Abandoned 后 archive without sync | 当前只做单 upstream GraphHarbor，不做 canary |
| `redesign-platform-runtime-integration` | 本专项 | Continue, pre-apply pending | 唯一 P1 规划真源 |

历史 `openspec/changes/archive/` 不修改。Active change 的 disposition、sync 和 archive 都要单独记录，
不能通过删除目录伪造结束。

## 7. 物理归档门槛

只有同时满足以下条件才执行移动/删除：

1. owner 批准本矩阵及目标架构；
2. 有效需求已经进入 active spec/current standard，不靠旧文件维持；
3. 代码删除项有调用者检查和 characterization/替代测试；
4. active OpenSpec 写明 `Accepted/Rejected/Abandoned` 和 sync 决策；
5. 所有移动使用一次性清单执行并通过链接检查，不边实现边零散搬文件。
