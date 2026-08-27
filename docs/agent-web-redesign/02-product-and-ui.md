# 产品与 UI 设计

状态：Draft supporting material。

## 1. 产品定位

Agent Web 不是传统管理后台的“聊天页”，而是用户观察、约束和审阅一个长期运行 Agent
的工作台。第一屏必须直接进入可工作的 Agent 工作区，不做营销式 landing page。

核心体验目标：

- 用户始终知道当前 project、thread、Run 和 Agent 在做什么。
- 用户可以查看但不被流式输出抢走阅读位置。
- 工具、子任务、文件和人工审批成为可审阅的工作证据，而不是混在一条文本里。
- 复杂能力收在 inspector，不挤占聊天主任务。

## 2. 信息架构

```text
应用壳
├── 项目切换与全局导航
├── Agent 工作区
│   ├── Thread 列表
│   ├── 对话与 Agent 行动时间线
│   ├── 输入、附件、模型与运行选项
│   └── Inspector: Run / Plan / Files / History
├── Agents / Targets
├── Runs（跨 thread 的只读运行记录）
└── Settings（个人偏好与可见运行配置）
```

首期只实施 Agent 工作区和它完成工作所需的 project/thread 入口。`Runs`、目标目录与
Settings 在路由上预留，但不以空壳页面充数。

## 3. Desktop 工作台

### 三栏结构

```text
┌──────────────┬──────────────────────────────────────────┬───────────────┐
│ Project +    │ Thread header / Run status                │ Inspector     │
│ Threads      ├──────────────────────────────────────────┤ Run           │
│              │ Conversation + tool / task timeline      │ Plan          │
│ Search       │                                          │ Files         │
│ Filters      │                                          │ History       │
│ New thread   ├──────────────────────────────────────────┤               │
│              │ Composer: attach / options / send/stop   │               │
└──────────────┴──────────────────────────────────────────┴───────────────┘
```

| 区域 | 宽度与行为 | 内容 |
| --- | --- | --- |
| 左侧栏 | 272px 默认；可收为 56px rail；窄屏自动收起 | 项目名、thread 搜索、状态筛选、按时间分组的线程、新建线程 |
| 主栏 | `minmax(640px, 1fr)`；唯一主滚动区域 | thread 标题、Run 徽标、消息、行动时间线、composer |
| Inspector | 360px 默认；可关闭但保持选中 tab | Run 摘要、审批、计划、文件变更、checkpoint history |

用户可拖动 desktop inspector 边界；左栏只在宽屏提供拖动。每个面板关闭后保留局部
状态，避免查看文件时反复重建内容。

### 主时间线

主栏按“人类意图 -> Agent 推理/回复 -> Agent 行动 -> 结果”组织，而不是按 raw event
类型堆叠。

- 用户消息：右对齐，紧凑弱背景，可附带文件缩略信息。
- Agent 文本：左对齐，无大卡片外框，Markdown 阅读宽度 760px 以内。
- 工具行动：折叠的行级卡片，显示动词、目标、状态、耗时和可展开 output。
- 子任务：具有独立运行状态的嵌套卡片；不能伪装成普通 tool output。
- diff/file：只显示简要统计和可打开的 inspector 锚点，首期不在消息中嵌完整编辑器。
- HITL：固定在 composer 上方的高优先级审阅面板，显示批准、编辑、拒绝的可用动作。
- 失败：将“Run failed”与网络订阅失败分开显示，并给出确切恢复动作。

## 4. 视觉系统

### 设计性格

风格应接近 DeepSeek Harness 的安静、精确、工具感：浅色中性背景、细边界、有限阴影、
高信息密度和明显层级。避免营销卡片、强渐变、装饰性圆球和大面积紫蓝主题。

### 令牌

CSS 变量使用 `--aw-*` 前缀，定义在 `src/styles/tokens.css`；Tailwind 配置只引用这些
变量。下表是设计起点，不是复制 DeepSeek 品牌。

| 角色 | Light | Dark | 用途 |
| --- | --- | --- | --- |
| canvas | `#F8FAFC` | `#15171C` | 应用背景 |
| surface | `#FFFFFF` | `#202329` | 输入、浮层、inspector |
| sidebar | `#F1F4F8` | `#191C21` | 左侧导航 |
| border | `rgba(15,23,42,.10)` | `rgba(255,255,255,.12)` | 分隔与容器 |
| text primary | `#171A20` | `#F4F6F8` | 标题与正文 |
| text muted | `#667085` | `#98A2B3` | 辅助信息 |
| accent | `#4176E6` | `#7AA2FF` | 选中、链接、主动动作 |
| success / warning / danger | `#16804B` / `#B76A00` / `#C33B42` | 同语义高对比版本 | Run 与工具状态 |

使用 4px spacing 基线；常用间距为 8/12/16/24px；panel 圆角为 6px，浮层不超过 8px；
按钮和输入控件高度固定为 32/36/40px 三档。字体使用 Inter 作为 UI，代码使用等宽字体。
字距保持 0，不用为了“科技感”而压缩文字。

### 动效与反馈

- 流式文本直接增长，不使用逐字符打字机动画。
- Run 状态使用颜色、图标和文字三种信号；不能只靠颜色。
- panel 开合与提示最大 180ms；`prefers-reduced-motion` 下禁用。
- 拖动宽度时禁用 grid transition，防止面板边界落后鼠标。
- loading 是保留布局的 skeleton；error 是可恢复的明确状态，不是永远旋转的 spinner。

## 5. 关键工作流

### 新建并运行

1. 用户从左栏选择 project 与 Agent target，点击新建 thread 或进入已有 thread。
2. 在 composer 输入内容、选择附件和受权限约束的运行选项。
3. 提交后立刻出现 optimistic human message 和 `Creating run` 行。
4. Run 创建成功后，主栏显示 Run 状态，事件按顺序进入时间线。
5. 页面刷新、断线或导航回来时，先读取 Run snapshot，再恢复未消费事件。

### 审阅行动与审批

1. 工具/子任务默认折叠，只给名称、目标、状态与时间。
2. 用户展开某个行动时，自动跟随暂停，避免输出改变阅读位置。
3. 发生 interrupt 时 inspector 和 composer 上方同时出现同一个待决策引用；主栏不允许
   发送冲突的新消息。
4. 提交决策后 UI 只等待同一 Run 的服务端状态变化，不乐观地伪造成功。

### 断线恢复

1. 订阅断开显示“连接中断，Run 仍可能继续”的非终态提示。
2. 先 `GET Run`；若未终结，从记录的 event id 重连。
3. 若 Run 已终结，刷新 durable snapshot；不重新 POST 创建 Run。
4. 只有服务端 Run 状态为 failed/cancelled/interrupted 才展示终态。

## 6. 响应式与可访问性

| 宽度 | 布局 |
| --- | --- |
| >= 1280px | 三栏；左右栏可调整；主栏最小 640px |
| 960-1279px | 左栏收为 rail；inspector 以右侧抽屉出现 |
| 640-959px | 单主栏；thread 与 inspector 都是全屏 sheet |
| < 640px | 顶栏 + 单栏；composer 固定底部，所有二级信息走 sheet |

- tab 顺序遵循视觉顺序；所有 icon-only 控件必须有 `aria-label` 与 tooltip。
- tool output、状态和提示使用语义标题及可复制文本；键盘可展开/收起。
- 不以 hover 作为唯一入口；拖拽面板有明确的按钮替代方式。
- composer、审批和取消可通过键盘完成；尊重屏幕阅读器的流式更新节流。

## 7. 首期页面验收图

```text
登录后的首次可工作屏幕
  -> project 已明确
  -> thread 列表可读
  -> 当前 thread 状态可见
  -> composer 可用或明确说明为何不可用
  -> Run/工具/interrupt/error 均有独立状态
```

这比做一组“漂亮但无法恢复的聊天气泡”重要得多。

## 8. 旧端能力承接边界

`apps/platform-web` 是完整控制面；Agent Web 首期是其中面向执行者的 Agent 工作台。迁移的
单位是用户可观察的行为、受治理接口和持久数据，不是 Vue 路由或组件源码。旧端 thread、
checkpoint、Run 和项目数据继续由后端拥有，新端读写同一数据，禁止为切换入口导出、复制或
改写历史数据。

工作台必须承接旧 chat 基座已被真实用户使用的能力：project/target 恢复、thread 搜索筛选与
新建/删除、历史消息、文本及图片/PDF 附件、模型和工具运行选项、取消、工具/子任务状态、
interrupt 审阅、任务和文件查看、checkpoint/分支历史、重试/编辑分支、错误态和不抢滚动的
自动跟随。它们必须改为 Durable Run 的 snapshot 与 Protocol v2 事件投影，不能继续依赖旧的
`stream.submit()`、`respondAll()` 或“浏览器连接即 Run 生命周期”。

SQL Agent、Test Case Agent 和 Test Case Agent V2 不再各自拥有聊天页面；它们是同一工作台的
受控 target 预设。工作台保留 target 选择和只读上下文，Assistant、Graph、Runtime 模型/工具/
策略的创建和治理仍在 `platform-web`，直到独立迁移获得审批。

对当前用户不可见的 runtime 调试、资源模板和开发范式页面不属于正式 Agent Web。它们继续作为
内部调试或文档资产，而不是被伪装成生产工作台功能。
