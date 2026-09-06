# Platform Runtime Control Plane

> 2026-09-04 owner decision: `execution_model_id`/revision、统一模型代理、Secret Store 编排、生产 RS256/JWKS
> 和 workload identity 均已 `Superseded/Rejected`，不属于当前现行契约。当前模型管理只使用七字段、服务端
> 加密和 write-only API key；下方若仍出现旧 requirement，必须按历史记录理解，不得作为实现门禁。

## Purpose

定义 Platform 控制面、模型治理、Run launch、Context、delegation、项目隔离和 Gateway allowlist 的
公开契约。该能力由 Platform API 负责治理，GraphHarbor/Runtime 负责通用执行。

## Requirements

### Requirement: 平台网关保持标准 Agent Server 客户端契约
正式平台 SHALL 以 `platform-web -> platform-api /api/langgraph -> compatible Agent Server`
作为唯一运行链。`platform-web` MUST 使用锁定版本的官方 LangGraph SDK 访问标准 Threads、Runs、
State、History、Protocol v2 command/event 和 cancel 能力；它 MUST NOT 识别 GraphHarbor 专用路径、
响应或部署拓扑。

#### Scenario: SDK 通过平台网关访问 GraphHarbor
- **WHEN** 已登录用户在已授权 project 中创建 thread、提交 run 并消费 stream
- **THEN** SDK 使用标准 Agent Server 请求和响应完成链路，Platform Gateway 完成治理，前端无需 GraphHarbor 专用分支

#### Scenario: 替换为另一兼容 Agent Server
- **WHEN** upstream 被替换为通过同一 Compatibility Profile 的 Agent Server
- **THEN** 平台前端调用契约和产品页面状态模型不需要修改

### Requirement: Platform Agent 使用稳定 agent_key
Platform Agent SHALL 是 control plane 产品对象，并使用稳定的 `agent_key` 作为产品标识和执行目标。
在本项目中 `agent_key`、Agent Server 的 `assistant_id` 和 Runtime 的 `graph_id` 使用同一个值。
Platform MUST NOT 通过镜像创建、更新或删除 GraphHarbor Assistant 来维持第二份产品主数据；Gateway
SHALL 在 Run 创建前校验已授权的 Agent 并解析其稳定执行键。Thread 创建只绑定可信 tenant/project；
第一次 Run 绑定 `agent_key`，同一 Thread 后续不得切换 Agent。

#### Scenario: 使用产品 Agent 启动 Run
- **WHEN** 用户以 `agent_key` 提交运行
- **THEN** Gateway 校验 Agent 的 project 归属和状态，并以同值 `assistant_id/graph_id` 将执行目标交给 Agent Server

#### Scenario: 映射失效
- **WHEN** Agent 不存在、未启用、跨 project 或其 `agent_key` 不在当前可用 catalog/policy 中
- **THEN** Gateway 在调用 upstream 前 fail closed，且不会临时创建或猜测 GraphHarbor Assistant

#### Scenario: Thread 首次绑定 Agent
- **WHEN** 已授权用户在当前 project 的未绑定 Thread 上以合法 `agent_key` 创建第一个 Run
- **THEN** Gateway 以并发安全的治理操作绑定该 Thread 和 `agent_key`，并使用同一个执行键调用 Agent Server

#### Scenario: Thread 不允许切换 Agent
- **WHEN** 已绑定 Agent A 的 Thread 收到 Agent B 的 Run 请求
- **THEN** Gateway 返回 `409 AgentThreadMismatch`，且不向 GraphHarbor 创建或调度 Run

### Requirement: Run 创建使用统一治理用例和幂等恢复
任何能创建 Run 的 Platform 入口 MUST 调用同一个 application use case，完成 Agent/Thread 校验、
Policy/Context 决议、不可变 Run intent、delegation、Idempotency-Key 和 audit 关联。上游超时 MUST
通过 reconciliation 查询实际结果，不能盲目再次创建；相同 key 和 request digest MUST 返回同一 Run，
相同 key 但 digest 不同 MUST 返回稳定的 `409 IdempotencyConflict`。

#### Scenario: 重复提交同一意图
- **WHEN** 同一个 actor 在同一 project 以相同 idempotency key 和 request digest 重复提交 Run
- **THEN** Gateway 返回已关联的同一 GraphHarbor `run_id`，且不会创建第二个 Run

#### Scenario: 幂等 key 被复用
- **WHEN** 相同 idempotency key 被用于不同 request digest
- **THEN** Gateway 返回 `409 IdempotencyConflict`，且不调用 upstream 创建 Run

#### Scenario: 上游创建请求超时
- **WHEN** GraphHarbor 的 Run create 响应超时而实际结果尚未可知
- **THEN** Platform 保留 `run_start_unknown` intent，通过 reconciliation 收敛结果，不直接盲目重试创建

### Requirement: 当前模型配置采用七字段最小闭环
Platform SHALL 管理 `provider`、`display_name`、`base_url`、`protocol`、`model`、`api_key`、`enabled`。
服务端 SHALL 校验必填字段、URL 和协议；API key 只写不读并使用部署级 master key 加密；GET/list 只返回
`credential_configured`。当前不引入 execution reference、revision registry、独立模型代理或 Secret Store 编排。

#### Scenario: 模型配置安全返回
- **WHEN** 管理员创建或编辑模型后查询列表/详情
- **THEN** API key 不出现在响应、Thread、Run、Context、GraphHarbor、日志或审计详情中

#### Scenario: 禁用模型拒绝运行
- **WHEN** 新 Run 选择 `enabled=false` 的模型
- **THEN** Gateway 在 upstream/Provider 调用前返回结构化错误且无副作用

### Requirement: 运行 Context 由控制面决议并形成不可变快照
Platform SHALL 只生成当前 Runtime contract 允许的运行选项：`model_id`、`temperature`、`max_tokens`、
`top_p` 和 `tools`。Gateway MUST 将客户端请求视为不可信偏好，与 Agent 默认值、Project Runtime Policy
和已部署能力共同决议，并为每次 Run 保存不可变 Context snapshot 与 `context_hash`。浏览器 MUST NOT
提交或编辑 `tools`；`system_prompt`、`enable_tools`、身份和 project 字段 MUST NOT 进入正式运行 Context。

#### Scenario: 合法运行选项被决议
- **WHEN** 用户请求 policy 允许的模型和生成参数，且 Agent/服务端决定可用工具
- **THEN** upstream 收到标准顶层 `context`，治理记录保存同一规范化快照和 hash，Runtime 可验证并执行该 Context

#### Scenario: 服务端显式禁用所有工具
- **WHEN** Agent 或服务端 Policy 决议为 `tools: []`
- **THEN** 快照和 upstream Context 均保留空列表语义，不会因删除字段而恢复默认工具

#### Scenario: 未提供工具覆盖
- **WHEN** Agent 或服务端没有提供工具覆盖
- **THEN** 决议流程按 Agent、Project 和 Runtime 默认规则处理，且该语义与 `tools: []` 可区分

#### Scenario: 非法或越权选项
- **WHEN** 客户端提交未知字段、`tools` 字段、未授权模型或超出 policy 的参数
- **THEN** Gateway 在签发 delegation 和创建 Run 前返回稳定错误，不用默认值掩盖请求

### Requirement: Delegation credential 按 upstream 操作即时签发
Platform Gateway MUST 在 actor、project、目标对象和最终 Context 已解析后，为当前 upstream 操作签发
短期 delegation credential。凭证 MUST 绑定 audience、actor、tenant/project、权限、`agent_key`、`graph_id`、
`thread_id`（存在时）和 `context_hash`；读、Run create、cancel 和 interrupt/respond 使用最小 scope。
当前本地 profile 复用现有 delegation 实现；RS256/JWKS、workload identity 和独立模型代理不属于本 change。

#### Scenario: 合法 Run delegation
- **WHEN** 授权用户为已归属 thread 和 graph 创建 Run
- **THEN** GraphHarbor Auth 验证 credential 并生成可信 user/permission context，Runtime 收到的身份与 Context hash 相互匹配

#### Scenario: 请求目标在签发后被替换
- **WHEN** upstream 请求中的 project、graph、thread 或 Context 与 credential claims 不一致
- **THEN** GraphHarbor 或 Runtime 在执行 graph/tool 前拒绝请求

#### Scenario: 只读请求
- **WHEN** 用户读取已归属 thread、state 或 history
- **THEN** Gateway 签发范围只覆盖该读取操作和 project，不复用具有 Run 创建权限的通用 token

#### Scenario: delegation 签名或 scope 无效
- **WHEN** credential 签名、issuer、audience、时间、scope、目标或 `context_hash` 无效
- **THEN** GraphHarbor 在持久化或调度前拒绝请求，且不进入 Redis、不调用 Runtime、Provider 或 Tool

### Requirement: 执行事实与平台治理记录分离
GraphHarbor PostgreSQL SHALL 是 Thread、Run、Checkpoint 和可恢复 Event 的执行事实源，Redis SHALL 只承担
队列和短生命周期协调。Platform 数据库 SHALL 保存 Agent、Catalog/Policy、Audit/Operation 和最小 Run
governance record；它 MUST NOT 复制完整 Thread state 或把状态投影作为执行真相。

#### Scenario: 查询 Thread 和 Run 状态
- **WHEN** Platform 页面读取 thread state、history 或 run status
- **THEN** Gateway 从 GraphHarbor 获取执行事实，并只用 Platform 记录完成归属、策略快照和审计关联

#### Scenario: 平台状态投影滞后
- **WHEN** Platform governance record 的状态与 GraphHarbor 当前 Run 状态不同
- **THEN** 用户可见执行状态以 GraphHarbor 为准，平台投影被更新而不是反向覆盖 upstream

### Requirement: 所有 Run 创建入口共享同一治理用例
Platform API 暴露的 Protocol v2、标准 Runs API 或后续自动化入口只要能够创建 Run，MUST 调用同一个
application use case 完成权限、目标解析、Policy/Context、delegation、幂等、governance record 和 audit。
Presentation handler 和 upstream adapter MUST NOT 各自复制这套逻辑。

#### Scenario: 不同入口创建 Run
- **WHEN** 同一 actor 分别通过允许的 Protocol v2 与标准 Runs API 入口创建 Run
- **THEN** 两条路径执行相同治理门禁并生成字段语义一致的 governance record

#### Scenario: 新入口绕过治理用例
- **WHEN** 契约测试发现某个公开入口直接调用 upstream Run create
- **THEN** 测试失败，该入口不得进入正式 allowlist

### Requirement: Project 隔离由可信数据边界执行
Thread/Run 的 tenant/project scope MUST 来自已验证 delegation/Auth，并在 GraphHarbor 的持久查询边界执行；
Thread metadata MAY 保存关联信息，但 MUST NOT 成为唯一授权依据。Platform Gateway MUST 在建立 SSE 前完成
project 归属校验。

#### Scenario: 跨项目读取 Thread
- **WHEN** actor 使用 Project A 的身份读取属于 Project B 的 thread、history、run 或 event stream
- **THEN** Platform Gateway 或 GraphHarbor 返回拒绝，且响应和日志不泄漏 Project B 的执行内容

#### Scenario: 伪造 metadata
- **WHEN** 客户端在 thread/run metadata 中夹带另一个 project ID
- **THEN** 可信 scope 不被覆盖，创建或读取请求被拒绝或按已认证 project 强制归一化

### Requirement: Gateway 暴露面采用产品所需 allowlist
Platform Gateway SHALL 只代理正式产品已经声明、测试并治理的标准 Agent Server endpoint。Agent Server 的
Assistant mutation、Cron、Store、System admin 或其他未使用 surface MUST NOT 因 SDK/Server 支持而默认公开；
Platform 不提供独立 Chat debug 工作台。

#### Scenario: 请求已允许 endpoint
- **WHEN** 已授权 SDK 请求 allowlist 中的 thread、run、state、history、command、event 或 cancel endpoint
- **THEN** Gateway 按该 endpoint 的读写权限、scope 和错误映射规则处理

#### Scenario: 请求未治理 endpoint
- **WHEN** 客户端请求尚未进入产品 allowlist 的 Agent Server endpoint
- **THEN** Platform API 明确拒绝或不注册该路由，不使用透明万能代理绕过治理

### Historical Requirement (removed): 模型代理必须有单一 owner 和清晰的数据面边界
模型代理 SHALL 指定一个数据面 DRI（职责名可暂用 `Runtime Platform Integration Owner`），对代理 API、
Provider allowlist、`execution_model_id` 路由、Secret 读取、timeout/retry、缓存失效、错误码、fail-closed、
服务身份、SLO、runbook、Compatibility Profile 和 Provider smoke 负最终责任。Platform API 负责模型目录、
Policy、revision、执行引用决议、连接验证和审计；GraphHarbor/Runtime 负责 Run 执行和薄代理 client；任何
组件 MUST NOT 因角色兼任而绕过该边界。

#### Scenario: owner 边界可审计
- **WHEN** 进入模型代理实现或发布评审
- **THEN** 变更记录包含实际 DRI、协作团队、代理 endpoint、Provider allowlist、SLO 和故障 runbook，且明确 Platform API 不代理模型流量、Worker 不读取生产 Secret

#### Scenario: 控制面不转发 Provider 流量
- **WHEN** Platform API 创建或执行 Run
- **THEN** Platform API 只决议并签发 `execution_model_id`，模型请求经受信模型代理发送到 Provider，不把 Provider token 流量纳入控制面

### Historical Requirement (removed): Secret Store 使用最小接口和分层权限
模型治理 SHALL 复用现有受信 Secret Store，至少提供 `create_or_rotate`、`resolve`、`get_status` 和
`disable` 能力。`credential_ref` MUST 是随机 opaque ID，Secret MUST 只在模型代理进程内存短暂存在，且
MUST NOT 出现在浏览器响应、数据库、Context、Thread、Run、GraphHarbor、缓存 key、日志、异常或审计详情。
Platform Model Admin 只能写入/轮换和读取脱敏状态；模型代理 workload 只能按已绑定的执行引用读取 credential
version；GraphHarbor/Runtime Worker 只能调用代理，不能直接访问 Secret Store。

#### Scenario: Secret Store 轮换保持版本绑定
- **WHEN** 管理员替换某模型 credential
- **THEN** 系统先验证新 Secret，再创建新的 `model_revision` 和 `execution_model_id`；旧执行引用不会悄悄指向新 credential version

#### Scenario: Secret Store 不可用
- **WHEN** 模型代理 resolve 超时、credential 无效或 purpose/版本不匹配
- **THEN** Run 在 Provider 调用前 fail closed，不读取环境变量、不切换其他 Provider，并记录脱敏关联

#### Scenario: Worker 直接读取 Secret
- **WHEN** GraphHarbor Worker 或 Runtime 以自身身份请求 Secret Store
- **THEN** Secret Store 返回拒绝，Worker 必须改为携带已签发执行引用调用模型代理

### Historical Requirement (removed): 生产服务身份使用 RS256/JWKS 和 workload identity
Platform SHALL 在最终 Agent、Thread、Policy、Context 和 `context_hash` 决议后签发短期 operation-scoped delegation。
生产 delegation MUST 使用 `RS256`、`JWKS` 和 `kid`，GraphHarbor/模型代理只读公钥并支持双 key overlap；生产
MUST NOT 接受共享 HS256。GraphHarbor/Worker 到模型代理 MUST 使用 audience 固定为 `model-proxy` 的 workload
OIDC identity（必要时叠加 mTLS），不得信任客户端身份 header。

#### Scenario: delegation 绑定模型执行引用
- **WHEN** Platform 为合法 Run 签发 delegation
- **THEN** claims 包含 project、agent/graph、thread（如有）、最小 scope、`policy_revision`、`execution_model_id` 和 `context_hash`，且目标或 hash 被替换时在持久化/调度前拒绝

#### Scenario: 无效服务身份
- **WHEN** Worker 使用错误 audience、未知 `kid`、过期或未授权 workload identity 调用模型代理
- **THEN** 模型代理拒绝请求且不访问 Secret Store 或 Provider

### Historical Requirement (removed): 模型代理路由能力必须先于实现被证明
Platform SHALL 在实施前对现有 Provider proxy 运行隔离 capability probe，证明合法 `execution_model_id` 能
唯一解析到 provider、upstream model 和 credential version，未知/已禁用/版本不匹配引用在 Provider 请求前
拒绝，且同一引用重复调用不会重新解析当前默认模型。若现有 proxy 不支持，只能在代理边界增加最薄 adapter，
不得把 Provider registry、Secret Store client、fallback 或版本决议复制进 Runtime。

#### Scenario: 现有 proxy 不支持执行引用
- **WHEN** capability probe 发现 proxy 只接受固定 `*_PROXY_URL`、`*_PROXY_API_KEY` 和上游模型名
- **THEN** Platform 将其标记为 local compatibility 依赖，并在受信代理边界增加 `execution_model_id -> pinned binding -> Secret Store -> Provider` adapter

#### Scenario: 未知引用被拒绝
- **WHEN** Run 携带未知、未验证或已禁用的 `execution_model_id`
- **THEN** capability probe/代理返回结构化拒绝且上游调用计数为 0，不回退当前 active revision 或 fake model

### Requirement: Local compatibility profile 必须显式选择
Runtime 本地兼容 MUST 通过 `RUNTIME_MODEL_PROFILE=local-compat` 显式启用；缺少 profile 或 profile 值未知时启动校验失败。
真实模型调用仅在显式 `RUNTIME_E2E=1` 且使用 owner 已授权的本地 `.env` 时执行；当前不要求 fake model、Secret Store、
RS256/JWKS 或 Provider 审批 smoke。

#### Scenario: 本地 profile bootstrap
- **WHEN** 开发者运行本地 Runtime 兼容链
- **THEN** 使用 Git ignored env 设置 `local-compat`，运行 `validate_runtime_config.py`、合同/单元测试；只有显式 `RUNTIME_E2E=1` 才调用真实 Provider

#### Scenario: 未知 profile 被拒绝
- **WHEN** Runtime 使用缺失或未知的 profile 启动
- **THEN** 启动校验失败，不静默降级为其他 profile
