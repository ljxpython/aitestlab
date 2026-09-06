# Chat Interaction Runtime

## Purpose

定义正式聊天的 LangGraph Protocol v2 网关、可信运行上下文、SDK 状态所有权和生产交互边界。

## Requirements

### Requirement: 正式聊天运行时使用 Protocol v2 网关

正式聊天页面 MUST 通过 `platform-api` 的 `POST /api/langgraph/threads/{thread_id}/commands` 提交 Protocol v2 command，并通过 `POST /api/langgraph/threads/{thread_id}/stream/events` 建立事件订阅。页面 MUST NOT 直连 upstream、手工解析 raw SSE 或在同一聊天会话中回退调用 legacy `/runs/*` 路由。

#### Scenario: 创建运行并订阅事件
- **WHEN** 已授权用户在已选 project 的 thread 提交 `run.start`
- **THEN** 网关返回保留 command id 的 protocol success/error envelope，页面经 v2 event stream 接收该运行的消息、values、tools、lifecycle 和 input 事件

#### Scenario: 同一 Thread 存在 active Run
- **WHEN** 正式 Chat 在同一 Thread 已有 active Run 时再次提交新的 Run
- **THEN** Gateway 返回稳定的 `409 ActiveRunConflict`，其中等待人工输入/HITL 的 Run 仍算 active，浏览器不通过 enqueue 参数绕过该限制

#### Scenario: 协议请求被拒绝
- **WHEN** command envelope 无效、actor 未授权，或 thread 不属于请求 project
- **THEN** 网关拒绝请求且不向 upstream 创建或订阅运行，并返回可归一化的协议或权限错误

### Requirement: Protocol v2 事件流保持可取消和可续接

`platform-api` MUST 将 event stream 的 channel/namespace 过滤、客户端断开、`since` replay 与 event `seq` 语义受控传递给 upstream。网关 MUST NOT 伪造、重排或跨 project 泄漏事件。

#### Scenario: 客户端重连
- **WHEN** 客户端以最后成功接收的 event `seq` 作为 `since` 重新订阅同一可读取 thread
- **THEN** 网关先交付序号更高的缓冲事件，再交付实时事件，且页面不会重复处理已确认的事件

#### Scenario: 订阅被取消
- **WHEN** 浏览器取消或关闭 event stream
- **THEN** 网关只取消对应 upstream subscription，不隐式取消服务端 Run；同一 thread 的其他合法订阅和运行不受影响

### Requirement: 正式聊天使用动态 HITL interrupt

正式聊天页面 MUST 使用 graph 内 `interrupt()` 产生的动态 HITL interrupt，以及 Protocol v2 `input.respond` 或 SDK 对应 `respond` 能力恢复运行。正式聊天 MUST NOT 发送 `interruptBefore`、`interruptAfter`、`streamSubgraphs` 或其他 static breakpoint 字段。

#### Scenario: 用户审批工具动作
- **WHEN** 运行通过 Protocol v2 `input` 事件暴露一个或多个未解决 HITL interrupt
- **THEN** 页面基于 `stream.interrupts` 展示决策，并以标准恢复 command 响应，不丢弃其他待决 interrupt

#### Scenario: 正式聊天不携带静态断点
- **WHEN** 用户在正式聊天页面提交或恢复运行
- **THEN** 请求只包含 Protocol v2 定义的 command 参数，且不会因 static breakpoint 不可用而切换至 legacy run 路由

### Requirement: 可信运行身份由服务端认证生成

正式聊天的用户、租户、角色、权限和项目上下文 MUST 由 `runtime-service` 的 Agent Server `Auth` 根据 `platform-api` 签发的短期 delegation credential 生成。当前 change 只要求绑定 audience、project、agent/graph、thread（如有）、最小 scope 和 `context_hash`；生产 RS256/JWKS 与 workload identity 另立 change。客户端 `input`、`config`、`metadata` 和普通 forwarded headers MUST NOT 设置或覆盖这些字段。

#### Scenario: v2 运行获得可信项目上下文
- **WHEN** 已授权用户通过 `platform-api` 为已选项目提交合法 `run.start`
- **THEN** `runtime-service` 验证 delegation credential，并从认证结果生成与 actor 和 project 一致的可信运行上下文

#### Scenario: 运行凭证无效
- **WHEN** delegation credential 缺失、过期、签名或 audience 无效，或其 project 与目标 thread 不一致
- **THEN** `runtime-service` 在创建运行前拒绝请求，且不从 command payload 推断或补齐身份与项目

#### Scenario: 客户端夹带身份字段
- **WHEN** command 的 `input`、`config` 或 `metadata` 包含 `project_id`、`user_id`、role 或 permissions
- **THEN** 网关或 runtime contract 拒绝/剥离这些字段，且最终可信上下文只来自认证结果

#### Scenario: delegation 目标或 hash 不匹配
- **WHEN** delegation 的 project、graph、thread 或 `context_hash` 与请求不一致
- **THEN** GraphHarbor 或 Runtime 在持久化/调度前拒绝请求，不调用 Provider/Tool，也不从 payload 猜测身份

### Requirement: 每次运行配置使用标准 context

正式聊天的模型和生成参数候选值 MAY 通过 Platform Gateway 的受控扩展进入 `run.start.params.config`；
该扩展只承载不可信候选值，MUST 在 Gateway 被消费和剥离。Agent Server 边界 MUST 使用标准 Runs API
顶层 `context`，其中的 `tools` 只能由 Agent、Policy 和 Runtime 服务端决议。Platform Gateway MUST
在单一治理用例中校验、决议、快照并注入 Context；Runtime resolver 继续执行最终 contract 验证。正式
聊天 MUST NOT 把 `system_prompt`、`enable_tools`、身份或项目字段传入 Agent Server，也 MUST NOT 将运行
Context 写入持久 graph state。

#### Scenario: v2 运行保留业务 Context
- **WHEN** 用户以已授权模型和生成参数启动正式聊天运行
- **THEN** Platform 根据 Agent 与 Project policy 生成标准 Context，GraphHarbor 完整转发，Runtime 以同一快照语义执行；Tools 仍由 Agent/服务端决定

#### Scenario: 运行 Context 越权或无效
- **WHEN** 请求包含未允许的模型、参数、`tools` 字段、未知字段或身份字段
- **THEN** 系统在签发 delegation、创建模型或执行工具前返回归一化错误，不使用默认值掩盖越权配置

#### Scenario: Protocol v2 版本不能承载 context
- **WHEN** 锁定的 v2-native SDK 不能在 `run.start` 中承载标准 `context`
- **THEN** Gateway 按已批准的单一路径决议 Context 并通过标准 Runs API 创建 upstream Run；若没有获批适配路径则阻止专项切换

### Requirement: 实时运行状态具有唯一事实源

聊天工作区 MUST 以当前 `useStream` 实例的实时投影作为 active run 的消息、agent values、tool calls、interrupts、loading、error 和 thread id 事实源。页面可以创建只读展示派生值，但 MUST NOT 维护会反向覆盖这些投影的独立可写镜像。

#### Scenario: 流式消息和加载状态同步更新
- **WHEN** active run 连续产生消息增量并最终结束
- **THEN** 页面按 stream 顺序展示消息、在运行期间显示 busy 状态，并在结束后恢复可提交状态

#### Scenario: 提交尚未被 SDK 接管
- **WHEN** 用户触发有效提交但 SDK 的 loading 投影尚未更新
- **THEN** 页面使用短暂 command pending 防止重复提交，且不会把该状态写回或伪装成 stream runtime 状态

#### Scenario: active thread 快速切换
- **WHEN** 用户在旧 thread 的异步刷新完成前切换到另一 thread
- **THEN** 旧响应不得覆盖新 thread 的实时消息、状态或 thread id

### Requirement: 持久 thread 数据通过正式控制面加载

聊天工作区 MUST 通过 `platform-api` runtime gateway service 加载 thread 列表、详情和持久 checkpoint history，并 MUST 保证同一 history view 只有该控制面加载路径可以写入。SDK live state 与持久 snapshot MUST 在显示边界合并，而不是互相回写。

#### Scenario: 选择已有 thread
- **WHEN** 用户从 thread 列表选择一个可读取的历史 thread
- **THEN** 页面通过正式 service 加载其详情和 checkpoint history，并将同一 thread id 绑定给 live stream

#### Scenario: snapshot 加载失败
- **WHEN** platform-api 无法返回所选 thread 的有效 snapshot
- **THEN** 页面显示归一化错误或既有损坏 thread 降级提示，不保留来自其他 thread 的 history

#### Scenario: run 结束刷新持久状态
- **WHEN** active run 正常结束或失败
- **THEN** 页面至多触发一次当前 thread 的持久状态刷新，且刷新结果必须通过 active thread 校验后才能展示

### Requirement: 工具调用使用统一生命周期投影

聊天工作区 MUST 使用 SDK tool call 投影展示每次调用的名称、参数、运行状态、输出和错误，并 MUST 将结果关联到正确的 assistant 回合。业务专用的结果 renderer 可以转换输出表现，但 MUST NOT 重新扫描完整实时消息流推导第二套 tool call 状态。

#### Scenario: 工具从运行中变为完成
- **WHEN** agent 发起工具调用并随后返回成功结果
- **THEN** 同一 tool card 从 running 更新为 finished，并展示对应输出且不生成重复卡片

#### Scenario: 工具执行失败
- **WHEN** SDK 报告某个 tool call 为 error
- **THEN** 对应 tool card 显示失败状态和可用错误信息，其他 tool call 状态不受影响

#### Scenario: task 子任务调用
- **WHEN** assistant 回合包含 `task` tool call
- **THEN** 页面继续以子任务语义展示其输入、运行状态和输出，同时使用 SDK 生命周期作为状态依据

### Requirement: Interrupt 可被可靠审阅和恢复

聊天工作区 MUST 展示 active thread 所有未解决的 protocol interrupts，阻止会与待决策运行冲突的新消息，并允许用户按 interrupt 支持的决策完成恢复。成功恢复后 MUST 清除已解决 interrupt，失败时 MUST 保留用户决策上下文和可重试反馈。

#### Scenario: 单个 HITL interrupt
- **WHEN** stream 暴露一个包含 approve、edit 或 reject 决策的 HITL interrupt
- **THEN** 页面只展示允许的决策并用符合 backend 协议的 resume command 恢复运行

#### Scenario: 多个未解决 interrupt
- **WHEN** stream 同时暴露多个未解决 interrupts
- **THEN** 用户可以辨认并处理每个 interrupt，页面不会只因 convenience alias 而静默丢弃其余 interrupt

#### Scenario: interrupt 恢复失败
- **WHEN** resume 请求被 SDK 或 platform-api 拒绝
- **THEN** 页面显示归一化错误、保持待决策界面，并允许用户修正或重试

### Requirement: 历史分支动作从 checkpoint 元数据执行

聊天工作区 MUST 从消息 metadata 和持久 checkpoint history 解析可用分支。重试、编辑重发或从历史节点继续 MUST 使用目标 SDK 支持的 checkpoint/fork 语义，并 MUST NOT 修改原有历史记录。

#### Scenario: 从 assistant 消息重试
- **WHEN** 用户对具有有效 checkpoint metadata 的 assistant 消息选择重试
- **THEN** 系统从对应 checkpoint 创建新的执行分支并保留原分支可访问

#### Scenario: 编辑历史 human 消息
- **WHEN** 用户编辑具有 parent checkpoint metadata 的 human 消息并提交
- **THEN** 系统从父 checkpoint 创建包含编辑内容的新分支，原消息和原分支保持不变

#### Scenario: 缺少 checkpoint metadata
- **WHEN** 历史消息没有执行分支动作所需的 checkpoint metadata
- **THEN** 页面不提供或拒绝该动作，并且不使用猜测的 checkpoint id 发起请求

### Requirement: 发送和取消保持可恢复交互

聊天工作区 MUST 防止重复提交，保留未成功发送的文本与附件，并在取消 active run 后恢复可编辑状态。服务端取消失败时，前端仍 MUST 停止当前 stream 并向用户提供一致反馈。

#### Scenario: 发送成功
- **WHEN** 用户提交有效文本或附件且当前无冲突运行
- **THEN** 页面立即阻止重复提交、展示 optimistic human message，并在 SDK 接管后继续显示实时结果

#### Scenario: 发送失败
- **WHEN** submit 在 active run 建立前失败
- **THEN** 页面恢复尚未被后续编辑覆盖的草稿和附件，并显示归一化错误

#### Scenario: 取消 active run
- **WHEN** 用户取消正在运行的对话
- **THEN** 页面尝试取消对应服务端 run、停止前端 stream，并恢复可继续编辑或重新发送的状态

### Requirement: 工作区局部交互不抢夺用户焦点

聊天工作区 MUST 保持现有 workspace shell、响应式布局、loading/empty/error 状态和基本可访问性。流式更新仅在用户仍接近底部且未查看 drawer、runtime options 或 message metadata 时自动跟随；否则 MUST 保留阅读位置并提供返回最新消息的明确操作。

#### Scenario: 用户停留在消息底部
- **WHEN** live stream 更新且用户仍接近消息底部
- **THEN** 消息视口自动跟随最新内容而不产生重复滚动任务

#### Scenario: 用户正在阅读历史内容
- **WHEN** 用户向上滚动或展开会暂停跟随的详情区域
- **THEN** 后续流式更新不强制改变阅读位置，并显示未读或返回最新消息提示

#### Scenario: thread 切换后的草稿隔离
- **WHEN** 用户在不同 project、target 或 thread 之间切换
- **THEN** composer 只恢复对应上下文的本地草稿，不把一个 thread 的未发送内容带入另一个 thread

### Requirement: Protocol v2 迁移保持数据与治理兼容

Protocol v2 迁移 MUST 保持既有 thread 数据、权限、项目隔离和审计语义。旧 snapshot 的读取兼容逻辑 MUST 只存在于有 characterization fixture 的 normalization 边界；正式 Chat 切换完成后 MUST 删除 legacy Run fallback 和旧 Runtime payload 生成路径。生产灰度与运行中自动回滚不属于本 change 的完成条件。

#### Scenario: 现有 thread 在升级后重新打开
- **WHEN** 用户在 v2 切换后打开一个格式有效的既有 thread
- **THEN** 页面继续展示其消息、history、tool result 和可用分支，不要求服务端数据迁移

#### Scenario: 已验收版本回滚
- **WHEN** v2 最短链或人工验收发现协议、debug 或 SSE 行为不兼容
- **THEN** 发布系统只能回滚到一个已验收的整体版本，不在同一会话内把正式 Chat fallback 到 legacy `/runs/*` 路由，也不修改 thread 数据

#### Scenario: legacy fallback 没有真实覆盖证据
- **WHEN** 某项 legacy snapshot fallback 没有 characterization fixture 或现有 snapshot 证明仍被需要
- **THEN** 实施删除该 fallback，而不是把它迁移进正式 live stream 路径

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
