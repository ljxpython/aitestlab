## Context

当前正式聊天页面经 `createLanggraphClient()` 访问 `platform-api /api/langgraph`，网关只实现 legacy thread/run 路由（包括 `/threads/{thread_id}/runs/stream`）。现有 `@langchain/vue` 0.4.5 的状态与页面手工 history、branch、interrupt 推导交织。目标 SDK 的 v2-native runtime 改为 thread-scoped command 和事件订阅：`POST /threads/{thread_id}/commands` 与 `POST /threads/{thread_id}/stream/events`；后者用 `since` 回放序号后的事件。

官方 Protocol v2 `run.start.params` 当前只定义 `assistant_id`、`input`、`config` 和 `metadata`，没有调用级 `context`。Agent Server 官方 `Auth` 可以在服务端认证每个请求，并通过 `runtime.server_info.user`/auth config 向运行暴露认证用户；LangGraph 同时允许 graph 通过 `RunnableConfig` 读取每次运行配置。现有仓库却把身份、项目、模型、工具和 prompt 全部放在 `RuntimeContext`，因此必须先拆开信任域与运行配置，再迁移 v2。

这是一项正式 runtime gateway 契约迁移。`platform-api` 仍拥有 actor、项目边界、审计和受控访问；`platform-web` 不得直连 LangGraph upstream。

## Goals / Non-Goals

**Goals:**

- 让正式聊天页面使用一条 Protocol v2 调用链，并以 SDK 投影作为 live run 唯一事实源。
- 只使用 Agent Server `Auth`、Protocol v2 `config`、`Runtime.server_info.user` 和 `RunnableConfig` 等官方扩展点，不定义私有 v2 method/field。
- 将可信身份/项目与每次运行模型、工具、prompt 配置拆成两个明确契约，并在单一 resolver 内装配。
- 在网关保持认证、`x-project-id` 作用域、SSE 取消、事件重连/replay 和 protocol error 的可验证行为。
- 保持发送、取消、tool call、单/多 interrupt、checkpoint fork/edit/retry 与 debug 静态 interrupt 的用户行为。
- 保留 legacy `/runs/*` 面作为发布回退，不进行 thread 数据迁移。

**Non-Goals:**

- 不让正式页面直连 upstream，不引入前端 custom transport、第二套 adapter 或双协议页面分支。
- 不改变 graph 编排、tool/MCP 选择、权限模型、审计模型或 runtime 内部 prompt 策略。
- 不创建 per-user/per-project assistant 来承载动态 context，不把身份放入普通 configurable headers，不让 runtime-service 反向查询 platform-api 才能执行运行。
- 不在本 change 中删除 legacy 网关接口；其退役另行评估。

## Decisions

### Decision 1: Protocol v2 成为正式聊天运行时唯一协议

`platform-web` 只通过 SDK 标准 v2 transport 提交 command、订阅 events；页面不拼接 v2 URL、不解析 raw SSE frame，也不保留按 scope 选择 legacy/v2 的分支。`usePlatformChatStream` 是唯一 Vue 适配边界，直接暴露 SDK 的 `messages`、`values`、`toolCalls`、`interrupts`、`isLoading`、`error` 与 `threadId` 只读投影。

保留 legacy 路由仅用于发布回退或其他未迁移调用方，不能成为同一正式聊天页面的 fallback。

**Rejected alternative:** 前端 custom transport 翻译 v2 到 legacy 路由。它会制造第二套协议实现，且把项目治理、SSE 语义和升级负担留在浏览器。

### Decision 2: `platform-api` 作为 v2 protocol gateway

网关新增 thread-scoped command 与 event SSE 路由，并在每个 command/订阅建立前验证 actor、thread 可见性和 `x-project-id` 作用域。它只转发协议允许的 command envelope 和订阅过滤条件，保持 command `id`、成功/错误 envelope、event `seq` 与取消语义；浏览器断开时取消相应 upstream subscription。重连由客户端携带 `since`，网关不得伪造或重排序 event sequence。

**Rejected alternative:** 让前端持有 upstream URL/token。它绕过 control plane，违反正式入口与项目隔离标准。

### Decision 3: 静态 breakpoint 与正式聊天分离

`interruptBefore`、`interruptAfter` 是官方保留的 graph debug/test static breakpoint，但不推荐用于 Human-in-the-Loop；它们也不属于 Protocol v2 `run.start` 的标准参数。正式聊天不再暴露或传递这些字段，改用 graph 内 `interrupt()` 产生的动态 HITL interrupt，并由 SDK `interrupts`/`respond` 或 Protocol v2 `input.respond` 恢复。

静态 breakpoint 保留在独立开发调试工作台：该工作台明确标识为 debug、复用既有项目 runtime write 授权和 legacy run 面，并使用独立 debug thread/session。它不是正式聊天的协议 fallback，不得在同一聊天会话切换协议。`streamSubgraphs` 不是断点；正式聊天改用 Protocol v2 namespaces/subgraph projections，debug 工作台仅在 legacy stream 仍需要时使用它。

**Rejected alternative:** 前端把 legacy 参数塞入 v2 command，或在正式聊天里按失败自动回退 legacy。前者是私有协议，后者形成不可验证的双链路。

### Decision 4: Agent Server Auth 生成可信身份与项目上下文

`platform-api` 继续使用现有 `ActorContext`、project membership 和 runtime permission 完成控制面授权，并为每次 upstream command 签发短期、带 audience/expiry/request/project 绑定的 delegation credential。`runtime-service` 在 `langgraph.json` 配置 Agent Server `Auth`，只接受该 credential；认证结果中的 actor/project/role/permissions 通过 `runtime.server_info.user` 进入单一 runtime resolver。

正式 graph 不从 command `input`、`config`、`metadata` 或普通 forwarded headers 读取可信身份。thread/run 的 Agent Server auth handlers 同时按认证 project 约束资源访问，作为 platform-api 检查之后的服务端防线。

**Rejected alternatives:**

- 直接信任 `x-project-id` 等 configurable headers。官方文档明确要求只对可信内部来源启用；裸字段容易被转发或配置错误污染。
- 为每个用户或项目创建 assistant static context。它是静态版本配置，无法安全表达每次运行的 actor、权限和项目，且会造成 assistant 膨胀。
- 让 runtime-service 每次回调 platform-api 查询 actor/project。它增加同步耦合和故障面，delegation credential 已能携带最小可信声明。

### Decision 5: 每次运行配置使用标准 Protocol v2 config

原 `RuntimeContext` 拆为两个内部模型：

- 可信身份/项目上下文：只由 Agent Server 认证结果构造。
- `RuntimeOptions`：模型、temperature/max_tokens/top_p、工具开关与 allowlisted tool names、prompt 配置、多模态模型。

`platform-api` 在完成 project runtime policy 校验后，将 `RuntimeOptions` 写入标准 `run.start.params.config.configurable.platform_runtime`。该 namespace 禁止出现 user/project/role/permissions。`runtime-service` 的单一 resolver 从 `runtime.server_info.user` 与 `RunnableConfig` 读取两部分，执行 schema、allowlist 和交叉 project 校验后产生 `ResolvedRuntimeRequest`；现有 `RuntimeRequestMiddleware`、model/tool resolver 和业务工具只消费该解析结果。

这层 resolver 是唯一协议适配点。未来官方 Protocol v2 若增加调用级 `context`，只替换 resolver 的 transport extraction，不改 graph、middleware、tools 或前端协议。

**Rejected alternatives:**

- 将 legacy `context` 增加为私有 v2 字段。它会 fork 官方协议。
- 将运行配置放入 graph `input`。它会污染持久 state/checkpoint。
- 继续让 `project_id`、模型和 prompt 共用一个可由客户端提交的 `RuntimeContext`。它混淆信任边界并阻碍 v2。

### Decision 6: 持久 thread 与实时 state 分离

SDK 投影拥有 live messages、values、tool calls、interrupts、loading、error 与 active thread id；`platform-api` runtime service 继续拥有 thread 列表、详情和持久 checkpoint history。展示层只读合并二者，run finish/error 至多触发一次经 active-thread token 校验的持久刷新，不恢复 stream-history 双写。

## Risks / Trade-offs

- [静态 breakpoint 被误用为正式 HITL] → 正式聊天改用动态 `interrupt()`；静态断点只在独立 debug 工作台保留。
- [delegation credential 被重放或错绑项目] → 使用短期 expiry、audience、request/project 绑定，并在 Agent Server auth 与 thread resource auth 双重校验。
- [`platform_runtime` 被夹带身份或越权选项] → schema 禁止身份键，platform-api policy 与 runtime-service allowlist 双重校验，失败不 fallback。
- [认证结果与 LangGraph 版本暴露面变化] → 只在单一 resolver 读取 `runtime.server_info.user`/官方 auth config，并用 contract test 固定当前版本行为。
- [SSE 代理破坏取消、重连或事件顺序] → route/adapter 测试覆盖 abort、`since` replay 与单调 `seq`；最短链进行真实订阅验证。
- [SDK major 升级产生 hydration 或事件顺序回归] → 依赖升级仅在 v2 网关契约通过后进行，并保留 characterization tests。
- [旧 thread payload 不符合新版消息投影] → 兼容只留在持久 snapshot normalization 边界，且必须有 fixture。
- [发布失败] → 关闭 v2 正式入口并让页面回退到已验证 legacy release；不修改数据，因此无需数据回滚。

## Migration Plan

1. 恢复试装依赖产生的 lockfile 差异，并以当前 legacy 测试作为基线。
2. 先修改 runtime-service current standard 与 harness，启用 Agent Server `Auth`，实现可信身份/项目上下文和类型化 `RuntimeOptions` 的单一 resolver。
3. 在 `platform-api` 增加 delegation credential、v2 config normalization、command/event gateway 及授权/项目作用域测试。
4. 以最短真实链验证 credential、project isolation、command、SSE、动态 HITL interrupt、cancel、reconnect/replay、fork 与 namespaces/subgraphs。
5. 升级 `@langchain/vue` 及配套依赖，移除前端 live state 双写并切换正式聊天页面到 v2。
6. 独立实现 legacy debug 工作台的静态 breakpoint 入口和会话隔离。
7. 完成受控发布与桌面/移动人工验收；异常时分别回退正式聊天 release 或关闭 debug 工作台入口。

## Open Questions

- delegation credential 的具体 JWT 实现优先复用仓库现有安全组件；若无可复用实现，实施前选择最小的成熟签名/验证依赖，不自定义密码学格式。
- legacy `/runs/*` 的最终退役窗口与其他调用方迁移范围不属于本 change。
