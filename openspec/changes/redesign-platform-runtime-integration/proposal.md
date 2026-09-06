## Why

> 方案处置（2026-09-04）：此前关于统一模型代理、`execution_model_id`/revision、Secret Store 编排和
> RS256/JWKS 的设计已被 owner 明确废弃（`Superseded/Rejected`）。本 change 只实施七字段模型配置、
> API key write-only 与服务端加密；旧设计不再是实施或验收依据。

Runtime R0-R6 已将执行面收敛到由 GraphHarbor 承载的 LangGraph-compatible Agent Server，
但当前 `platform-web`、`platform-api` 及其设计文档仍混有旧 Runtime payload、重复状态所有权、
Assistant/Graph 两套产品命名和未统一的 Run 治理入口。继续在旧契约上补丁式联调会把已经淘汰的假设重新带回
Runtime，因此必须先冻结新的平台到执行面边界，再实施 P1。

本变更的 owning loci 是 `apps/platform-web` 与 `apps/platform-api`，受影响的最短链为
`platform-web -> platform-api /api/langgraph -> GraphHarbor API/Worker -> runtime-service graph`。
它涉及公开契约、权限、数据所有权和迁移，按 B3 Governed 执行。已加载仓库 Harness、
`platform-web` frontend/control-plane leaf standards、`platform-api` handbook 与 runtime gateway、
permission、audit standards，以及 Runtime R0-R6 supporting knowledge。

## What Changes

- 将 GraphHarbor 明确为 LangGraph-compatible Agent Server；平台前端继续使用官方 LangGraph SDK，
  不感知 upstream 是 GraphHarbor 还是其他满足冻结 Compatibility Profile 的 Agent Server。
- 重新定义 Platform Web、Platform API、GraphHarbor、Runtime Agent、PostgreSQL 和 Redis 的职责、
  ID、事实源及请求/状态时序；平台产品统一使用 Agent，`agent_key = graph_id`。
- 新增统一的 Platform Runtime Control Plane 契约：IAM、项目隔离、Agent key 校验、模型目录与安全
  凭据引用、Runtime Policy、不可变 Context snapshot、delegation token、审计和最小 Run governance ledger。
- 收敛所有允许创建 Run 的入口到同一应用服务，确保授权、目标解析、Context hash、幂等和审计不会
  因 REST、Protocol v2 或后续入口不同而绕过。
- 重设计正式 Chat：保留 `@langchain/vue` / `@langchain/langgraph-sdk` 作为运行客户端，保留
  `platform-api` 同源网关；移除前端对旧 Runtime 私有字段和重复 live state 的依赖。
- **BREAKING**：淘汰 Runtime 对 `config.configurable.platform_runtime` 的直接消费，以及
  `system_prompt`、`enable_tools` 等与当前 `RuntimeContext` 不一致的正式输入；浏览器不再配置 Tools，
  Agent Server 边界只接受冻结的标准 `context` 语义，Tool 集合由服务端/Runtime Agent 决定。Web 到
  Gateway 是否保留一个受控模型提示字段由 design 的 Context transport 决策门确定。
- 补齐 GraphHarbor 的通用 Protocol v2 与标准 Runs API 字段兼容性；修复必须留在 GraphHarbor 通用协议层，
  禁止加入本平台的 Project、Agent、IAM 或 Policy 业务规则。
- **BREAKING**：删除 `RUNTIME_MODEL_PROFILE` 和 `RUNTIME_E2E` 作为服务启动/真实链路门禁；服务启动默认
  运行完整本地链路，Provider smoke 通过独立测试目录或 pytest marker 选择。
- **BREAKING**：模型目录成为唯一模型配置来源；Platform 录入的 URL、protocol、model 和加密 API Key
  必须真正参与 Runtime resolver，Chat 支持项目唯一默认模型和单次模型覆盖。
- **BREAKING**：前端产品对象收敛为 Agent 和 Models；Graph 保留为 Runtime 内部部署目录，Runtime Policy
  保留后端 deny-first 校验但不再作为普通用户独立页面。
- 审计旧 Platform Runtime 文档、代码和重叠 OpenSpec，先标记 `Superseded` 或拟归档处置，待本
  change 获得 owner acceptance 后再执行删除、移动和业务代码改造。
- 建立分阶段改造、契约测试、最短真实链和 owner acceptance 清单；任务勾选不得替代证据。

本变更不实现 Runtime graph、Middleware、Sandbox、MCP、Run Explorer、Langfuse/OTLP、生产灰度、性能 SLO
或生产回滚；这些能力保持各自 owner 和既有 deferred 状态。本轮 proposal/design 阶段也不修改
Platform Web/API 业务代码，不物理删除或归档旧文档。

## Capabilities

### New Capabilities

- `platform-runtime-control-plane`：定义 Agent key、模型配置边界、平台治理对象、运行目标解析、可信
  Context、delegation、Thread/Run 事实源、最小治理记录以及所有 Run 入口必须共享的应用服务边界。

### Modified Capabilities

- `chat-interaction-runtime`：正式 Chat 改为由官方 LangGraph SDK 消费受控的标准 Agent Server
  网关契约，并移除旧 `platform_runtime` payload、重复 live state 和隐式 legacy fallback。
- `platform-runtime-graphharbor-compatibility`：将现有 info/graph/thread smoke 契约扩展为平台实际
  使用的 Threads、Runs、Protocol v2 command/event、标准 `context`、SSE 和拒绝语义兼容边界。

## Impact

- Platform Web：`src/modules/chat/`、`src/services/runtime/` 及相关 route、store、测试和 Chat 文档。
- Platform API：现有 `app/modules/assistants/` 迁移为 Agent 目录、`runtime_catalog/`、`runtime_policies/`、
  `runtime_gateway/`、`app/adapters/langgraph/`、数据库 migration、权限、审计和测试。
- GraphHarbor：只涉及通用 LangGraph Compatibility Profile 及协议字段透传，不接受平台专用模型。
- Runtime Service：保持 `RuntimeContext`、Auth 和 graph public contract；将正式注册的 `workflow_demo`
  组合为 Runtime 真实模型 `create_agent` 外层 Workflow/HITL，不新增 Platform 专用执行协议。
- 文档：新建 P1 专项导航；`22`、`27` 及旧 Chat 决策/计划进入待归档矩阵；`28` 只保留 P1 阶段入口。
- 兼容与回退：外部 `/api/langgraph` 路径和 SDK 调用模型优先保持稳定；旧 payload 和旧页面版本的
  迁移窗口、数据兼容 fixture 与删除门槛必须在 design/tasks 中明确，不能永久双轨。
