# Platform API 与 Runtime Service 分阶段整合设计

> 文档类型：Draft
>
> 生命周期：Superseded（2026-09-03）
>
> 状态：阶段 R/P 的历史边界仍可追溯，但本文 payload、Assistant 与数据模型不得继续作为 P1
> 实现依据。新的讨论入口见
> [`Platform Runtime Integration 专项`](./platform-runtime-integration/README.md)，
> 规范与执行真源见
> [`redesign-platform-runtime-integration`](../../../../openspec/changes/redesign-platform-runtime-integration/)。
> owner 批准退役矩阵后再物理归档本文。
>
> 关联文档：`10-production-agent-platform-roadmap.md`、
> `12-runtime-context-and-local-debug-architecture.md`、
> `14-runtime-contracts-and-resolution-design.md`、
> `22-platform-runtime-contract-design.md`、
> `26-runtime-custom-routes-and-model-config-design.md`

## 1. 背景与结论

当前 `platform-api` 并非完全没有运行时能力，已经存在：

- `runtime_catalog`：Runtime 的 Graph、Model、Tool 目录同步和查询；
- `runtime_policies`：Project 级 Graph、Model、Tool 开关和默认模型；
- `assistants`：Assistant/Graph 映射和 Profile；
- `runtime_gateway`：权限、幂等、Durable Run、Protocol v2 代理和错误整形；
- `runtime_runs`：Durable Run 与 Interrupt 的平台侧索引。

但这些代码仍混有旧的 `platform_runtime`、`enable_tools` 和历史 Assistant 归一化逻辑，不能
作为新实现基础。它们只用于了解现状；模型配置持久化、不可变 Run 配置快照和新
`RuntimeContext` 的端到端链路全部按绿色开发重新设计。

本次采用明确的两阶段策略：

```text
阶段 R：先完成 Runtime Service
  本地配置 + 本地凭据 + 标准 LangGraph Agent Server + 本地调试
  不依赖 Platform API 数据库和 HTTP

阶段 P：再整合 Platform API
  配置持久化 + 权限策略 + Run 快照 + Delegation Token + Runtime Gateway
  不改变 Runtime 的 Graph 组合根和执行职责
```

Runtime 是本次重构的优先边界。Platform 的数据库和控制面改造不得反向污染 Runtime 的
公共 API，也不要求 Runtime 为 Platform 保留兼容旧代码的分支。

## 2. 借鉴 Open SWE 的边界

Open SWE 的 `agent/server.py` 和 `agent/dispatch.py` 提供的是执行面参考，而不是平台配置
中心：

- `get_agent(config)` 在执行期组合模型、Backend、Tools、Middleware 和 Subagents；
- Durable Run 入口集中设置 `durability`、可恢复流和并发策略；
- 模型凭据由 Runtime 进程环境提供；
- Open SWE 没有本项目所需的 Project Model Policy、Assistant 配置数据库或 Delegation Token。

本项目借鉴其简单的执行入口、配置在 Run 开始时解析和 durable 默认值集中注入；配置目录、
权限策略、审计和持久化属于本项目 Platform 控制面新增能力，不能假装是 Open SWE 已经提供的
功能，也不把 Open SWE 的 Dashboard、Team/Profile 或业务调度复制进 Runtime。

## 3. 阶段 R：Runtime 独立完成

### 3.1 Runtime 的输入来源

Runtime Service 只需要以下本地来源：

| 来源 | 内容 | 是否进入请求 |
| --- | --- | --- |
| Service 代码 | `get_agent(config)`、Graph、Prompt、显式 Tool、Middleware | 否，编译或装配时固定 |
| Runtime 环境/Secret Store | Provider API Key、Base URL、模型实际连接参数 | 否，绝不透传给 Platform |
| `AgentDefaults` | 默认 `model_id`、参数上限、可执行模型 allowlist | 通过本地配置加载 |
| 本地调试脚本 | 最小合法 `RuntimeContext` 和开发 Token | 是 |

Runtime 不提供模型配置 CRUD、`/models`、`/model-config`、`/debug/run` 或配置数据库。
正式请求仍使用标准 LangGraph Agent Server 的 Thread/Run/Stream 接口。

### 3.2 本地调试链路

```text
local .env / Secret Store
  -> Runtime AgentDefaults
  -> local signed dev token + RuntimeContext
  -> langgraph dev --config ./langgraph.json
  -> get_agent(config)
  -> Graph / Model / Tool execution
```

本地调试必须使用与生产相同的 `context` 字段和 Token 校验路径，只允许 Token 签发者替换为
本地脚本。不能通过绕过认证的调试路由掩盖生产链路问题。模型不可用时，使用 fake model
完成 Unit/Composition 测试，再单独执行真实 Provider smoke test。

### 3.3 Runtime 阶段 R 的完成标准

- `get_agent(config) -> Pregel` 可独立启动和调用；
- `RuntimeContext`、模型 allowlist 和工具选择 fail-closed；
- Thread、Run、Checkpoint、Interrupt、Resume 和 Stream 在 LangGraph Agent Server 中闭环；
- 不依赖 Platform API、Platform 数据库或 Platform Gateway；
- 本地 fake model 和真实 Provider smoke test 均有最小证据；
- Runtime 的旧 `platform_runtime`、`enable_tools` 解析路径不再成为新代码入口。

## 4. 阶段 P：Platform 控制面最小能力

Platform 的目标不是重新实现 Agent，而是把“谁可以运行什么、使用什么模型、以什么参数运行”
持久化并在 Run 启动时固化。

### 4.1 数据边界

按新契约设计新的逻辑表和字段，不迁移旧 Runtime 数据，不增加 Model Registry、Route Registry
或通用配置中心。

| 数据 | 事实源 | 最小内容 |
| --- | --- | --- |
| Runtime Model Catalog | Platform DB，由管理员或部署清单维护 | `runtime_id`、稳定 `model_id`、展示信息、可用状态 |
| Project Model Policy | Platform DB | enabled、project default、temperature 上限/默认、更新时间 |
| Assistant Runtime Config | Platform DB 的 Assistant Profile | 可选 `model_id`、生成参数、可选工具名；只存非敏感配置 |
| Durable Run | Platform DB | 幂等键、project/thread、Runtime run id、状态、配置快照摘要 |
| Provider 凭据 | Runtime 环境/Secret Store | API Key、Base URL、租户密钥；不进入 Platform DB |

当前 `runtime_catalog`、`runtime_policies`、`assistant_profiles` 和 `runtime_runs` 只作为
现状参考，不复用其代码、旧字段或数据。Model Catalog 不再通过 Runtime Custom Route 自动发现；
管理员配置或部署流水线导入的 `model_id` 必须与 Runtime 的本地 allowlist 对齐。第一版不新增独立 Snapshot 表：将规范化后的安全
`RuntimeContext`、`context_hash` 和 `policy_revision` 作为 `runtime_runs` 的不可变启动快照
字段保存；快照过大或需要独立查询时再拆表。

Platform 不保存完整 Prompt、API Key、完整 Tool 参数或模型响应。Catalog 的
`raw_payload_json` 只能用于同步诊断，不能成为 Run 权限决议的事实源。

### 4.2 配置合并规则

Run 启动时只执行一次以下合并，结果不可变：

```text
Runtime Service defaults
  <- Project Model Policy
  <- Assistant Runtime Config
  <- 本次请求允许的 override
  -> normalized RuntimeContext snapshot
```

约束：

1. `model_id` 必须存在于 Runtime Catalog 且被 Project Policy 允许；
2. Assistant 只能选择其 Project 已允许的模型和工具；
3. 请求 override 只能覆盖明确允许的字段，且不能突破参数上限；
4. 缺省模型按 Assistant -> Project -> Runtime 的顺序回退；没有可用模型直接失败；
5. `context.tools` 保持 14 号文档的三态语义，Platform 不再生成 `enable_tools`；
6. 解析后的 `RuntimeContext`、`model_id`、参数上限和安全摘要绑定到本次 Run，后续配置变更
   不影响进行中的 Run。

`model_id` 是稳定的不透明标识，例如 `openai:gpt-5.5`。Platform 不解析 Provider SDK，也不
保存 Provider 凭据；Runtime 的 `modeling.py` 负责把已授权的 `model_id` 映射为 ChatModel。

### 4.3 快照与 Token 绑定

Platform 在调用 Runtime 前：

1. 规范化配置并计算 canonical JSON 的 `context_hash`；
2. 在 `runtime_runs` 中事务化保存快照、hash、graph_id、assistant_id 和 policy revision；
3. 签发短期 Delegation Token；
4. 将相同的 `context` 和 Token 一起发送给 Runtime。

Token 最小增加以下绑定字段：

```json
{
  "aud": "runtime-service",
  "tenant_id": "tenant-123",
  "project_id": "project-123",
  "thread_id": "thread-123",
  "assistant_id": "research_agent",
  "graph_id": "research_agent",
  "context_hash": "sha256:...",
  "jti": "token-123",
  "exp": 1788080000
}
```

Runtime 校验签名、audience、scope、过期时间、Graph 和 `context_hash`。Runtime 不需要访问
Platform DB，也不需要理解 Project Policy 的全部业务规则；它只需拒绝篡改、未部署模型和本地
不支持的能力。相同 Run 的重试必须复用原快照，不能重新读取当前 Project 默认模型。

## 5. 阶段 P 的最小 API

### 控制面 API

按新契约重新实现以下最小操作；底层数据库连接和通用 IAM 原语可以复用，但不得复用旧 Runtime
归一化、Gateway 分支或兼容函数：

- `GET /projects/{project_id}/runtime/models`：读取 Runtime Model Catalog；
- `PUT /projects/{project_id}/runtime/model-policies/{catalog_id}`：设置启用、默认和参数上限；
- `GET/PATCH /assistants/{assistant_id}/runtime-config`：维护 Assistant 的非敏感运行配置；
- `POST /platform/runtime/catalog/import`：管理员或部署流水线导入已审核的 Model/Graph/Tool
  清单；不调用 Runtime 私有 HTTP 路由。

这些接口只修改 Platform DB，不直接修改 Runtime 进程。Runtime 的模型可用性由部署配置和
`modeling.py` 在 Run 启动时最终确认。

### 执行面 API

继续由 `runtime_gateway` 代理 LangGraph Protocol v2：

- `run.start`：读取并冻结配置、写入 `run.submitted`、注入 Context 和 Token；
- `input.respond`：校验 active interrupt 和幂等键后恢复 Run；
- `cancel`：写取消请求并转发 Runtime；
- `GET/SSE`：查询或投影 Runtime Run、事件和安全摘要。

不新增 `/models`、`/debug/run`、第二套 Run API 或 Platform 到 Runtime 的自定义 RPC。

## 6. 端到端时序

```text
1. 前端读取/修改模型配置 -> Platform API -> Platform DB
2. 前端提交 run.start + Idempotency-Key
3. Platform 校验 actor/project/assistant/thread
4. Platform 读取 Project Policy + Assistant Config + Catalog
5. Platform 计算 RuntimeContext snapshot + context_hash
6. Platform 事务保存 runtime_runs(submitted, snapshot)
7. Platform 签发 Delegation Token，调用 Runtime Agent Server
8. Runtime 校验 Token、hash、Graph、model allowlist、tools
9. Runtime 执行 Graph 并写入 LangGraph checkpoint
10. Platform 写 started/interrupted/terminal，并通过 Gateway 查询或投影事件
```

失败必须在边界收敛：配置或权限失败不创建 Runtime Run；Runtime 拒绝则 Platform 将已创建的
Durable Run 标记为 failed，并保存脱敏的 `upstream_code`；SSE 断开不改变 Run 状态。

## 7. 绿色开发处置规则

新 Runtime 和新 Platform 链路不兼容 `platform_runtime`、`enable_tools`、旧 Assistant 字段或
客户端自带权限字段。实现时遵守：

- 新代码只读取新 `RuntimeContext` 和新 Platform schema；
- 不提供旧字段适配器、双读、双写、兼容路由或旧 graph 导出；
- 旧 Runtime 包、旧 Gateway 分支、旧归一化函数和旧测试不进入新测试路径；
- 旧 Platform 数据不迁移到新 schema；需要数据时由新的管理 API 或部署清单重新创建；
- 旧代码和旧数据可以在获得危险操作确认后直接删除，Git 历史仅作为参考存档。

## 8. 实施顺序与门槛

### R 阶段（先做）

1. 完成 `runtime_service` 新目录、Contracts、Resolver、Modeling、Middleware 和 Agent Server；
2. 用 fake model 完成组合测试和契约样例；
3. 用本地 Token、`.env` 和 `langgraph dev` 完成真实 Thread/Run/Stream smoke test；
4. 固定 Runtime 的错误码、事件和 Context schema。

### P 阶段（后做）

1. 对齐 Catalog、Project Policy、Assistant Runtime Config 的字段和权限；
2. 给 `runtime_runs` 增加不可变 Context snapshot/hash/revision 字段；
3. 重写 Gateway 的配置合并、幂等预留和 Token 注入；
4. 增加 Platform/Runtime 双端独立契约测试和真实 Gateway 集成测试；
5. 再接入前端配置页面和 Run Explorer。

进入 P 阶段的门槛是 R 阶段已经能在不启动 Platform API 的情况下稳定运行。进入真实环境前，
必须证明：同一幂等键只生成一个快照和一个 Run；配置变更不影响进行中的 Run；Token/context
篡改被拒绝；Runtime 不可用时 Platform 状态可恢复和可查询。

## 9. 明确不建设

- Runtime Custom Route、模型自动发现、模型配置中心或 Runtime 数据库；
- Platform Provider 凭据托管和 Provider SDK 适配；
- Agent/Graph/Prompt/Tool 版本治理、灰度和自动回滚；
- 独立 Event Bus、通用 RPC SDK、Model Registry、Route Registry；
- 为了兼容旧代码而在 Runtime 增加万能 Builder、Factory、Registry 或 Adapter。
