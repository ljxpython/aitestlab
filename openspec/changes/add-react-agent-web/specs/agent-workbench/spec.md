## ADDED Requirements

### Requirement: React Agent 工作台提供可工作的三栏会话体验

系统 MUST 在 `apps/agent-web` 提供 React 正式 Agent 工作台。desktop MUST 提供 thread
sidebar、对话/行动主栏和可关闭 inspector；主栏 MUST 保持会话为第一优先级。应用 MUST
提供 loading、empty、error、interrupt 和 terminal Run 的明确状态，并支持浅色、深色、
`prefers-reduced-motion` 与键盘可达的基础交互。

#### Scenario: 用户打开现有 thread
- **WHEN** 已授权用户在已选 project 打开可读取 thread
- **THEN** 工作台显示该 thread 的 durable snapshot、可用 thread 列表和当前 Run 状态，且不会显示其他 project 的数据

#### Scenario: 窄屏工作区收敛
- **WHEN** viewport 宽度不足以同时容纳三栏
- **THEN** 系统将 sidebar 和 inspector 收敛为可访问的 rail 或 sheet，主对话栏保持可读且控件不重叠

### Requirement: 工作台以稳定行动时间线展示 Agent 证据

系统 MUST 将用户消息、agent 文本、工具调用、子任务、文件引用、interrupt 和 Run 错误渲染为
稳定的时间线项。工具或子任务的状态 MUST 来自同一 Run 的受控事件/快照，不得从自由文本
猜测。用户阅读历史内容时，流式更新 MUST 不强制改变滚动位置，并 MUST 提供回到最新内容的
明确操作。

#### Scenario: 工具调用完成
- **WHEN** 同一 tool call 的事件从运行中变为完成或错误
- **THEN** 系统更新原有时间线项的状态和输出，而不创建重复 tool card

#### Scenario: 用户暂停自动跟随
- **WHEN** 用户离开消息底部或展开会暂停阅读的详情
- **THEN** 后续事件不抢夺滚动位置，并以未读提示提供返回最新内容的操作

### Requirement: 工作台在未解决 interrupt 时提供受控审阅

系统 MUST 展示当前 Run 的所有未解决 interrupt，并只提供服务端声明允许的 approve、edit 或
reject 决策。存在会冲突的未解决 interrupt 时，系统 MUST 阻止创建冲突的新 Run；恢复失败时
MUST 保留用户决策上下文和可重试反馈。

#### Scenario: 用户恢复待审批 Run
- **WHEN** 用户提交匹配当前 interrupt 的合法决策
- **THEN** 系统仅调用目标 Run 的 resume 接口，并等待该 Run 的 snapshot/event 确认状态变化

### Requirement: 工作台保持旧 chat 用户工作流的行为连续

系统 MUST 以一个 target 驱动的工作台承接通用 Chat、SQL Agent、Testcase Agent 与 Testcase
Agent V2 的执行型会话能力。系统 MUST 支持已授权 project/target 的恢复、thread 搜索筛选、
新建/选择/删除、文本和受支持附件、运行选项、取消、工具/子任务、任务/文件、历史/分支以及
重试或编辑后产生的分支。实现 MUST 以 Durable Run snapshot 和 Protocol v2 事件为事实来源，
不得复制旧 `runs.stream` 或 Vue SDK stream 状态机。

#### Scenario: 专用 Agent 进入统一工作台
- **WHEN** 用户从 SQL Agent 或任一 Testcase Agent 入口进入已授权 project
- **THEN** 系统以受控 target 预设打开同一工作台，并保留该 target 的 thread、权限和 Run 隔离，不渲染第二套聊天页面

#### Scenario: 用户在旧线程继续工作
- **WHEN** 用户打开同一 project/target 下已有的可读取 thread
- **THEN** 系统读取既有 thread、checkpoint 和 Run 数据，不复制或改写历史数据，并在刷新或断线后先 hydrate snapshot 再续订事件

### Requirement: 工作台不得吞并未迁移的控制面能力

系统 MUST 只在工作台中呈现当前会话所需的 project、target、运行选项和 Run 摘要。Assistant/
Graph 配置、项目成员、知识库管理、Runtime 策略、全局 Operations/Audit、账号和平台治理在未有
独立批准的迁移 change 前 MUST 继续由 `platform-web` 拥有；资源模板和 runtime 调试 MUST 不作为
正式 Agent Web 页面。

#### Scenario: 用户需要管理目标配置
- **WHEN** 用户在工作台中需要创建、编辑或治理 Assistant、Graph 或 Runtime 策略
- **THEN** 系统提供明确的受权限约束入口到当前控制面，而不以空壳、复制的未审计表单或调试接口替代
