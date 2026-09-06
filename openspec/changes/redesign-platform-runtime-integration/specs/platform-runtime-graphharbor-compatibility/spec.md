## MODIFIED Requirements

### Requirement: Platform Runtime Gateway SHALL reach GraphHarbor through the compatible Agent Server protocol
当 Platform API 的 Runtime upstream 指向 GraphHarbor 时，Platform Runtime Gateway SHALL 通过
真实 HTTP/SSE 和标准 Agent Server endpoint 完成产品所需的 Thread create/search/get、State、
History、Run create/get/list/cancel、Protocol v2 command/event stream 与 Graph discovery。Gateway
SHALL 完成 Platform access token、project permission、运行目标、Runtime Policy/Context snapshot
和 delegation 校验；上层调用方 MUST NOT 理解 GraphHarbor 专用 API。协议固定字段 `assistant_id` 的值
由 Platform 传入稳定 `agent_key`，不要求 GraphHarbor 保存 Platform Agent 产品对象。

#### Scenario: Platform requests Runtime info through GraphHarbor
- **WHEN** 已认证且具有项目 Runtime read 权限的 Platform API 客户端请求 `/api/langgraph/info`
- **THEN** Platform API 返回 GraphHarbor 的兼容 info 响应，且请求经过按操作签发的 GraphHarbor delegation authentication

#### Scenario: Platform searches graphs through GraphHarbor
- **WHEN** 已认证且具有项目 Runtime read 权限的 Platform API 客户端请求 `/api/langgraph/graphs/search`
- **THEN** Platform API 返回 GraphHarbor 的 graph search 响应，并只暴露当前项目 policy 允许的 graph

#### Scenario: Platform creates a scoped Thread through GraphHarbor
- **WHEN** 已认证且具有项目 Runtime write 权限的 Platform API 客户端请求 `/api/langgraph/threads`
- **THEN** Platform API 返回 GraphHarbor 创建的 Thread，GraphHarbor 按可信 tenant/project scope 持久化归属

#### Scenario: Platform runs and resumes through GraphHarbor
- **WHEN** SDK 为已归属 thread 提交 `run.start`、订阅 events、响应 interrupt 或取消 Run
- **THEN** GraphHarbor 保持标准请求、响应、SSE、Run ID 和错误语义，且 API/Worker 使用同一持久执行事实

#### Scenario: Missing Platform or upstream environment is explicit
- **WHEN** 集成测试缺少 Platform API 地址、access token、project ID 或 GraphHarbor upstream 配置
- **THEN** 测试明确报告缺失输入并跳过；不得启动旧 `langgraph dev`，也不得将 skip 计为通过

### Requirement: Platform-to-GraphHarbor integration SHALL preserve denial semantics
Platform Gateway SHALL preserve fail-closed behavior at both boundaries：Platform API 对未认证、无项目权限、
无效 Agent target/Policy/Context 的请求在调用 upstream 前拒绝；GraphHarbor 对缺失或无效 delegation
拒绝并不得调度到 Worker。`context_hash` 是 Platform governance 与 Runtime execution contract 的绑定，
Runtime 必须在模型/工具执行前 fail closed。测试 MUST NOT 用 mock upstream 代替真实 GraphHarbor。

#### Scenario: Platform rejects an unauthenticated gateway request
- **WHEN** 客户端不提供有效 Platform access token 请求 Runtime Gateway
- **THEN** Platform API 返回稳定的 401/403，且不会向 GraphHarbor 发出匿名执行请求

#### Scenario: GraphHarbor rejects a request without valid delegation
- **WHEN** 直接请求 GraphHarbor 时不提供有效 Runtime delegation credential
- **THEN** GraphHarbor 返回认证失败，且 Platform Gateway 集成测试不能通过该请求冒充已认证链路

#### Scenario: Platform rejects a mismatched target before upstream
- **WHEN** Platform 请求中的 project、graph、thread 或 resolved Context 与即将签发的 delegation 不一致
- **THEN** Platform 在调用 GraphHarbor 前拒绝请求，不创建 Platform durable Run，不向 GraphHarbor 发出创建/调度请求

#### Scenario: Runtime rejects a mismatched context hash before model execution
- **WHEN** 标准 Runs 请求已经被 GraphHarbor 接收，但 delegation 的 `context_hash` 与 Runtime 收到的
  canonical Context 不一致
- **THEN** Runtime 在模型、Provider 或 Tool 执行前 fail closed；该通用 Agent Server 行为不承诺已持久化的
  Run 记录一定不存在，若产品要求零 Run 记录，必须由 Platform 在 upstream 调用前完成校验或另立 GraphHarbor
  通用协议变更。

#### Scenario: Graph introspection does not bypass execution authentication
- **WHEN** GraphHarbor 为加载 Graph 执行 `get_agent({})` 或无副作用 introspection
- **THEN** 该操作不读取用户 Secret、不创建 Run；真实用户 Run 仍必须通过 delegation 和执行 Auth

## ADDED Requirements

### Requirement: GraphHarbor SHALL preserve the frozen standard Run fields
GraphHarbor SHALL 分别遵守冻结版本的两套标准表面：Protocol v2 `run.start` 完整处理该版本定义的
`assistant_id`、`input`、`config` 和 `metadata`；标准 Runs API 完整处理 Platform 实际使用的
`assistant_id`/执行目标、`input`、`context`、`config`、`metadata`、`durability`、
`stream_resumable`、`multitask_strategy` 和 stream 选项。实现 MUST NOT 静默丢弃已接受字段，也
MUST NOT 用 Platform 专用字段替代标准字段。在 Platform 集成中，`assistant_id`/`graph_id` 使用
`agent_key`；`context_hash` 属于 delegation 和 Platform governance binding，不得作为未声明字段
塞入 Runtime `context`。

#### Scenario: Context reaches Runtime
- **WHEN** Gateway 通过标准 Runs API 和合法 credential 提交包含非默认 `temperature` 和服务端决议的 `tools: []` 的 Run，且 delegation claim 与 governance record 绑定同一 `context_hash`
- **THEN** GraphHarbor Worker 调用 Runtime graph 时保留同一标准 Context，Runtime 证据可观察到对应决议结果

#### Scenario: Durable and stream options reach the worker
- **WHEN** Run 请求使用 Compatibility Profile 支持的 durability、resumable、multitask 和 stream 选项
- **THEN** GraphHarbor 持久记录并按这些值执行，API restart 或 Worker restart 不把它们重置为隐式默认值

#### Scenario: Unsupported field
- **WHEN** 客户端提交冻结 Profile 未支持的标准可选字段
- **THEN** GraphHarbor 返回明确的兼容性错误或按文档化默认处理，不得接受后静默丢弃

#### Scenario: Protocol v2 uses its frozen field set
- **WHEN** SDK 通过冻结版本 Protocol v2 提交 `run.start`
- **THEN** GraphHarbor 只按该协议版本声明的字段执行，不把 Runs API 专属字段伪装成既有 v2 标准

### Requirement: Compatibility Profile 作为平台切换门禁
Platform 与 GraphHarbor SHALL 锁定 SDK、Gateway 和 GraphHarbor 版本组合，并为产品 endpoint/field
矩阵保存自动化合同测试。只有 Profile 的 success、denial、SSE cancellation/reconnect 和 API/Worker
durability 证据均通过，L2 才能声明 shortest-chain complete。

#### Scenario: 版本组合通过 Profile
- **WHEN** CI 或本地验收使用锁定版本运行 Compatibility Profile
- **THEN** 每个必需 endpoint 和字段都有真实 GraphHarbor 证据，结果记录具体版本、命令、输入和输出摘要

#### Scenario: 升级产生协议回归
- **WHEN** SDK、Gateway 或 GraphHarbor 升级导致必需 endpoint、字段或 SSE 语义变化
- **THEN** Profile 失败并阻止发布，不通过 Platform 专用 fallback 掩盖回归

### Historical Requirement (removed): Worker 到模型代理必须使用受信执行引用和 workload identity

> 该 requirement 属于已废弃的生产模型代理方案。GraphHarbor 继续保持通用 Agent Server，不实现
> Platform 模型目录、Secret Store、execution reference 或 workload identity。
GraphHarbor Worker 调用统一模型代理时 MUST 使用 Platform 已签发且与 Run governance 绑定的
`execution_model_id`，以及 audience 固定为 `model-proxy` 的 workload OIDC identity（必要时叠加 mTLS）。
Worker/Runtime MUST NOT 直接访问 Secret Store、提交 Provider API key/raw URL 或根据当前默认模型重新解析
旧 Run。模型代理 MUST 在读取 Secret 或调用 Provider 前校验 identity、scope、target、revision 和
`execution_model_id` 绑定。

#### Scenario: Worker 以执行引用调用代理
- **WHEN** GraphHarbor Worker 执行一个已授权且已持久化 governance snapshot 的 Run
- **THEN** 代理请求携带同一 `execution_model_id`、`run_id`、`operation_id` 和受信 workload identity，代理解析到唯一 provider/revision/credential version

#### Scenario: Worker 直接访问 Secret Store
- **WHEN** Worker 绕过代理请求 Secret Store 或提交 raw key/URL
- **THEN** Secret Store/代理拒绝请求，不进入 Provider，GraphHarbor 不把 Secret 写入 Thread、Run、Event 或日志

#### Scenario: 执行引用或身份不匹配
- **WHEN** `execution_model_id` 未知、revision 已禁用、credential version 不匹配、identity audience 错误或 Context hash 与 delegation 不一致
- **THEN** 请求在 Provider 调用前 fail closed，且不回退 active revision、环境变量或其他 Provider

#### Scenario: 旧 Run 重启后保持固定版本
- **WHEN** 模型目录激活新 revision，随后旧 Run 经 Worker 重启、重试或 SSE 重连继续执行
- **THEN** Worker 继续使用 governance snapshot 中原有 `execution_model_id`，不重新读取当前默认模型

## REMOVED Requirements

### Requirement: Worker 到模型代理必须使用受信执行引用和 workload identity
**Reason**: GraphHarbor 保持通用 Agent Server；当前不实现模型代理、Secret Store、execution reference 或 workload identity。

**Migration**: Runtime 使用当前七字段模型配置和本地兼容 profile；生产治理需求另立 change。
