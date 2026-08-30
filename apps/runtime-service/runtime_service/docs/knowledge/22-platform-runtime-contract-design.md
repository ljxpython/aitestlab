# Platform API / Runtime Service 控制面与执行面契约设计（Draft）

> 文档类型：Draft
>
> 状态：讨论结论，暂不替代 `docs/standards/` 下的现行规范
>
> 关联文档：`10-production-agent-platform-roadmap.md`、
> `12-runtime-context-and-local-debug-architecture.md`、
> `14-runtime-contracts-and-resolution-design.md`、
> `15-runtime-middleware-lifecycle-and-failure-semantics.md`、
> `17-platform-observability-query-and-admin-console-design.md`、
> `18-open-swe-to-runtime-event-and-run-explorer-design.md`
>
> 冻结范围：Platform API 与 Runtime Service 的职责边界、JSON 命令、错误信封、事件顺序、
> 幂等键和权限边界
>
> 明确不包含：Agent Release、灰度发布、自动回滚、跨版本 Run Snapshot、事件消息队列和
> 通用 RPC SDK

## 1. 本轮结论

平台与 Runtime 只保留一条清晰的最短链路：

```text
Platform API
  -> 鉴权、项目权限、幂等、Run 记录、审计、协议适配
  -> Runtime Service
       -> Graph、Model、Tool、MCP、Checkpoint、Interrupt、Resume、Stream
```

不在 Runtime 中建设 Agent Release、版本 Registry、灰度选择器或万能调度器。部署版本由
部署系统管理，Runtime 只消费当前部署的 Graph，并在 Trace/Event metadata 中记录
`deployment_revision`。

首期不再发明第三套 Agent RPC。Platform API 到 Runtime Service 的执行请求沿用现有
LangGraph Protocol v2，由 Platform Gateway 做可信字段注入、权限检查、错误整形和事件投影。

## 2. Open SWE 借鉴边界

### 2.1 必须借鉴

Open SWE 的 `agent/server.py` 和 `agent/dispatch.py` 给出了几个简单而有效的边界：

1. `get_agent(config)` 是组合根，负责模型、工具、Middleware、Backend 和 Subagent 装配；
2. `create_durable_run(...)` 集中设置 `durability="sync"`、`stream_resumable=True` 和
   `multitask_strategy="interrupt"`，入口不会各自发明运行语义；
3. Thread、Run、Checkpoint 和 Stream 分工明确：Thread 保存长期上下文，Run 表示一次执行，
   Checkpoint 用于恢复，Stream 只负责实时展示；
4. 命令与事件流分离，浏览器断线不等于 Run 停止；
5. `assistant_id` 选择 Graph，`metadata` 只用于关联和来源记录，不承载权限真相；
6. SSE 建立前先完成鉴权和参数校验，避免流开始后才返回 HTTP 错误。

### 2.2 不照搬

- Slack、Linear、GitHub、Sandbox 和 PR 业务状态不进入公共契约；
- Open SWE 的 Dashboard metadata 不作为平台 Run 事实源；
- 不把 LangSmith/Langfuse Trace 当成 Run 状态或权限来源；
- 不复制 Open SWE 的大型 dashboard proxy 和集成工具清单；
- 不因为需要动态模型或 Prompt 就每次重建 Graph。

Open SWE 的学习文档中出现的版本快照、迁移和平台控制面属于分析方案，不代表 Open SWE
当前源码已经实现；本项目当前也不建设这些能力。

## 3. 责任边界

### 3.1 Platform API（控制面）

负责：

- 用户、tenant、project 认证和权限；
- Assistant/Graph 是否属于当前项目；
- Thread、Run 和 Operation 的平台记录；
- `Idempotency-Key` 去重和请求摘要 hash；
- 运行生命周期事件和审计；
- 将平台请求转换成 Runtime 可接受的 Protocol v2；
- 对 Runtime 错误进行脱敏和 HTTP 映射。

不负责：

- Graph 编排和模型调用；
- Tool、MCP、Backend 或 Subagent 实现；
- LangGraph checkpoint 内部结构；
- 根据 Langfuse 结果改变 Run 状态。

### 3.2 Runtime Service（执行面）

负责：

- Delegation Token 验证和 tenant/project scope 校验；
- 根据 `langgraph.json` 找到 Graph；
- `RuntimeContext`、Model、Tool、MCP 和 Middleware 校验；
- Graph 执行、Checkpoint、Interrupt、Resume 和 Stream；
- Tool 执行前的 capability 复核；
- 返回稳定的 Runtime 错误码和安全错误摘要。

不负责：

- 用户是否属于项目；
- 灰度或 active Agent 选择；
- Platform 数据库写入；
- 通过客户端字段改变权限、Graph 或工具实现。

## 4. 传输和认证

Platform API 调用 Runtime Service 使用短期服务间 Delegation Token：

```http
Authorization: Bearer <runtime-delegation-token>
X-Request-ID: req-123
X-Protocol-Version: 2
Idempotency-Key: idem-123
```

Token 的最小 claims：

```json
{
  "sub": "user-123",
  "tenant_id": "tenant-123",
  "project_id": "project-123",
  "role": "member",
  "permissions": [
    "project.runtime.read",
    "project.runtime.write"
  ],
  "aud": "runtime-service",
  "exp": 1788080000,
  "jti": "token-123"
}
```

Runtime 必须校验签名、issuer、audience、过期时间、`jti` 和 project scope。Runtime 不访问
Platform 数据库，也不根据 token 以外的客户端字段补全权限。

## 5. JSON 命令契约

### 5.1 通用命令信封

命令接口继续使用 Protocol v2：

```json
{
  "id": 1,
  "method": "run.start",
  "params": {}
}
```

`id` 只用于协议响应关联，不承担业务幂等语义。幂等使用 HTTP `Idempotency-Key`。

### 5.2 `run.start`

```json
{
  "id": 1,
  "method": "run.start",
  "params": {
    "assistant_id": "research_agent",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": "请分析这个项目"
        }
      ]
    },
    "context": {
      "model_id": "default-model",
      "temperature": 0.2,
      "tools": ["read_project"]
    },
    "config": {
      "configurable": {
        "thread_id": "thread-123"
      }
    },
    "metadata": {
      "request_id": "req-123"
    },
    "durability": "sync",
    "stream_resumable": true,
    "on_disconnect": "continue"
  }
}
```

字段规则：

| 字段 | 责任 | 规则 |
|---|---|---|
| `assistant_id` | Platform 选择、Runtime 校验 | 只能是已部署 Graph 的稳定标识 |
| `input` | 业务输入 | Service 自己定义 schema，不放身份和权限 |
| `context` | RuntimeContext 候选值 | 不可信，严格校验并受 RuntimePolicy 收缩 |
| `config` | LangGraph 执行控制 | 只放 thread、checkpoint、tags、callbacks 等 |
| `metadata` | 关联信息 | 只能放 request/source 等低敏字段 |
| `durability` | Runtime 执行语义 | 默认 `sync` |
| `stream_resumable` | Stream 恢复 | 默认 `true` |
| `on_disconnect` | 断线行为 | `continue` 或 `cancel` |

`context.tools` 使用三态语义：字段缺省或值为 `null` 时继承 Assistant/Service 的 Optional
Tools；空数组表示本次禁用全部 Optional Tools；非空数组表示整体替换为指定工具。新契约不再
使用重复表达相同含义的 `enable_tools` 字段。

`tenant_id`、`project_id`、`user_id`、`role`、`permissions`、凭据、Tool 实现、Prompt 模板和
Graph 路径禁止由客户端提交。Platform API 负责从可信上下文或 Delegation Token 注入。

当前 `runtime_contract.py` 的 Protocol v2 校验尚未把 `context` 的位置写死。实施时必须在
单一适配层明确 `params.context -> RuntimeContext` 的映射；如果锁定版本的 LangGraph SDK
不接受该字段，由适配层转换，不能让每个 Agent 自己解析一遍。

### 5.3 `input.respond`

恢复 HITL 或 Interrupt 使用现有 Protocol v2 命令：

```json
{
  "id": 2,
  "method": "input.respond",
  "params": {
    "interrupt_id": "interrupt-123",
    "response": {
      "approved": true
    }
  }
}
```

Platform API 必须确认 `interrupt_id` 属于当前 project 的 active Run，Runtime 再根据
checkpoint 验证它是否仍可恢复。恢复不能改变原始 Graph 或业务输入。

### 5.4 取消

取消继续使用 Runtime 的 Run cancel 接口，不把取消实现成 Agent Tool：

```json
{
  "run_ids": ["run-123"],
  "action": "cancel"
}
```

Platform API 先写 `run.cancel_requested`，Runtime 接受后再写 `run.cancelled`。重复取消返回
当前状态，不重复执行副作用。

### 5.5 Durable Run 默认值

Open SWE 的 `agent/dispatch.py` 没有实现 Agent 工厂，而是把所有入口创建 Durable Run 时
都需要的运行参数集中到 `create_durable_run()`：

```python
await client.runs.create(
    thread_id,
    assistant_id,
    input=input,
    config=config,
    metadata=metadata,
    durability="sync",
    stream_resumable=True,
    multitask_strategy="interrupt",
    stream_subgraphs=True,
)
```

可借鉴的含义：

- `durability="sync"`：每个图步骤继续前同步保存 checkpoint，适合长任务和可恢复执行；
- `stream_resumable=True`：保留 Stream 数据，断线后可以按游标补发；
- `multitask_strategy="interrupt"`：交互式 Thread 的新输入中断当前 Run，并从 checkpoint
  继续；
- `stream_subgraphs=True`：Deep Agent 的 Subagent/子图事件进入事件流；
- `if_not_exists="reject"`：Thread 必须先由 Platform 创建，避免错误 ID 产生孤立 Thread；
- `on_disconnect="continue"`：SSE 断开不代表 Run 取消，取消必须显式调用 cancel。

这些是 Run 传输语义，不属于 `get_agent()` 的 Graph 组装职责。我们的项目不把
`dispatch.py` 原样复制到每个 Service，而是在 Platform API Runtime Gateway 放一个薄的
参数规范化函数，所有入口复用它：

```python
def apply_run_defaults(params: dict, *, mode: str) -> dict:
    params = dict(params)
    params.setdefault("durability", "sync")
    params.setdefault("stream_resumable", True)
    params.setdefault("if_not_exists", "reject")
    params.setdefault("on_disconnect", "continue")
    params.setdefault(
        "multitask_strategy",
        "interrupt" if mode == "interactive" else "enqueue",
    )
    if mode == "deep_agent":
        params.setdefault("stream_subgraphs", True)
    return params
```

默认策略：

| 场景 | `durability` | `stream_resumable` | `multitask_strategy` | `stream_subgraphs` |
|---|---|---|---|---|
| 交互式普通 Agent | `sync` | `true` | `interrupt` | `false` |
| Deep Agent | `sync` | `true` | `interrupt` | `true` |
| 后台任务 | `sync` | `true` | `enqueue` 或 `reject` | 按服务需要 |

当前 `runtime_contract.py` 已处理 `durability`、`stream_resumable` 和 `on_disconnect`，但
`multitask_strategy`、`if_not_exists`、`stream_mode`、`stream_subgraphs` 尚未全部纳入
Protocol v2 规范。实施时必须在唯一的 Platform Gateway 适配层补齐白名单和默认值，不能让
各 Agent 自己解析。Open SWE 使用的 `__event_streaming_v2` 属于内部实现细节，不直接复制；
只采用公开的 Run 参数和 SSE replay 能力。

## 6. 响应和错误契约

### 6.1 成功响应

```json
{
  "type": "success",
  "id": 1,
  "result": {
    "run_id": "run-123"
  }
}
```

### 6.2 统一错误信封

```json
{
  "error": {
    "code": "runtime.context_invalid",
    "message": "Runtime context contains an unsupported field",
    "retryable": false,
    "request_id": "req-123",
    "details": {}
  }
}
```

错误消息禁止包含堆栈、Token、API Key、完整 Prompt、完整 Tool 参数、数据库连接信息和
内部绝对路径。

### 6.3 HTTP 映射

| HTTP | Platform 错误码 | 语义 |
|---:|---|---|
| 400 | `platform.invalid_request` | JSON 或业务参数错误 |
| 401 | `platform.unauthenticated` | 用户或 Delegation Token 无效 |
| 403 | `platform.permission_denied` | 无项目运行权限 |
| 404 | `platform.project_not_found` / `platform.thread_not_found` | 资源不存在或不可见 |
| 409 | `platform.idempotency_conflict` / `platform.run_conflict` | 幂等或状态冲突 |
| 429 | `platform.rate_limited` | 频率或并发受限 |
| 502 | `platform.runtime_bad_response` | Runtime 返回非法响应 |
| 503 | `platform.runtime_unavailable` | Runtime 暂不可用 |
| 504 | `platform.runtime_timeout` | Runtime 超时 |

Runtime 内部错误码使用 `runtime.*` 前缀，例如：

```text
runtime.auth_invalid
runtime.scope_mismatch
runtime.graph_not_found
runtime.context_invalid
runtime.model_not_allowed
runtime.tool_not_allowed
runtime.tool_failed
runtime.model_timeout
runtime.run_not_found
runtime.run_not_resumable
runtime.internal_error
```

Platform 可以映射错误前缀，但在 `details.upstream_code` 中保留原始 Runtime code。SSE 已经
开始后不能再改变 HTTP status；此时发送一个脱敏的 `error` 事件并关闭流。

## 7. 事件顺序和事实源

### 7.1 生命周期顺序

```text
run.submitted
  -> run.started
  -> run.interrupted
  -> run.resumed
  -> run.completed | run.failed

run.submitted | run.started | run.interrupted
  -> run.cancel_requested
  -> run.cancelled
```

约束：

- `run.submitted` 由 Platform API 在创建 Durable Run 时事务化写入；
- `run.started` 只有在 Runtime 返回有效 `run_id` 后写入；
- `run.interrupted` 和 `run.resumed` 必须关联对应的 `interrupt_id`；
- `run.completed`、`run.failed`、`run.cancelled` 是终态；
- 终态之后不再写新的生命周期事件；
- 重复终态请求按幂等成功处理，冲突状态转换返回 409；
- Token、模型增量和完整 Tool 参数不进入平台产品事件表。

### 7.2 事件信封

```json
{
  "event_id": "event-123",
  "event_version": 1,
  "run_id": "run-123",
  "thread_id": "thread-123",
  "sequence": 4,
  "event_type": "run.completed",
  "occurred_at": "2026-08-30T10:00:00Z",
  "source": "platform",
  "status": "succeeded",
  "safe_metadata": {},
  "correlation": {
    "request_id": "req-123",
    "operation_id": "operation-123",
    "platform_trace_id": "trace-123",
    "deployment_revision": "runtime@sha256:abc"
  }
}
```

规则：

- `event_id` 全局唯一；
- `sequence` 只在一个 `run_id` 内单调递增，从 1 开始；
- `event_version` 只允许新契约增加字段，不为旧客户端保留兼容语义；
- `source` 仅允许 `platform`、`runtime`、`worker`；
- `status` 使用 `submitted`、`running`、`waiting`、`cancel_requested`、`succeeded`、
  `failed`、`cancelled`、`unknown`；
- `safe_metadata` 使用白名单和大小上限；
- `correlation` 只用于查询关联，不能参与鉴权或 Runtime 配置决议。

Platform 的 `sequence` 与 LangGraph 上游 `seq` 分离。上游 `seq` 只用于继续读取上游流，
Platform `sequence` 才是 Run Explorer 的历史游标。

### 7.3 事件来源

首期不增加 Runtime 到 Platform 的独立消息队列或回调协议：

1. Platform API 生成 `submitted`、`started`、取消和终态生命周期事件；
2. Gateway 代理 Runtime SSE，并将需要展示的 Interrupt/Tool 副作用摘要投影成平台事件；
3. 异步 Run 的最终状态由 Gateway 的 wait/reconcile 读取 Runtime 状态确认；
4. SSE 只负责实时展示，事件表负责历史查询，Checkpoint 负责恢复。

等异步任务规模证明 HTTP/SSE 不够，再增加事件投递通道，不能提前建 Event Bus。

## 8. 幂等键

`id` 和 `Idempotency-Key` 明确分工：

```text
id                  Protocol 命令响应关联
Idempotency-Key     业务操作去重
```

### 8.1 `run.start`

必须提供 `Idempotency-Key`，幂等范围为：

```text
tenant_id + project_id + thread_id + operation + idempotency_key
```

Platform 保存请求规范化后的 body hash：

- 相同 Key、相同 hash：返回第一次创建的 `run_id`；
- 相同 Key、不同 hash：返回 `409 platform.idempotency_conflict`；
- 原请求仍在 reconcile：返回 `409 platform.run_start_in_progress`。

### 8.2 `input.respond`

必须提供幂等键，范围为：

```text
run_id + interrupt_id + idempotency_key
```

重复提交相同响应返回第一次结果，不得重复恢复 Graph 或重复触发工具。

### 8.3 `cancel`

建议提供幂等键。重复取消直接返回当前 Run 状态；已经进入终态时不再向 Runtime 发起新的
取消请求。

### 8.4 查询

GET、事件历史查询和 SSE 重连不需要幂等键。SSE 重连通过 `after_sequence` 或
`Last-Event-ID` 补发，前端按 `event_id` 去重。

## 9. 权限边界

### 9.1 Platform 权限

Platform API 负责：

- `project.runtime.read`：读取 Graph、Thread、Run、事件和安全摘要；
- `project.runtime.write`：创建 Run、恢复 Interrupt、取消 Run；
- project/tenant 范围校验；
- Assistant/Graph 归属校验；
- Admin 跨项目查询和审计权限。

项目 API 从已验证的 project context 派生 `project_id`。body、query 或 metadata 中的同名
字段只能被拒绝或忽略。

### 9.2 Runtime 权限

Runtime Service 负责：

- 验证 Delegation Token；
- 校验 tenant/project scope；
- 校验 Graph 是否已部署；
- 校验 RuntimeContext 是否合法；
- 校验 Model allowlist；
- Tool/MCP 执行前复核权限和副作用策略；
- 拒绝直接来自浏览器或未签名服务的请求。

权限链路固定为：

```text
Platform 用户权限
  -> Platform API 校验
  -> 签发受限 Delegation Token
  -> Runtime scope 校验
  -> Tool 执行前再次复核
```

Platform 的项目权限检查不能替代 Runtime 的 Tool 检查；Runtime 的 Tool 检查也不能替代
Platform 的项目访问控制。

## 10. 最小运行时序

```text
1. Platform 校验 actor/project/thread/assistant
2. Platform 校验 RuntimeOptions 和 Idempotency-Key
3. Platform 写入 run.submitted 和 Durable Run 记录
4. Platform 签发 Delegation Token，调用 Runtime run.start
5. Runtime 验证 token、context、Graph、model、tools
6. Runtime 返回 run_id
7. Platform 写入 run.started
8. Platform 代理 SSE；Runtime 写 checkpoint
9. Interrupt 时写 run.interrupted，input.respond 后写 run.resumed
10. Runtime 进入终态，Platform reconcile 并写 completed/failed/cancelled
```

伪代码：

```python
async def start_run(request, actor):
    project = authorize_project(actor, request.project_id, write=True)
    command = normalize_start_command(request.payload)
    key = require_idempotency_key(request.headers)

    existing = runs.find_by_idempotency(project.id, request.thread_id, key)
    if existing:
        ensure_same_request(existing.request_hash, hash_command(command))
        return existing.run_id

    durable = runs.reserve(project=project, thread_id=request.thread_id, key=key)
    platform_context = build_trusted_context(actor, project, request)
    token = sign_runtime_token(actor, project)
    result = await runtime.send(
        command=inject_context(command, platform_context),
        authorization=token,
    )
    run_id = require_run_id(result)
    runs.mark_started(durable.id, run_id)
    return run_id
```

## 11. 首期不建设的内容

- Agent Release、Prompt/Tool/Graph 独立版本表；
- 灰度百分比和自动发布控制器；
- 自定义 Run Snapshot 公共类型；
- Runtime 到 Platform 的 Kafka/Event Bus；
- 跨版本 Thread 自动迁移或旧 Thread 兼容；
- 统一 Tool Registry、Backend Registry 或通用 Builder；
- 暴露 Langfuse、Prometheus、Loki 凭据给前端。

## 12. 实施前的最小验证

实施阶段至少验证：

1. 相同 `Idempotency-Key` 不会创建两个 Run；
2. 相同 Key 不同请求体返回 409；
3. 客户端不能伪造 project、permissions 或 Graph 路径；
4. Runtime 能拒绝错误 audience、过期或跨项目 Token；
5. `submitted -> started -> terminal` 顺序稳定且终态不重复；
6. Interrupt/resume 使用同一个 Thread 和 checkpoint；
7. SSE 断线按 Platform sequence 补发且不重复；
8. Runtime 错误经过 Platform 脱敏后仍保留可查询的 upstream code；
9. Durable Run 默认值由 Gateway 统一注入，入口之间不产生行为差异；
10. Langfuse、日志等外部观测源不可用时，Run 核心状态仍可查询。

本轮只固化契约和规划，不创建新 Schema、不改 Runtime 源码、不调用 OpenSpec。具体
Schema、错误类和测试任务在进入实施阶段后再拆分；实施时不迁移旧数据或兼容旧契约。
