## Context

本变更跨 `apps/agent-web`、`apps/platform-api` 和 `apps/runtime-service`。新 React
工作台的视觉参考为 DeepSeek Harness，交互参考为 Open SWE；现有正式聊天使用 Vue，且
`platform-api` 同时公开 Protocol v2 command/event 和创建即流式返回的 run 入口。

正式 production chain 必须保持 `agent-web -> platform-api -> runtime-service`。当前
gateway 已负责 project scope、role、delegation credential、runtime target/options 校验；
`runtime-web` 是内部直连调试壳。迁移的核心是将 durable Run 与浏览器观察通道分离。

## Goals / Non-Goals

**Goals:**

- 新建 React Agent 工作台，提供三栏 thread、消息/行动时间线、composer 与 inspector。
- 将正式 Agent Web 的运行创建、查询、事件订阅、取消和恢复收敛为 Durable Run resource。
- 保证 Run 在刷新、SSE 断开或页面切换后不重复执行，并保持 project/permission/audit 边界。
- 借鉴两份参考实现的有效交互与视觉模式，不引入其无关应用框架。

**Non-Goals:**

- 不迁移 DeepSeek Harness Cordis 插件系统、Open SWE 外部协作和 sandbox 能力。
- 不将 `runtime-web` 作为生产入口或 Agent Web 的协议 fallback。
- 不在本 change 未获批准前实施 API、数据库、runtime 或前端业务代码。

## Decisions

### React 应用使用独立边界

`apps/agent-web` 使用 React 19、TypeScript、Vite 7、TanStack Router/Query、Tailwind 4、
Base UI 和自有 `--aw-*` CSS token。CSS token 是视觉事实源，Tailwind 仅消费 token。

选择理由：React 与 Open SWE 的流式 UI 机制同构，Vite/TypeScript 与两个参考项目接近；
三栏布局和 token 可以借鉴 DeepSeek Harness，而无需引入 Cordis。

拒绝替代方案：继续基于 Vue 重做样式会保留现有前端的实现边界，不能满足已确认的 React
方向；复制 DeepSeek Harness workspace packages 会引入多余的 plugin host。

### Durable Run 由 control plane 协调，Protocol v2 作为远程协议

`platform-api` runtime gateway application 层新增唯一 Run Coordinator。它认证 actor、
校验 project/thread、冻结受控 runtime options、保证幂等并调用 LangGraph。Protocol v2 的
`run.start`/`input.respond` 是其正式命令面，event stream 是观察面；run 的业务执行、checkpoint
与 graph 状态由 `runtime-service` 持有。

Coordinator 将每个 Durable Run 一对一映射为 project operation。Run 是 AI 执行事实，operation
是项目权限、取消责任、审计与平台查询事实；同一 thread 同时至多一个 active Run，第二个
`run.start` 返回确定冲突。

选择理由：project/permission/delegation 已在 control plane；让 React 或多个入口各自拼装
LangGraph run 会破坏治理并造成重复状态机。

拒绝替代方案：让 Agent Web 直连 runtime-service 不能证明租户和权限隔离；在每个 route
handler 复制幂等/配置检查会产生不一致入口。

### 正式 Protocol v2 分离命令与事件观察

目标交互为 `POST commands` 的 `run.start`/`input.respond`、已有 `GET run` snapshot、
`POST stream/events` 和已有 Run cancel。创建幂等由 gateway 的受控记录保证；事件订阅用
POST body 的 `since` 恢复。snapshot 是终态和状态事实，SSE 只提供事件投影。

浏览器将 `Idempotency-Key` 放在 HTTP header；gateway 按 project/thread/key 与规范化请求摘要
持久化后剥离该 header，绝不把私有幂等字段加入 Protocol v2 payload。`run.start` success result
必须提供可解析的 `run_id`；未通过隔离 PoC 前不得以查询“最新 Run”作为替代。`input.respond`
必须以服务端 interrupt ID 精确恢复，不能以 thread 或前端索引推断目标。

选择理由：浏览器生命周期不应决定 agent 执行；该模型支持刷新、断线恢复、重复 completion
webhook 和 worker 重启后的确定行为。

拒绝替代方案：保留 legacy `POST /runs/stream` 作为 Agent Web fallback 会保留两条生产状态机；
将 SSE 最后一帧当成功证明无法处理断线和重放。Protocol v2 不被移除，它就是 Durable Run 的
远程命令和观察协议。

### Bearer SSE 使用单一 fetch transport

现有前端采用 Bearer access token + refresh。原生 `EventSource` 不能加 Authorization header，
因此默认用带授权 header 的 `fetch` ReadableStream 封装一个 `RunEventsController`；它向
POST event stream 提交最后确认 `seq` 作为 `since`，业务组件只消费规范化事件和 snapshot，
不能解析 raw SSE。

gateway 保留 Protocol v2 event type、payload 语义和 `seq` 顺序；仅允许经过测试的敏感字段
规则脱敏，不能重命名、合成或重排事件。RunEventsController 集中解析标准帧；审计、日志和
客户端诊断不得记录 Bearer token、Authorization header 或完整输入消息。

替代方案是由 IAM 提供同源 HttpOnly session cookie 后使用 EventSource。该替代会改变认证
模型，只有 owner 明确批准时采用。Bearer token 不得放入 URL。

### UI 使用一个 active Run controller

TanStack Query 缓存 project/thread/run snapshot；`RunEventsController` 仅管理 active run
订阅、event id、reconnect 与 terminal refresh；`useRunTimeline` 只派生消息/tool/interrupt
展示。composer 草稿和 panel UI 仍是局部状态。

选择理由：它保留 Open SWE 的“live projection 不手工镜像”优点，同时满足 durable Run
snapshot 是事实源的要求。

## Risks / Trade-offs

- [legacy `runs.stream` 与 Protocol v2 的双入口] -> owner 在 apply 前确认唯一 production
  surface、退役窗口和回退路径；Protocol v2 作为正式协议不退役。
- [runtime 不支持可靠 replay/durability] -> 先以 runtime harness 证明；失败时阻止发布而非
  在浏览器重发创建请求。
- [幂等记录与上游创建出现部分失败] -> 使用 HTTP `Idempotency-Key` 持久化请求摘要与状态；
  PoC 必须证明 `run.start` 返回 run_id，补偿任务只更新确定状态。
- [线程级 event stream 导致 Run 串写] -> 每个 thread 同时只允许一个 active Run，并用 PoC
  验证事件 Run 关联和多 interrupt 的精确恢复。
- [长任务无平台治理记录] -> 每个 Durable Run 一对一映射 project operation，并记录 operation
  与 runtime run 生命周期审计。
- [SSE 长连接消耗资源] -> gateway 限制订阅、断线清理、按 thread/run 授权，并保持 upstream
  subscription 与 Run 生命周期分离。
- [UI 信息密度过高] -> 主栏只保留会话，文件/plan/history 移入 inspector；以实际任务衡量后
  再引入 Monaco/terminal。
- [参考代码许可证] -> 优先重写小模块；复制 MIT 实质片段时保留版权和许可证。

## Migration Plan

1. Owner 已验收隔离 PoC 的真实 E2E 证据，并批准实施 Phase 1-3：gateway/runtime 合约、React
   产品工作台和 Durable Run transport。Phase 0 的最小 `agent-web` transport harness 仍仅用于真实
   浏览器登录、Bearer fetch SSE、创建/重连/取消/interrupt 恢复 E2E；共享环境依赖升级、staging/
   生产切流和 legacy `runs.stream` 退役仍须再次批准。
2. 先在隔离 PostgreSQL/Redis 与固定镜像 digest 上升级并验证 Agent Server、CLI、SDK、
   custom routes、platform auth 与所有 graph；再在 platform-api/runtime-service 建立 DTO、
   Coordinator、HTTP header 幂等、operation/audit 映射、durability/replay 与 Protocol v2
   契约测试。PoC 必须通过 run_id、单 active Run、interrupt ID、`since` replay 的硬门禁，且必须
   使用已部署的完整真实链路与隔离 PostgreSQL/Redis 运行 E2E；mock upstream 不能作为该证据。
3. 初始化 Agent Web 静态 shell 和可访问设计系统，再接入 Durable Run transport。
4. 已获批实现 React 业务页面；只有在固定 digest/锁文件组合获得共享环境升级批准后，才可部署至
   staging。staging/生产灰度仍需 feature flag、项目白名单和单独 owner 批准；旧 `platform-web`
   不被静默替换，thread 数据不迁移或改写。
5. 达到灰度 E2E、稳定性指标和 owner 接受后再扩大入口；仅在旧页面无生产依赖、回退窗口结束并
   再次批准后退役 legacy `runs.stream`。若失败，回退到已验证旧页面/接口，不删除 Run 或 checkpoint 数据。

## Open Questions

- `fetch` SSE transport 的 parser、重试上限和 token refresh 并发策略是什么？
- 幂等 mapping、事件 replay 和 Run 摘要的 retention、审计字段及数据库 ownership 由谁批准？
- `platform-web` 保留多久作为回退，以及何时移除 legacy `runs.stream` production surface？

## LangGraph 技术裁决与旧端迁移边界

用户指定的 `apps/runtime-service/runtime_service/docs/knowledge/09-langgraph-runtime-upgrade-and-event-migration.md`
和 Open SWE 的 `12-migration-phase-2-durable-run-and-stream-zh.md` 是本 change 的 Durable Run
技术参考。两者都要求 Run 脱离浏览器连接、checkpoint/终态/通知有固定顺序、SSE 不是事实源，
且 production UI 不得采用 runtime-web 的直连模式。

当两者在具体 HTTP 形态冲突时，本项目采用前者所冻结并由当前官方 Agent Server 文档验证的
Protocol v2：`run.start`、`input.respond`、`POST /threads/{thread_id}/stream/events` 和 body
`since`。Open SWE 的 REST URL、GET EventSource/`Last-Event-ID` 和请求体幂等键不迁入；其
Coordinator、`durability="sync"`、`stream_resumable=True`、Run 查询优先和终态顺序仍是实现
约束。gateway HTTP `Idempotency-Key` 保持在 Protocol payload 之外。

旧 `platform-web` 的全部业务能力理论上都可在 React 重实现，但此 B3 change 的产品范围仅为
Agent 工作台。通用 Chat、SQL Agent、Testcase Agent 和 Testcase Agent V2 收敛为一个 target
驱动的工作台；项目/target 选择、thread、附件、运行选项、工具/子任务、interrupt、任务/文件、
历史/分支与恢复必须逐项验证行为连续。项目、知识库、runtime 配置、运维、审计、账号和平台治理
仍由旧控制面拥有，除非另一个已批准的 B3 change 明确接管。新旧入口共享持久 thread、Run 和
checkpoint，发布时不得执行前端驱动的数据复制或改写。
