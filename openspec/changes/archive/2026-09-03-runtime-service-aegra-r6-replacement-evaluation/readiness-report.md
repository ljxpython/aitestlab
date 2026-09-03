# Aegra 替换 R6 Readiness 报告

评估日期：2026-08-31  
版本：Aegra `0.10.4`、LangGraph `1.2.11`、langgraph-sdk `0.4.3`  
结论：`not_ready`

## 门槛结果

| 范围 | 结果 | 证据 |
| --- | --- | --- |
| Thread/Run/Checkpoint/Lease | pass | Spike 真实 PostgreSQL/Redis E2E |
| Graceful shutdown handoff | pass | SIGTERM 后新 Worker 完成 Run |
| HITL、Cancel、错误终态 | pass | `test_durable.py` |
| SSE `since` replay | pass | `spike_replay` 两节点 graph，顺序和去重通过 |
| 延迟 Worker 重复 completion | blocked | 尚无可控迟到 Worker 注入 |
| Workspace/Backend Thread 隔离 | pass | 双 Thread + Backend 重启专项 |
| Skills/Subagent 跨 Worker namespace | blocked | 当前只能做构造级检查 |
| Subagent 工具/路径收缩 | fail | DeepAgent task 工具描述暴露内置 `general-purpose` 类型，超出仅委派 `summarizer` 的预期 |
| Context 签名和模型/工具拒绝 | pass | HMAC fixture + 真实 Run fail-closed |
| Context 跨 Worker 恢复 | blocked | 未证明 worker 边界的可信恢复语义 |
| Langfuse 关联字段 | fail | API 查询有 run/thread/graph，但缺少 `model_id` |
| Langfuse 脱敏 | fail | Trace API 可见完整 input/output，未满足内容脱敏门槛 |
| Exporter 故障不阻塞 finalize | blocked | 不可用 endpoint 下 Run 成功，但未观察到故障日志，队列满/flush 超时未覆盖 |

## Langfuse 查询证据

使用 Langfuse Public API `/api/public/traces?limit=5` 查询真实 Spike Trace：

- `run_id`、`thread_id`、`graph_id` 可关联；
- `model_id` / Platform trace 字段未出现在 Trace metadata；
- Trace `input` 和 `output` 字段仍有实际内容，不能宣称完整 Prompt/Response 已脱敏；
- 未发现 metadata 中的凭证字段，也未发现配置密钥泄漏。

因此 Langfuse 观测门槛当前为 fail，而不是 pass。

## 决策

保持正式 R6 Runtime 和部署路径不变，不创建生产切换实现。下一轮最小补验证集合：

1. 注入迟到 Worker completion，验证终态条件更新和事件去重；
2. 证明 DeepAgent Skills/Subagent namespace 在不同 Worker 上隔离；
3. 让 RuntimeContext 在 worker handoff 后从可信存储恢复；
4. 修正 Aegra OTEL/Langfuse metadata allowlist 和内容脱敏，并验证 exporter 故障不影响 finalize。
