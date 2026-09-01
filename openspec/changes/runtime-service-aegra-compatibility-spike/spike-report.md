# Aegra Compatibility Spike 结果

日期：2026-08-31  
版本：Aegra `0.10.4`、LangGraph `1.2.11`、langgraph-sdk `0.4.3`  
范围：`apps/runtime-service/spikes/aegra`

## 结果摘要

- 基础协议、真实 DeepSeek 文本、豆包多模态、PostgreSQL/Redis Durable、HITL、取消、
  Worker 崩溃恢复、优雅停机接管、Backend 重启恢复、权限拒绝：`pass`。
- Langfuse exporter 启动和本地 fail-soft callback：`partial`；Aegra exporter 故障注入及
  Langfuse 服务端 Trace 字段逐项查询：`blocked`。
- 公开 API 终态保护：`partial`；真正延迟 Worker completion 的重复终态实验：`blocked`。
- SSE 断线 replay：`pass`。新增两节点 `spike_replay` graph，使用 `since` 和协议 `seq`
  验证断线后的递增事件和去重。
- DeepAgent 跨 Worker 的 Skills/Subagent namespace 隔离、Subagent 能力收缩、RuntimeContext
  在 Worker 边界恢复：`blocked`，当前夹具不能证明这些边界。
- 最后一次真实回归：`18 passed, 3 skipped`；另有本地 fail-closed/fixture 检查全部通过。

## 可复现实验

```bash
cd apps/runtime-service/spikes/aegra
./scripts/up.sh
AEGRA_SPIKE_E2E=1 ./scripts/test.sh
```

专项命令：

```bash
AEGRA_SPIKE_E2E=1 AEGRA_SPIKE_GRACEFUL_SHUTDOWN=1 \
AEGRA_SPIKE_GRACEFUL_SHUTDOWN_COMMAND='pid=$(<.aegra.pid); kill -TERM "$pid"; sleep 3; ./scripts/up.sh' \
./scripts/test.sh tests/test_context_and_worker.py::test_graceful_shutdown_handoff -q

AEGRA_SPIKE_E2E=1 AEGRA_SPIKE_BACKEND_RESTART=1 \
AEGRA_SPIKE_RESTART_COMMAND='pid=$(<.aegra.pid); kill -TERM "$pid"; sleep 3; ./scripts/up.sh' \
./scripts/test.sh tests/test_context_and_worker.py::test_backend_scope_survives_worker_restart -q
```

## 决策

Spike 证明 Aegra 能承接当前 `async def get_agent(config) -> Pregel` 和主要 Durable 基础能力，
但仍未达到本项目生产替换门槛。保留 R6 正式路径，不创建生产引入 change；待补齐 SSE replay、
DeepAgent 隔离、Context worker 恢复和 Langfuse 服务端查询后再重新评审。
