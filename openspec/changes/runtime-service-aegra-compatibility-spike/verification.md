# Verification

- 状态：Owner approved，进入 apply
- Change：`runtime-service-aegra-compatibility-spike`
- Locus：`apps/runtime-service`
- 最短验证链：Runtime Agent -> Aegra Server -> PostgreSQL/Redis/Langfuse
- 执行分级：B3 Governed

## Pre-apply Review

- Owner decision：Approved
- Reviewer：项目负责人（用户确认）
- Review date：2026-08-30
- Scope waiver：无

## Planned Checks

- `get_agent(config)` per-Run factory 兼容性
- 真实 DeepSeek/豆包多模态模型调用
- PostgreSQL Checkpoint、Redis Worker、Lease Recovery、Graceful Shutdown
- SSE Replay、HITL interrupt/resume、Cancel、终态幂等
- DeepAgent Workspace/Backend/Subagent 隔离
- RuntimeContext 签名、权限和 server-authoritative 字段
- Langfuse correlation 与 exporter 故障隔离

## Evidence

### 2026-08-31：本地 uv 启动与基础协议

- 前提：`~/.my_best/.env` 存在，Docker Desktop 可用，PostgreSQL/Redis 端口未冲突。
- 命令：`apps/runtime-service/spikes/aegra/scripts/up.sh`。
- 结果：`pass`。Compose 仅启动 `aegra-postgres-1` 和 `aegra-redis-1`；Aegra `0.10.4`
  由 Spike 的 `uv` 环境启动，健康检查返回 PostgreSQL、LangGraph Checkpoint/Store
  均为 `connected`。
- 图加载：`reference_agent`、`workflow_demo`、`backend_demo`、`deep_agent_demo`、
  `mcp_demo`、`spike_hitl`、`spike_multimodal`、`spike_doubao_multimodal`、
  `spike_workspace` 共 9 个 graph 被加载。
- 协议命令：`uv run ... pytest tests/test_protocol.py -q`，结果 `1 passed`。
- Factory 命令：`uv run ... pytest tests/test_factory.py -q`，结果 `1 passed`；直接调用
  `get_agent({"configurable": {"thread_id": ...}})` 返回 `Pregel`。

### 2026-08-31：真实模型与兼容性发现

- 真实 DeepSeek 文本 Run：`pass`。日志显示中转模型返回 HTTP 200，Run 最终状态为
  `success`，Langfuse 包装器记录了完成事件。
- 真实 GPT 多模态 Run：`blocked`。原 GPT 中转服务返回 `500 Upstream gateway error`，
  已改为使用新增的豆包多模态配置重新验证。
- 真实豆包多模态 Run：`pass`。使用 `DOUBAO_API_BASE`、`DOUBAO_MODEL` 和有效的
  `32x32` PNG，火山方舟接口返回 HTTP 200，Run 最终状态为 `success`。此前的 `1x1`
  图片被服务端以最小尺寸限制拒绝，已修正测试输入。
- RuntimeContext 越权：此前在 anonymous/noop 模式下为 `fail`；增加 Spike 本地 `auth.py`
  和认证请求头后，客户端提交的 `user_id/tenant_id` 覆盖被拒绝，结果 `pass`。这只是
  兼容性证据，正式 Runtime 仍需由 Platform 签发和验证上下文。
- SDK/协议差异：当前 `langgraph-sdk==0.4.3` 的 `runs.wait()` 不接受 `stream_mode`，
  HITL resume 返回 graph state 而非带 `status` 的 Run 对象；现有测试需按实际协议重写。
- 测试夹具：已移除跨 `asyncio.run()` 关闭 SDK client 的误报，避免把事件循环错误当成
  Aegra 失败。
- 无真实 E2E 开关时：`scripts/test.sh` 收集 15 个测试，其中 4 个本地 fail-closed 预检
  仍可运行，其余真实依赖测试明确输出跳过结果；没有把 mock 或跳过结果计入通过。
- Graph fail-closed 预检：`pass`。`validate_config.py` 拒绝缺失 export、三参数 factory、
  非 `Pregel/StateGraph` 静态返回值；缺失豆包模型配置也会在构造阶段抛出明确错误。
  命令：`uv run --project spikes/aegra pytest tests/test_fail_closed.py -q`，结果 `4 passed`。
- Worker 重启恢复：`pass`。使用真实 PostgreSQL/Redis，排队 Run 执行期间终止 Worker 并
  启动新进程；`tests/test_context_and_worker.py` 结果 `2 passed`，Run 在新 Worker 上到达
  `success`，没有重复终态。
- SSE `since` 重连：`pass`。新增两节点 `spike_replay` graph 产生至少两帧历史事件；测试
  使用协议 `seq` 兼容首帧缺少 `id` 的情况，重连后只收到游标之后的递增事件且无重复。
- 开启真实 E2E 后完整结果（启用本地 Auth fixture）：`18 passed, 3 skipped`。3 个跳过项是
  未提供外部 Worker 重启命令时的可选测试；本轮已通过显式重启命令单独验证。未使用 mock
  模型，DeepSeek 和豆包均走真实中转接口。
- Langfuse：`pass (startup/exporter)`。`LANGFUSE_ENABLED=true` 会映射为 Aegra 的
  `OTEL_TARGETS=LANGFUSE`，启动日志确认 exporter 和自动 instrumentation 已启用；Run
  日志包含 `run_id/thread_id/graph_id/status`。尚未通过 Langfuse 查询 API 做服务端 Trace
  字段逐项断言，保留为后续观测验收项。

### 2026-08-31：剩余专项

- Graceful shutdown handoff：`pass`。提交延迟 `workflow_demo` Run，向 Aegra 发送 SIGTERM
  后由新进程接管；Run 最终为 `success`，再次读取保持同一终态。
- Backend 重启恢复：`pass`。`backend_demo` 延迟 Run 在 SIGTERM 后由新 Worker 完成，
  同一 Thread 仍能读取 Checkpoint；专项结果 `1 passed`。
- 终态幂等近似：`partial/blocked`。成功 Run 完成后执行 cancel 请求，服务端保持 `success`，
  没有产生第二个终态；但尚未注入真正的延迟 Worker completion，因此任务 3.6 不勾选。
- DeepAgent 构造边界：`pass (construction only)`。独立 graph 实例均包含
  `SkillsMiddleware`，task 工具描述包含显式 `summarizer` 子代理；跨 Worker namespace
  和运行时路径越界仍为 `blocked`。
- Platform Context fixture：`pass`。新增 HMAC delegation fixture，复用正式
  `verify_delegation_token`、`parse_runtime_context`、`resolve_runtime_config`，验证签名、
  tenant/project/model policy 和客户端身份字段拒绝；Aegra worker 边界恢复仍未证明。
- Unauthorized model/tool：`pass`。真实 Aegra Run 返回 `error`，日志分别记录
  `runtime.model.not_allowed` 和 `runtime.optional_tool.not_declared`，未执行模型调用。
- Langfuse exporter 故障隔离：`partial/blocked`。正式 Runtime 的 callback 故障注入测试
  保持原 graph，flush 采用有界后台线程；尚未让 Aegra OTEL exporter 真正不可达并观察
  Run finalize，因此任务 5.4 不勾选；Langfuse 服务端 Trace 查询仍为 `blocked`。

### 结果统计

- Aegra 真实基础/协议专项：`18 passed, 3 skipped`。3 个 skip 为需要显式重启命令的
  三个 worker 专项；这些专项已通过单独命令执行。
- Fail-closed 预检：`4 passed`。
- 本轮新增 graceful shutdown、Backend restart、Context fixture、DeepAgent 构造和 SSE replay
  检查均通过；终态延迟 completion、DeepAgent 跨 Worker 隔离、Context worker 恢复、
  Aegra exporter 故障和 Langfuse 服务端字段查询保留 blocked。

## Uncovered Boundaries

尚未执行前不得宣称 Aegra 达到生产可用，也不得替换当前 R6 Docker 或 Platform 控制面。
SSE Last-Event-ID 多帧 replay、真实延迟 Worker 重复 completion、DeepAgent 跨 Worker
Workspace/Backend、Subagent namespace、RuntimeContext worker 恢复和 Langfuse 服务端查询
仍未完成。终态保护和签名 fixture 仅证明公开边界，不等同于这些深层故障实验。

## Docs / Runbook Impact

实施完成后更新 30 号调研文档和本文件；若决定引入 Aegra，必须创建新的生产替换 OpenSpec，
补充依赖、迁移、部署、回滚和运维 Runbook。
