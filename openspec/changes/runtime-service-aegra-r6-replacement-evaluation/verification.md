# Verification

- Status：In progress
- Disposition：Pending acceptance
- Pre-apply review：Approved
- Change：`runtime-service-aegra-r6-replacement-evaluation`
- Locus：`apps/runtime-service`
- Chain：Runtime Service -> Aegra -> PostgreSQL/Redis/Langfuse -> Platform gateway
- Band：B3 Governed

## Pre-apply Review

- Owner decision：Approved（用户确认开始实施）
- Reviewer：项目负责人
- Review date：2026-08-31
- Scope waiver：无

## Planned Evidence

- 复用 `apps/runtime-service/spikes/aegra/` 的真实模型、PostgreSQL、Redis 和 Langfuse 环境。
- 对 SSE 多帧 replay、迟到 Worker completion、DeepAgent 跨 Worker 隔离、RuntimeContext
  恢复和 Aegra exporter 故障执行可重复专项。
- 运行本 change tasks 中的本地、最短链和必要正式验证命令，不把 skip/blocked 计为 pass。

## Current Baseline

兼容性 Spike 当前为 `21/28` 完成；本 change 已补出 SSE 多帧 replay 通过证据，并查询到
真实 Langfuse Trace。延迟 completion、DeepAgent 深层隔离、Context worker 恢复和 Aegra
exporter 故障仍为 blocked；Langfuse 关联/脱敏门槛为 fail。详细结果见：

- `openspec/changes/runtime-service-aegra-compatibility-spike/spike-report.md`
- `apps/runtime-service/docs/knowledge/30-agent-server-replacement-research.md`
- `openspec/changes/runtime-service-aegra-r6-replacement-evaluation/readiness-report.md`

## Implementation Evidence

- SSE：新增 `spike_replay` 两节点 graph，真实 `since` 重连测试通过，事件序列递增且无重复。
- Langfuse API：真实 Trace 可见 `run_id/thread_id/graph_id`，但缺少 `model_id`，且 input/output
  仍包含实际内容；因此关联和脱敏门槛分别记录为 `fail`。查询命令为
  `GET /api/public/traces?limit=5`，只输出字段名、长度和布尔结果，不输出凭证或内容。
- 现有真实回归：`18 passed, 3 skipped`；新增 SSE 专项通过。未使用 mock 代替真实服务证据。
- DeepAgent task 工具静态检查发现内置 `general-purpose` 类型仍可见，超出显式委派的
  `summarizer` 能力范围；Subagent 能力收缩门槛记录为 `fail`。
- Aegra exporter 故障注入：将 `LANGFUSE_BASE_URL` 指向不可用本机端口后，确定性
  `workflow_demo` Run 仍成功 finalize；但本次窗口未观察到 exporter 错误日志，队列满/flush
  超时也未覆盖，因此任务 4.3 仍为 `blocked`。

## Decision Rule

只有所有硬门槛均为可复现 `pass` 才能将状态改为 `ready_for_cutover`。当前存在 `fail` 和
`blocked`，状态保持 `not_ready`，
不修改 R6 正式部署，也不在本 change 中创建生产切换代码。

因此任务 5.3 的条件不满足，本轮没有创建生产切换 OpenSpec；继续保留 R6 正式路径。

## Docs / Runbook Impact

本评估完成后更新 Spike 报告和 Aegra 调研文档。若通过，后续独立生产切换 change 必须补充
部署、迁移、灰度、回滚、数据保留和运维 Runbook；若不通过，只记录缺口和下一轮最小实验。
