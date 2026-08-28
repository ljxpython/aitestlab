## 1. 审批与契约冻结

- [x] 1.1 owner 已评审 proposal、delta specs、design、tasks 与 `verification.md`，验收隔离 PoC 的真实 E2E 证据并批准实施 Phase 1-3 的 gateway/runtime 合约、React 产品工作台和 Durable Run transport；共享环境依赖升级、staging/生产切流和 legacy `runs.stream` 退役仍待复审。
- [x] 1.2 定义 Durable Run DTO、状态枚举、错误码、Protocol v2 command/event、event `seq`、POST `since` 重放和 Run/operation 关联语义。
- [x] 1.3 定义 `Idempotency-Key` HTTP header、唯一键、请求摘要、冲突和 retention 规则；禁止把私有幂等字段送入 Protocol payload。
- [ ] 1.4 在隔离 PostgreSQL/Redis 和固定镜像 digest 上验证新版 Agent Server、CLI、SDK、全部 graph、custom routes、platform auth、checkpoint 与 Protocol v2 replay；本地消费者收敛到稳定 `version="v2"`，v3 仅内部 PoC。
- [ ] 1.5 以真实 Protocol v2 证明 `run.start` 返回 `run_id`、同 thread 单 active Run、事件可关联 Run、多 interrupt 以 interrupt ID 精确恢复，以及 POST `since` 的 replay 顺序。
- [ ] 1.6 证明每个 Run 可映射 project operation 与审计生命周期，且请求、审计和诊断不保存 token、Authorization header 或完整输入消息。
- [ ] 1.7 创建并部署最小 `agent-web` transport harness，在真实 `agent-web -> platform-api -> runtime-service -> Agent Server -> 隔离 PostgreSQL/Redis` 链路执行 E2E，使用真实 delegation credential、Bearer fetch SSE 与实际 graph；不得以 mock upstream 或内存替身替代，不得扩展为产品 UI，并将输入、命令、结果和未覆盖边界回填 `verification.md`。
- [x] 1.8 以 `09-langgraph-runtime-upgrade-and-event-migration.md` 与 Open SWE Durable Run 阶段资料逐项冻结技术裁决：Protocol v2 `run.start`/`input.respond`、POST SSE `since`、本地 `version="v2"` StreamPart、gateway HTTP `Idempotency-Key`；发现上游版本或资料冲突时记录并提交 owner，不保留双协议。

## 2. Platform API Durable Run Coordinator

- [x] 2.1 在 `runtime_gateway` application 层实现唯一 Run Coordinator，复用 project scope、actor、delegation、target/options policy，并一对一映射 project operation。
- [x] 2.2 建立 Run/operation/idempotency 持久记录或等价受控存储，以 HTTP `Idempotency-Key` 实现相同 key 的安全重试与不同摘要冲突。
- [x] 2.3 以 Protocol v2 `run.start`/`input.respond` 操作 Run，复用 Run 查询/取消与 POST event stream，移除 Agent Web 对 legacy 创建即流式接口的使用。
- [x] 2.4 让 fetch SSE 订阅正确处理 authorization、POST `since`、upstream 断开和 event 脱敏，且不改变 Run 状态。
- [x] 2.5 为 command、查询、订阅、取消和恢复写 focused gateway/contract tests，包括 actor/project 拒绝、单 active Run、run_id、interrupt ID、幂等和审计路径。

## 3. Runtime Durable Execution

- [ ] 3.1 在 runtime-service 装配 durable、resumable run，并冻结可信 RuntimeContext/RuntimeOptions；gateway 已补齐持久 interrupt-to-run ID 索引，但仍待真实隔离 E2E 验证 Agent Server durable/resume 行为。
- [ ] 3.2 保证 checkpoint、Run terminal state、terminal SSE event、completion webhook 的写入顺序。
- [ ] 3.3 验证 worker 重启、重复 webhook、cancel、多 interrupt resume、Run/operation 审计的确定行为。
- [x] 3.4 将本地 v1 元组流消费者迁移至 `version="v2"` 统一 StreamPart；仅以 harness 验证 v3 event streaming 的消息、状态、子图和 interrupt 投影，不将其发布为 HTTP 协议。
- [x] 3.5 更新最窄 runtime harness 与运行时标准/运行手册影响记录。

## 4. React Agent Web Foundation

- [x] 4.1 初始化 `apps/agent-web` 的 React 19、TypeScript、Vite、Router、Query、Tailwind、Base UI、Zod 和测试脚本。
- [x] 4.2 建立 `--aw-*` token、亮暗主题、全局 reset、reduced-motion 与可访问 primitive。
- [x] 4.3 实现 AppBootGate、WorkspaceFrame、responsive sidebar/inspector 和 project/thread 导航。
- [x] 4.4 实现消息、工具、子任务、Run status、error/empty/loading、composer 与 interrupt 审阅的静态 fixture 视图。
- [x] 4.5 为响应式布局、键盘访问和关键空/错状态添加 focused component/browser checks。
- [ ] 4.6 逐项重实现旧 chat 的 project/target 恢复、thread 搜索筛选/新建/删除、附件、运行选项、取消、工具/子任务、任务/文件、历史/分支、重试/编辑分支和自动跟随；每项必须以新的 Durable Run contract 验收，不复制 Vue SDK stream 状态机。
- [x] 4.7 将 SQL Agent、Testcase Agent 和 Testcase Agent V2 收敛为受控 target 预设，并验证 target、project、thread、Run 和权限不会串写；不建立第二套聊天页面。
- [x] 4.8 为未迁移控制面能力保留受权限约束的明确入口，核对项目、Assistant/Graph、Knowledge、Runtime、Operations/Audit、账号和平台治理均未被空壳替换、静默删除或错误迁入工作台。

## 5. React Durable Run Interaction

- [x] 5.1 实现授权 API client，复用平台 token refresh 和 `x-project-id` 语义，不将 Bearer token 放入 URL。
- [x] 5.2 实现单一 `RunEventsController`，完成 command/hydrate/fetch-subscribe/reconnect/cancel/respond 和 Protocol `seq` 去重。
- [x] 5.3 将 thread/run snapshot 放入 Query，将时间线投影、草稿隔离、自动跟随暂停和 terminal refresh 保持为单向派生。
- [x] 5.4 对刷新、断线、乱序/重复 event、thread 切换、取消、单 active Run 和 interrupt ID resume 编写 focused tests。
- [ ] 5.5 在真实最短链展示 tool lifecycle、错误、恢复和 approval，不实现 legacy `runs.stream` fallback。

## 6. 集成、发布与证据

- [ ] 6.1 在 staging/灰度环境以真实 E2E 验证 `agent-web -> platform-api -> runtime-service` 的 `run.start`/query/events/`input.respond`/cancel 完整链，并记录稳定性、恢复率、取消率、权限审计与回退演练。
- [ ] 6.2 完成 1440/1024/768/390 viewport 的人工可用性和基本可访问性验收。
- [ ] 6.3 制定 feature flag、项目白名单灰度、固定 digest/锁文件共享环境升级、可观测性、用户支持与不改 thread 数据的回退方案。
- [x] 6.4 维护 `verification.md` 的 pre-apply decision、命令、输入、结果、未覆盖边界、文档/runbook 影响与 disposition。
- [ ] 6.5 变更被接受后同步 delta specs 到 `openspec/specs/`，再按流程 archive；未经请求不执行 git commit 或 push。
