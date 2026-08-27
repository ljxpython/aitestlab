# Durable Run 架构与 AI 交互迁移

状态：Draft supporting material。正式 requirement 以 OpenSpec delta spec 为准。

## 1. 迁移目标

采用 `research/open-swe/docs/agent-engineering-learning/12-migration-phase-2-durable-run-and-stream-zh.md`
的核心原则：

```text
Run 是持久任务
SSE 是观察与恢复通道
Thread / Run snapshot 是事实源
正式前端是受控观察者
runtime-web 是内部调试壳
```

新 Agent Web 不调用浏览器连接绑定的 `runs.stream`。它创建 durable Run，随后订阅该
Run 的事件，网络中断后恢复观察而不重复执行。

## 2. 当前实现与目标差异

当前 `platform-api` 已拥有 project scope、role 校验、delegation credential、Run 查询/取消
基础，以及 Protocol v2 command/event 代理。它仍保留：

- `POST /api/langgraph/threads/{thread_id}/runs/stream`：创建并隐式流式返回；
- `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/stream`：join stream，使用 query
  参数传 `last_event_id`；
- Protocol v2 command/event 入口：已暴露在 gateway，当前前端尚未接入。

目标不在 Agent Web 内同时兼容这些状态机。Durable Run 是正式执行模型，Protocol v2 是它的
正式远程命令和事件协议；legacy 创建即流式入口不属于 Agent Web。`runtime-web` 可继续以现有
受控路径调试，但不得成为 Agent Web fallback。

## 3. 目标 API

路径以 `platform-api` gateway 前缀为准；下表只定义目标语义。

| 操作 | 接口 | 语义 |
| --- | --- | --- |
| 创建/恢复 | `POST /threads/{thread_id}/commands` | `run.start` 或 `input.respond` 创建/恢复后台 Durable Run，并返回 Protocol v2 envelope |
| 查询 | `GET /threads/{thread_id}/runs/{run_id}` | 返回运行状态、安全摘要和持久 Run snapshot |
| 订阅/恢复 | `POST /threads/{thread_id}/stream/events` | 以 channel/namespace filter 和 `since` 返回 SSE；先重放缺失事件再实时订阅 |
| 取消 | `POST /threads/{thread_id}/runs/{run_id}/cancel` | 请求取消；终态由后续 snapshot 确认 |
| 继续 | `POST /threads/{thread_id}/commands` | `input.respond` 处理已授权的 interrupt/approval，只恢复目标 Run |

### 创建请求

```json
{
  "id": 1,
  "method": "run.start",
  "params": {
    "assistant_id": "research_agent_v1",
    "input": {"messages": [{"role": "user", "content": "..."}]}
  }
}
```

浏览器不得提交或覆盖 `project_id`、用户身份、role、permissions、模型白名单、工具策略和
可信 RuntimeContext。`platform-api` 在认证与 project authorization 后冻结这些值，再调用
runtime。

### 命令与幂等规则

- `id` 是客户端命令关联号，响应必须回显；它不是浏览器重试的幂等依据。
- 浏览器每次创建意图生成 `Idempotency-Key` HTTP header；`platform-api` 按
  `(project_id, thread_id, idempotency_key)` 持久化规范化请求摘要。该 header 绝不进入
  Protocol v2 command 或 runtime config。
- 相同 key 与相同摘要返回同一 `run_id`；相同 key 与不同摘要返回
  `409 idempotency_key_conflict`。
- gateway 必须先验证 actor、project、thread 与受控 runtime config，再向 Agent Server 发送
  `run.start` 或 `input.respond`。
- PoC 必须证明 `run.start` success result 可稳定取得 `run_id`。未取得 `run_id` 时不得以
  “查询 thread 最新 Run”猜测替代，必须阻止后续实施并调整正式契约。
- 创建超时或页面恢复时，客户端仅按已知 `run_id` 查询 snapshot；不得盲目重发 `run.start`。

## 4. 责任划分

```text
Agent Web
  - 生成 idempotency key、渲染 snapshot 与事件、保存已确认 event id
  - 不决定权限、项目、模型、工具或 Run 终态

platform-api / Runtime Protocol Coordinator
  - 认证、project/thread authorization、幂等映射、运行策略冻结
  - 代理 Protocol v2 command、Run 查询/取消和 POST SSE，审计受治理动作
  - 将每个 Durable Run 一对一映射为 project operation；Run 负责 AI 执行事实，operation
    负责平台治理、审计与生命周期查询

runtime-service / LangGraph
  - graph 执行、checkpoint、durability="sync"、stream_resumable=True
  - 返回真实运行状态与可恢复事件

runtime-web
  - 内部直接调试；不改变生产 Agent Web 的鉴权或协议
```

Coordinator 落在 `apps/platform-api/app/modules/runtime_gateway/` 的 application 层，
而不是 React 应用或路由 handler 中。需要持久化的幂等映射和安全摘要由 control plane
拥有；graph 编排、prompt 与 tool 选择仍由 runtime-service 拥有。

## 5. Run 状态模型

```text
queued -> running -> waiting_for_input -> running -> succeeded
                  |                  \-> cancelled
                  \-> failed
queued -> cancelled
```

- `queued`、`running`、`waiting_for_input` 是非终态。
- `succeeded`、`failed`、`cancelled` 是终态；服务端 snapshot 是最终依据。
- 一个 thread 同时至多有一个 active Run；新的 `run.start` 在已有非终态 Run 时返回确定冲突，
  不能用线程级事件流猜测归属。
- 浏览器连接关闭、SSE 代理错误和页面刷新都不改变 Run 状态。
- `input.respond` 只允许恢复服务端声明的 interrupt ID。gateway 必须证明该 interrupt 属于当前
  active Run；多 interrupt 情况下不得依赖“当前 thread”或前端索引猜测目标。

## 6. React 端状态与传输

### 状态边界

| 状态 | 所属位置 | 规则 |
| --- | --- | --- |
| project/thread/run snapshot | TanStack Query | 只从 platform-api 更新 |
| 活跃订阅与最后 event id | `RunEventsController` | 一个 active Run 一条订阅 |
| UI 展示投影 | `useRunTimeline` | 纯派生，按 event id 去重 |
| composer 草稿/panel 开合 | 组件/局部 store | 不写回 Run snapshot |
| optimistic human message | 当前 idempotency key 关联的局部 projection | 收到同一 Run 事实后合并或回滚 |

### 生命周期

```text
submit
  -> POST command (run.start)
  -> cache returned run_id / refetch Run snapshot
  -> POST events with saved seq as since
  -> apply ordered events
  -> terminal event: refetch Run + thread snapshot

disconnect / page restore
  -> GET Run
  -> non-terminal: POST events with last seq as since
  -> terminal: refresh durable snapshot
```

事件应用必须满足：同一 `event_id` 幂等、只接受当前 `project/thread/run`、乱序事件不倒退
状态、SSE 末帧不直接标记成功。

gateway 保持 Protocol v2 的 event type、payload 语义与 `seq` 顺序；只允许在明确的敏感字段
允许列表/拒绝列表下进行脱敏，不能重命名、合成或重排事件。`RunEventsController` 集中解析
标准 Protocol 帧，UI 组件不解析 raw SSE，审计和客户端诊断均不得记录 token、Authorization
header 或完整输入消息。

### 已确认的鉴权与传输

原生 `EventSource` 不能附加现有 Bearer `Authorization` header。当前平台又使用 token 刷新
逻辑，因此 Agent Web 固定使用带授权 header 的 `fetch` ReadableStream 订阅 POST SSE：

- 单一 transport 模块解析 SSE framing、保存最后确认的 Protocol `seq`、处理 token refresh
  和重连；业务组件永不解析 raw SSE。
- 重连使用 POST body 的 `since`，不能使用 EventSource 的 `Last-Event-ID` 自动重连。
- Bearer token 不得放入 URL。受控 HttpOnly cookie/EventSource 不是本变更的备选实现。

不得把 bearer token 写进 URL query，也不得因为 EventSource 不支持 header 而绕过
`platform-api`。

## 7. 事件与 snapshot 顺序

运行完成的服务端顺序固定为：

```text
graph / business state 完成
  -> 同步 checkpoint
  -> 写 durable Run terminal state
  -> 发布 completed / failed event
  -> 发送可重试 completion webhook
```

webhook 失败只能影响通知重试，不能把成功 Run 改为失败。若 runtime 无法回放事件，客户端
先读 Run snapshot 与 thread checkpoint，再显示“部分实时事件不可恢复”的受控提示，绝不
重新创建 Run。

## 8. Protocol v2 与 Durable Run 的层次关系

Durable Run 定义执行持久化、snapshot 与恢复语义；Protocol v2 定义浏览器的命令和事件格式。
官方 Protocol v2 的 `run.start`/`input.respond` 在后台创建或恢复 Run，而事件流只做并发观察。
因此它们不是竞争入口：新 Agent Web 用 Protocol v2 操作和观察 Durable Run。

这是 **BREAKING governed change**，owner review 必须明确批准：

- Agent Web 是否成为唯一新的正式 chat surface；
- legacy `/runs/stream` 的退役窗口和旧 `platform-web` 回退策略；
- Run snapshot/cancel 资源与 Protocol v2 command/event 的边界；
- 幂等、SSE event format、audit 与数据保留规则。

在此批准之前，不得改 API、切流生产用户或删除 legacy 路径。

## 9. LangGraph 升级策略

`langgraph==1.2.11` 已包含稳定的 v2 unified stream output 与 beta 的 v3 event streaming。
升级实施按层推进，不能将 Python 本地 API 的 v3 直接暴露为浏览器协议：

1. 先在隔离 PostgreSQL 数据库、Redis namespace 和固定镜像 digest 上升级 Agent Server、CLI、SDK
   与约束依赖，验证 graph 注册、custom routes、lifespan、platform auth 和 checkpoint。
2. 将本地 `graph.astream()` 消费者从 `(mode, event)` 元组收敛到 `version="v2"` 的
   `type`/`ns`/`data`，每类消息、工具、更新和子图至少有一个断言。
3. v3 `stream_events` 仅作为 runtime 内部的类型化投影 PoC，验证 messages、values、subgraphs
   和 interrupts；在其稳定且契约明确前，不作为平台 HTTP 或浏览器公共协议。
4. 新 Agent Web 的远程链路仍以 Agent Server Protocol v2 为准；用真实 SSE 验证
   `run.start -> events -> input.respond -> since replay` 的全链路。

### PoC 硬退出条件

隔离 PoC 未全部通过前，不创建 React 业务页面、不改生产配置、不切换任何用户：

1. 固定并记录 Agent Server 镜像 digest、CLI、SDK、Python 包和锁文件的兼容组合。
2. `run.start` 返回可解析的 `run_id`；重复 `Idempotency-Key` 只创建一个上游 Run。
3. 同一 thread 的第二个 active Run 被拒绝；事件可按 `run_id` 关联，不能串写时间线。
4. 多 interrupt 时，`input.respond` 仅恢复带匹配 interrupt ID 的目标 Run。
5. POST SSE 的 `since` 先重放较高 `seq` 再进入实时流；断线不改变 Run 状态。
6. `platform_auth`、custom routes、全部 graph、PostgreSQL checkpoint 和 Redis 在隔离环境通过，
   且 operation/audit 生命周期完整、无凭证或完整消息泄漏。
7. 必须完成真实全链路 E2E：真实部署的 `agent-web -> platform-api -> runtime-service -> Agent
   Server -> 隔离 PostgreSQL/Redis`，使用真实 delegation credential、真实 HTTP Bearer SSE 与
   实际 graph；禁止以 mock upstream、内存替身或单模块测试替代该证据。测试 project、账号、
   数据库和 Redis namespace 必须隔离于生产。

## 10. LangGraph 技术裁决优先级

本设计的 LangGraph 技术事实必须同时遵循下列两份已指定资料：

1. `apps/runtime-service/runtime_service/docs/knowledge/09-langgraph-runtime-upgrade-and-event-migration.md`
   定义本仓库接入官方 Agent Server、Protocol v2、`version="v2"` 本地 StreamPart、隔离升级
   与平台边界的做法。
2. `/Users/lijiaxin/PyCharmMiscProject/research/open-swe/docs/agent-engineering-learning/12-migration-phase-2-durable-run-and-stream-zh.md`
   定义应吸收的 Durable Run 生命周期原则：Coordinator 唯一创建、同步 durability、可恢复流、
   checkpoint 先于终态、终态先于通知，以及浏览器仅为授权观察者。

两份资料出现字面实现差异时，不得同时保留两套生产协议，也不得凭旧 Vue 或旧 SDK 行为回退。
以本项目的官方 Agent Server 适配结论为协议裁决：生产远程命令使用 Protocol v2
`run.start` / `input.respond`，事件使用 `POST /threads/{thread_id}/stream/events`，断线恢复在
body 传递 `since`。Open SWE 的 `POST /runs`、GET SSE、`Last-Event-ID` 与请求体
`idempotency_key` 是其网关形态，不迁入本项目。

Open SWE 仍是生命周期语义的强制参考，但本项目保持既定安全边界：幂等使用 gateway HTTP
`Idempotency-Key`，浏览器不得自由决定 project、身份、RuntimeContext、RuntimeOptions 或
Agent Server URL。当前官方 LangChain 文档是版本事实的复核来源；若它与两份资料或固定镜像
组合不一致，必须停止升级，记录差异并由 owner 决定，不得擅自引入第二条兼容路径。
