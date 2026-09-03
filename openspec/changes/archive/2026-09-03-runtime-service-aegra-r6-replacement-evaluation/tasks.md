## 1. 评估夹具与版本

- [x] 1.1 固定 Aegra、LangGraph、SDK、PostgreSQL、Redis 及模型依赖版本，复核启动和停止脚本
- [x] 1.2 建立不打印密钥的 Platform Context、Auth 和多 Worker 测试前提
- [x] 1.3 创建并维护 `verification.md`，记录 owner review、命令、输入、结果、缺口和 disposition

## 2. Durable 与事件硬门槛

- [x] 2.1 真实验证 Thread/Run/Checkpoint、同 Thread 连续运行和 Lease Recovery
- [x] 2.2 注入 SIGTERM，验证 graceful shutdown handoff 不丢 Run 且只产生一个终态
- [x] 2.3 构造至少两帧历史事件，验证 SSE `since` replay 顺序、去重和断线恢复
- [ ] 2.4 注入迟到 Worker completion，验证已提交终态不可覆盖且无重复终态事件
- [x] 2.5 验证 HITL interrupt/resume、cancel 和错误/超时终态事件顺序

## 3. DeepAgent 与权限边界

- [x] 3.1 在两个 Thread、两个 Worker 上验证 Workspace/Backend 状态互不可见
- [ ] 3.2 验证 Bundled Skills 和 Subagent namespace 不跨 Thread 或 Worker 泄漏
- [x] 3.3 验证 Subagent 只能使用父 Agent 明确委派的工具和路径
- [x] 3.4 验证 tenant/project/thread/model/tool policy 和签名 Context 越权请求 fail-closed

## 4. 观测与故障隔离

- [x] 4.1 真实模型 Run 查询 Langfuse，断言 Platform Run ID、Runtime Run ID、Thread、Agent 和 model 关联字段
- [x] 4.2 断言 Trace 不包含凭证、完整 Prompt/Response 或未允许的高基数字段
- [ ] 4.3 注入 Aegra OTEL/Langfuse exporter 不可达、队列满和 flush 超时，确认 Run finalize 不受阻塞
- [x] 4.4 汇总 Aegra 日志、指标和 Runtime diagnostics，确认故障可观测且不改变业务错误语义

## 5. 替换决策与后续变更

- [x] 5.1 生成 readiness 结果报告，逐项标记 `pass`、`fail`、`blocked` 和未覆盖边界
- [x] 5.2 Owner 评审是否达到 `ready_for_cutover`；任何 blocked/fail 均保持 `not_ready`
- [x] 5.3 若全部硬门槛通过，另建生产切换 OpenSpec，补充迁移、灰度、回滚、数据兼容和 Runbook（条件未满足，按决策不创建）
- [x] 5.4 若未通过，保留 R6 正式路径，记录下一轮 Spike 所需的最小补验证集合

## 阻塞项

- 2.4：尚无可控的迟到 Worker completion 注入点。
- 3.2：当前夹具只能证明构造级 Skills/Subagent，无法证明跨 Worker namespace 隔离。
- 4.3：Exporter 不可达时 Run 能 finalize，但未覆盖队列满、flush 超时和故障日志观测。
