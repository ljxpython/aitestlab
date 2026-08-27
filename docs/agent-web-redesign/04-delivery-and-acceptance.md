# 实施与验收计划

状态：Draft supporting material。所有任务以
`openspec/changes/add-react-agent-web/tasks.md` 为执行清单。

## 1. 实施前门禁

本变更是 B3：它引入正式 React 前端并替换受治理 Run contract。开始任何 API 或前端实现
前，owner 必须一起审批 proposal、delta specs、design、tasks 和 `verification.md` 的
pre-apply review。没有该审批，只允许维护本次方案文档。

必须确认：

1. `apps/agent-web` 的 product owner、发布 owner 和最终上线范围。
2. Durable Run 作为执行模型、Protocol v2 作为正式命令/事件协议的边界。
3. `fetch + ReadableStream` 的 Bearer token refresh 与 POST `since` 重连策略。
4. Run record、幂等 mapping、event replay/checkpoint 的数据保留与审计策略。
5. `platform-web` 的回退期限，以及 legacy `runs.stream` 的退役策略。

## 2. 建议的交付阶段

### Phase 0：契约冻结

- 隔离 PoC 的真实 E2E 证据已由 owner 验收，并已批准实施 Phase 1-3；仍未批准共享环境依赖升级、
  staging/生产切流或 legacy `runs.stream` 退役。
  为完成真实浏览器 E2E，允许创建最小 `agent-web` transport harness：它只覆盖真实登录、Bearer
  `fetch` SSE、创建/重连/取消/interrupt 恢复，不提供三栏工作台或正式用户入口。
- 在 `platform-api` 定义 Protocol v2 command/event、Run snapshot/cancel、错误码、幂等冲突
  语义和 event envelope 的边界。
- 确认 runtime-service 对 durability、checkpoint、Protocol v2 `since` replay 的真实支持度。
- 在隔离 PostgreSQL/Redis 环境验证新版 Agent Server、全部 graph、platform auth 与 custom routes；
  本地流消费者优先收敛到稳定 `version="v2"`，v3 仅做内部 PoC。
- 固定镜像 digest 与兼容依赖组合；验证 `run.start` 的 `run_id`、`Idempotency-Key`、单 thread
  active Run、interrupt ID、POST `since` replay、operation/audit 生命周期与凭证脱敏。
- 写 platform-api/runtime-service 契约测试，并执行真实 E2E：部署实际 Agent Web、platform-api、
  runtime-service、Agent Server 与隔离 PostgreSQL/Redis；使用真实 delegation credential、Bearer
  fetch SSE 和真实 graph，禁止以 mock upstream 或内存替身替代。

完成条件：所有 PoC 硬退出条件有可复现证据；owner 已批准进入 Phase 1-3。仓库内仍需补齐可重放的
命令、输入和结果明细，作为后续 staging/生产门禁证据。

### Phase 1：Run Coordinator 与 gateway

- 以 Protocol v2 `run.start`/`input.respond` 建立或恢复 Run，并冻结可信 RuntimeContext/RuntimeOptions。
- 以 `Idempotency-Key` header 实现受控幂等记录与请求摘要冲突检测；header 不进入 Protocol payload。
- 每个 Durable Run 一对一映射为 project operation，并写入 operation 与 runtime run 生命周期审计。
- 复用 Run 查询/取消资源与 Protocol v2 events；不向 Agent Web 暴露 legacy `runs.stream`。
- 将 authorization、project scope、delegation 与审计挂在 control plane 边界。

完成条件：同 key 重试绝不重复执行；SSE 断开不改变 Run；非授权 actor 不能读取 event。

### Phase 2：React 壳和静态 UI

- 初始化 `apps/agent-web`：React 19、TypeScript、Vite 7、Router、Query、Tailwind 4、
  Base UI 和 token sheet。
- 实现 AppBootGate、WorkspaceFrame、thread sidebar、主时间线、composer、inspector。
- 先以 fixture 测量响应式、空态、加载态、失败态和 reduced motion。

完成条件：三栏在 desktop 稳定，tablet/mobile 不重叠，所有 icon 控件可键盘访问。

### Phase 3：Durable Run transport 与会话体验

- 实现单一 `RunEventsController`，负责 command/hydrate/subscribe/reconnect/cancel/respond。
- 使用 Bearer `fetch + ReadableStream` 解析 POST SSE，以 Protocol `seq` 去重和重连；将服务端
  snapshot 与时间线投影分开。
- 实现草稿隔离、自动跟随暂停、回到最新、工具卡片、interrupt 审阅和终态刷新。

完成条件：刷新、断网、切换 thread、取消和审批不产生重复 Run 或串写消息。

### Phase 4：最短链集成与迁移

- 在受控环境接通 `agent-web -> platform-api -> runtime-service`。
- 与现有 `platform-web` 对照 thread 历史、工具、interrupt、权限拒绝和项目隔离。
- 生产切流采用 feature flag 和项目白名单灰度：先限内部/测试项目，再扩大范围；旧
  `platform-web` 与 legacy `runs.stream` 必须保持可回退，不做静默替换。

完成条件：灰度真实 E2E、错误率/恢复率/取消率、权限审计和人工验收达标；旧入口回退明确且
不修改持久 thread 数据。

### Phase 5：发布与收敛

- 由 owner 决定分批用户/项目、观测面板、支持路径与回退开关。
- React 业务实现只在 Phase 0 真实 E2E 全部通过并取得 owner 批准后开始；共享环境只部署已验证的
  固定镜像 digest 与锁文件组合，先经 staging 验收。
- Agent Web 始终不使用 legacy `runs.stream` fallback。legacy 路径仅在没有生产用户依赖旧页面、
  灰度指标稳定、回退窗口结束且 owner 再次批准后退役；不按日期或新页面发布即删除。
- 被接受的 OpenSpec delta specs 同步到 `openspec/specs/` 后才归档 change。

完成条件：B3 验证证据 Complete，owner 接受，文档与 runbook 已更新。

## 3. 验收矩阵

| 场景 | 最小证明 | 预期 |
| --- | --- | --- |
| 正常创建 | 相同输入一次提交 | 返回一个 Run，事件和 snapshot 一致 |
| 幂等重试 | 同 key 重放 POST | 同一 `run_id`，无第二次 Agent 执行 |
| key 冲突 | 同 key 不同 input | `409`，不改原 Run |
| 并发创建 | 同一 thread 已有 active Run | 新 `run.start` 被确定拒绝，时间线不串写 |
| run id | `run.start` 成功返回 | 获得稳定 `run_id`，不查询“最新 Run”猜测 |
| 页面刷新 | Run running 时刷新 | 先查询再恢复，绝不重复 POST |
| SSE 断线 | 中途断开 transport | Run 保持运行；携带最后 `seq` 以 POST `since` 续接 |
| event 重放 | 重复或乱序 event | 时间线无重复，终态不回退 |
| 取消 | running Run 调 cancel | snapshot 进入 cancelled/interrupted，composer 恢复 |
| 审批恢复 | waiting_for_input Run resume | 只恢复目标 Run，决策与 interrupt 匹配 |
| 多中断 | 同一 thread 有多个 interrupt | 按服务端 interrupt ID 恢复，不靠前端索引猜测 |
| 权限拒绝 | 错 project/actor | 不创建、不订阅、不泄漏 Run 摘要 |
| runtime 重启 | checkpoint 后重启 worker | 恢复或确定失败；不假装成功 |
| 治理记录 | Run 创建、恢复、终结与取消 | project operation 与审计生命周期完整，token/完整消息未落库 |
| 真实 E2E | 已部署完整链路与隔离 PostgreSQL/Redis | 真实鉴权、真实 graph、真实 SSE 下通过创建、重连、取消和恢复；无 mock upstream |
| UI 阅读 | 用户向上滚动后流式输出 | 不抢焦点，出现“回到最新” |
| 响应式 | 1440/1024/768/390 viewport | 布局无溢出、控件可达、文本不遮挡 |

## 4. 非目标

- 首期不做终端、IDE、PR 自动化、GitHub/Slack/Linear 集成。
- 不迁移 DeepSeek Harness 插件框架。
- 不把 runtime-web 发布成生产工作台。
- 不在 Agent Web 中实现新的 Agent prompt、工具选择或 graph 编排。
- 不为 legacy `runs.stream` 写第二条 React 客户端路径，也不以本地 LangGraph v3 替换远程 Protocol v2。

## 5. 当前交付状态

- 已建立：`apps/agent-web/` 的应用边界与本方案文档组。
- 已建立：B3 OpenSpec change `add-react-agent-web`。
- 已完成局部实现：React 静态工作台和 Bearer fetch SSE transport；platform-api Durable Run
  Coordinator、`runtime_runs` migration 与 focused local checks。实现与证据细节以 change 的
  `verification.md` 为准。
- 未开始或未完成：runtime-service durable 配置、真实 isolated E2E、共享环境 migration、staging/生产发布。
- 当前可执行范围：已获准实施 Phase 1-3 的 gateway/runtime 合约、React 产品工作台和 Durable Run
  transport；共享环境依赖升级、staging/生产切流和 legacy `runs.stream` 退役仍须 owner 再次批准。

## 6. 旧端能力对齐与迁移矩阵

本矩阵以 `apps/platform-web/src/router/routes.ts` 的 45 个页面级入口和其复用的 chat 基座为
盘点范围。这里的“迁移”只承诺行为、权限、审计与数据连续性，不承诺复制 Vue 文件、样式或
旧流式 SDK 调用。

| 旧端范围 | 现有内容 | Agent Web 承接方式 | 首次出现阶段 |
| --- | --- | --- | --- |
| 通用 Chat | target 恢复、thread、消息、附件、运行参数、Run、工具、interrupt、历史/分支、文件和任务 | 完整重设计为三栏工作台；以 Protocol v2 + Durable Run 投影替代旧 SDK stream | Phase 2-4，Phase 0 仅 transport harness |
| SQL Agent | 固定 `sql_agent` graph 的通用 chat 基座 | 同一工作台 target 预设，不建立第二套页面 | 通用 Chat 达标后 |
| Testcase Agent / V2 生成 | 固定 graph、概览条和通用 chat 基座 | 同一工作台 target 预设；概览只在对应项目能力已可读时展示 | 通用 Chat 达标后 |
| 项目上下文 | 项目选择、项目详情、成员和创建 | 工作台只保留项目切换、读取当前项目权限和 target 选择；项目治理继续旧端 | Phase 2；治理后续单独变更 |
| Assistant 与 Graph | 目录、创建、编辑、详情 | 工作台只读选择已授权 target；配置、发布、删除继续旧端 | Phase 2；治理后续单独变更 |
| Threads | 全局/项目列表与详情 | 左栏承接当前 target 可读 thread 的搜索、筛选、新建、选择、删除；跨 target 管理仍旧端 | Phase 3-4 |
| Runtime | models、tools、policies、runtime 总览 | composer 展示服务端许可的运行选项；目录和策略治理继续旧端 | Phase 3；治理后续单独变更 |
| Operations 与 Audit | 列表、详情和正式审计查询 | inspector 展示当前 Run 的安全摘要和状态；全局列表、导出与审计检索继续旧端 | Phase 3-4；治理后续单独变更 |
| Knowledge | 文档、检索、图谱、设置 | 附件/文件和 Agent 产物进入 inspector；知识库 CRUD、检索调试和图谱治理继续旧端 | 附件能力验证后；治理后续单独变更 |
| Testcase 用例/文档管理 | cases、documents 及 V2 对应页面 | 生成入口迁入；用例和文档管理继续旧端，避免把领域管理塞进对话界面 | 后续独立变更 |
| 账号与通知 | profile、security、announcements | 认证和基础账户信息可由共享壳提供；安全设置、公告管理不纳入首期工作台 | 后续独立变更 |
| 平台治理 | users、service accounts、control plane、platform config、system governance | 保留 `platform-web`，不迁入工作台 | 后续独立 B3 变更 |
| 资源和调试 | resources、UI assets、Chat Debug | 不迁入正式 Agent Web；分别继续作为文档资产和内部 runtime 调试入口 | 不迁移为生产页面 |

首期产品对齐不是“页面数量相等”，而是以下聊天工作流在真实 E2E 下可连续完成：选择已授权
project/target、打开或新建 thread、发送文本和受支持附件、创建一次 Durable Run、观察消息与
工具/子任务、取消或按 interrupt ID 恢复、刷新/断线后以 snapshot 和 `since` 续流、查看任务/
文件/历史分支，并在权限拒绝、失败或终态时得到明确且不丢失上下文的反馈。

任何旧能力在新入口启用前都必须归入以下一种结果：已按行为对齐、继续由旧端拥有并有明确入口、
在独立变更中迁移，或被 owner 明确退役。禁止静默删除、用空壳页面替代，或把调试功能当作生产
能力。全量 React 重实现是可行的长期目标，但每一组控制面页面仍需要独立契约、权限/审计和发布
审批；它不是本 change 的隐含交付物。
