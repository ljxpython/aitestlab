## Context

本项目 R6 Runtime 目前仍是正式执行路径。Aegra `0.10.4` Spike 已验证真实
`get_agent(config) -> Pregel`、PostgreSQL/Redis Durable、HITL、取消、Worker 崩溃恢复和优雅
停机接管，但 SSE 多帧 replay、延迟 Worker 重复 completion、DeepAgent 深层隔离、Context
跨 Worker 恢复和 Langfuse 服务端查询仍没有充分证据。本 change 只负责替换可行性评估，
不直接修改 `apps/runtime-service/deploy` 或 `apps/platform-api`。

## Goals / Non-Goals

**Goals:**

- 建立可复现的 Aegra 替换 R6 readiness 矩阵。
- 补齐剩余硬门槛实验，并区分 `pass`、`fail`、`blocked` 和近似证据。
- 明确 Platform 控制面、Aegra 执行面、RuntimeContext、Checkpoint、Trace 和回滚边界。
- 评估通过后，为后续生产切换提供独立 change 的输入。

**Non-Goals:**

- 本 change 不切换生产流量、不迁移 R6 Docker、不修改正式 Runtime 默认值。
- 不复制 Aegra 内部实现，不新增 `engine/`、`builder/`、`factory/`、`registry/` 或万能协调层。
- 不把 Langfuse 当作 Run 状态或权限事实源。

## Decisions

1. **复用现有 Spike，不另建执行框架。** 所有实验继续放在
   `apps/runtime-service/spikes/aegra/`，沿用固定依赖、真实 PostgreSQL/Redis、真实模型和
   本地 Auth/Context fixture；这样结果可重跑且不污染正式依赖。
2. **硬门槛优先于近似测试。** SSE replay 必须有至少两帧可重放历史；重复 completion 必须
   有可控迟到 Worker；DeepAgent 隔离必须跨 Worker 验证；否则记录 `blocked`，不升级为 pass。
3. **控制面/执行面分离。** Platform 继续负责 tenant/project/model/tool policy 和签发
   Context；Aegra 只负责 Agent Protocol、队列、Worker、Checkpoint、事件和执行，不接管
   Platform 权限事实源。
4. **先双轨观测再决定切换。** Aegra OTEL/Langfuse 与 Runtime 本地诊断同时保留；服务端
   Trace 查询和敏感字段断言通过后，才可把 Trace 作为生产验收证据。
5. **切换单独建 change。** 本评估通过只产生 `ready_for_cutover` 结论；迁移、灰度、回滚、
   数据兼容和 Platform API 修改必须在新的生产切换 OpenSpec 中评审。

## Risks / Trade-offs

- [Aegra Beta API 变化] -> 锁定版本和启动命令，升级必须重新跑矩阵。
- [Checkpoint/Backend 不兼容] -> 先做跨 Worker 恢复和数据格式检查，未通过则禁止切换。
- [事件 replay 证据不足] -> 不以 SDK 能连通代替协议验收，保留 blocked。
- [Exporter 故障拖慢执行] -> 注入不可达、队列满和 flush 超时，要求 Run finalize 独立完成。
- [生产回滚复杂] -> 本 change 不触碰生产；后续切换 change 必须保留 R6 回滚开关和健康探针。

## Migration Plan

1. 在隔离 Spike 中完成所有硬门槛并更新 `verification.md` 和结果报告。
2. Owner 审核 readiness：任一 blocked/fail 则保留 R6，不创建切换实现。
3. 全部通过后，另建生产切换 OpenSpec，定义依赖、数据库/Checkpoint 策略、灰度、回滚和运维 Runbook。
4. 切换 change 通过审批后才允许修改 Platform gateway、部署清单和生产流量路由。

## Open Questions

- Aegra 是否能提供稳定的多帧 replay 保留策略和公开事件去重契约？
- DeepAgent Backend/Workspace 是否需要独立持久存储才能跨 Worker 恢复？
- Langfuse 查询 API 是否能稳定返回所需关联字段并满足数据保留要求？
- R6 Checkpoint 数据是否需要迁移，还是采用新 Thread 起步并保留旧路径只读？
