## MODIFIED Requirements

### Requirement: 正式聊天运行时使用 Protocol v2 网关
正式聊天页面 MUST 通过锁定版本的官方 LangGraph SDK，以 Platform API 的
`/api/langgraph` 为 `apiUrl`，使用标准 Thread/State/History、Protocol v2 command/event 和
Run cancel 契约。页面 MUST NOT 直连 upstream、识别 GraphHarbor、手工解析 raw SSE，或在同一
聊天会话中回退调用 legacy `/runs/*` 路由。发布回滚只能切换已验收的版本，不得在单次会话内暗中切换协议。

#### Scenario: 创建运行并订阅事件
- **WHEN** 已授权用户在已选 project 的 thread 通过 SDK 提交运行
- **THEN** SDK 经 Gateway 提交标准 `run.start` 并消费 event stream，页面收到该运行的 messages、values、tools、lifecycle 和 input 投影

#### Scenario: 协议请求被拒绝
- **WHEN** command envelope 无效、actor 未授权，或 thread 不属于请求 project
- **THEN** 网关拒绝请求且不向 upstream 创建或订阅运行，并返回 SDK 可归一化的协议或权限错误

#### Scenario: 同一 Thread 存在 active Run
- **WHEN** 正式 Chat 在同一 Thread 已有 active Run 时再次提交新的 Run
- **THEN** Gateway 返回稳定的 `409 ActiveRunConflict`，其中等待人工输入/HITL 的 Run 仍算 active，浏览器不通过 enqueue 参数绕过该限制

#### Scenario: upstream 为 GraphHarbor
- **WHEN** Platform Runtime upstream 配置为 GraphHarbor
- **THEN** 页面使用同一 SDK、路径和状态模型完成运行，不出现 GraphHarbor 专用代码分支

### Requirement: 可信运行身份由服务端认证生成
正式聊天的用户、租户、角色、权限和项目上下文 MUST 由 Platform API 根据当前 session/actor
校验，并通过按请求签发的 delegation credential 交给 GraphHarbor Auth。客户端 `input`、
`context`、`config`、`metadata` 和普通 forwarded headers MUST NOT 设置或覆盖这些字段。

#### Scenario: v2 运行获得可信项目上下文
- **WHEN** 已授权用户通过 Platform Gateway 为已选项目提交合法 `run.start`
- **THEN** Gateway 在决议目标和 Context 后签发 credential，GraphHarbor Auth 生成与 actor/project 一致的可信运行身份

#### Scenario: 运行凭证无效
- **WHEN** delegation credential 缺失、过期、签名或 audience 无效，或其 project/target/hash 与请求不一致
- **THEN** GraphHarbor 或 Runtime 在创建运行前拒绝请求，且不从 command payload 推断或补齐身份与项目

#### Scenario: 客户端夹带身份字段
- **WHEN** command 的 `input`、`context`、`config` 或 `metadata` 包含 `project_id`、`user_id`、role 或 permissions
- **THEN** Gateway 拒绝或剥离这些字段，最终可信身份只来自认证结果

### Requirement: Protocol v2 迁移保持数据与治理兼容
Protocol v2 迁移 MUST 保持既有有效 thread 数据、权限、项目隔离和审计语义。旧 snapshot 的读取
兼容逻辑 MUST 只存在于有 characterization fixture 的 normalization 边界；正式 Chat 切换完成后
MUST 删除 legacy Run fallback 和旧 Runtime payload 生成路径。生产灰度与运行中自动回滚不属于本
change 的完成条件。

#### Scenario: 现有有效 Thread 在升级后重新打开
- **WHEN** 用户在专项切换后打开格式有效且仍归属当前 project 的既有 thread
- **THEN** 页面继续展示其 messages、history、tool result 和可用分支，不要求复制 Thread 到 Platform 数据库

#### Scenario: 旧 snapshot 需要归一化
- **WHEN** characterization fixture 证明某个旧字段仍存在于受支持数据
- **THEN** 兼容逻辑仅转换读取视图，不写回或污染新的 live stream/Context 契约

#### Scenario: legacy fallback 没有真实覆盖证据
- **WHEN** 某项 legacy route、payload 或 snapshot fallback 没有 fixture 或现有数据证明仍被需要
- **THEN** 实施删除该 fallback，而不是迁移进新的正式 Chat 路径

### Requirement: SSE 断开与显式 Stop 的取消语义必须分离
正式聊天 MUST 将 SSE 连接生命周期与 Run 生命周期分离。浏览器关闭、网络断开或主动重连只取消当前
事件订阅，不得隐式取消服务端 Run；只有用户显式触发 Stop/Cancel，或服务端策略明确终止，才调用
Run cancel。等待人工输入/HITL 的 Run 在收到合法恢复或显式 Stop 前持续占用该 Thread 的 active Run 槽位。

#### Scenario: SSE 断开不取消 Run
- **WHEN** 浏览器关闭事件流、网络断开或以 `since` 重连，且用户没有显式触发 Stop
- **THEN** Gateway 释放/重建事件订阅但保留服务端 Run 和 HITL 状态；同一 Thread 仍拒绝新 Run，直到原 Run 终态或被显式取消

#### Scenario: 用户显式 Stop
- **WHEN** 用户点击 Stop/Cancel 并提交对应 `run_id`
- **THEN** Gateway 使用 cancel scope 调用 GraphHarbor 取消该 Run，事件流最终反映取消结果；取消失败时页面显示可重试错误，但不得创建替代 Run

## ADDED Requirements

### Requirement: 每次运行配置使用标准 context
正式聊天的模型和生成参数候选值 MAY 通过 Platform Gateway 的受控扩展进入 `run.start.params.config`；
该扩展只承载不可信候选值，MUST 在 Gateway 被消费和剥离。Agent Server 边界 MUST 使用标准 Runs API
顶层 `context`，其中的 `tools` 只能由 Agent、Policy 和 Runtime 服务端决议。Platform Gateway MUST
在单一治理用例中校验、决议、快照并注入 Context；Runtime resolver 继续执行最终 contract 验证。在
官方 Protocol v2 尚未承载 `context` 时，Web 到 Gateway MAY 使用一个经 owner 批准且有删除边界的
Platform 扩展传递不可信偏好，但 Gateway MUST 消费并剥离它。正式聊天 MUST NOT 把 `system_prompt`、
`enable_tools`、身份或项目字段传入 Agent Server，也 MUST NOT 将运行 Context 写入持久 graph state。

#### Scenario: v2 运行保留业务 Context
- **WHEN** 用户以已授权模型和生成参数启动正式聊天运行
- **THEN** Platform 根据 Agent 与 Project policy 生成标准 Context，GraphHarbor 完整转发，Runtime 以同一快照语义执行；Tools 仍由 Agent/服务端决定

#### Scenario: 运行 Context 越权或无效
- **WHEN** 请求包含未允许的模型、参数、`tools` 字段、未知字段或身份字段
- **THEN** 系统在签发 delegation、创建模型或执行工具前返回归一化错误，不使用默认值掩盖越权配置

#### Scenario: Protocol v2 版本不能承载 context
- **WHEN** 锁定的 v2-native SDK 不能在 `run.start` 中承载标准 `context`
- **THEN** Gateway 按已批准的单一路径决议 Context 并通过标准 Runs API 创建 upstream Run；若没有获批适配路径则阻止专项切换

## REMOVED Requirements

### Requirement: 静态 breakpoint 位于独立 debug 工作台
**Reason**: Platform 已决定删除 `ChatDebugPage`，正式控制面不再提供第二套 debug 协议或 legacy
运行入口；保留它会继续扩大 Gateway allowlist 和双轨状态机。

**Migration**: static breakpoint 调试转移到 Runtime Web 或独立测试工具。正式 Chat 只使用 Protocol v2
和动态 `interrupt()`；需要调试的工具必须使用独立 session/thread，不得成为正式 Chat fallback。

### Requirement: 每次运行配置使用标准 config
**Reason**: 该 requirement 要求 Runtime 直接消费私有 `config.configurable.platform_runtime`，
与当前 `RuntimeContext` 和标准 Run `context` 契约冲突。

**Migration**: Platform Gateway 在唯一治理入口决议并注入标准顶层 `context`；若 Web 到 Gateway
暂时使用一个 Protocol v2 扩展，它必须只承载不可信偏好并在 Gateway 被剥离。GraphHarbor
Compatibility Profile 验证标准 Runs API Context 到 Worker/Runtime 的完整传递。
