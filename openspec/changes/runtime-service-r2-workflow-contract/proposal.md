## Why

R2 的目录设计已经把 `workflow_demo` 定义为 StateGraph、条件分支和可恢复流程的参考
Service，但 active spec 目前只覆盖 `reference_agent`，导致设计目标、归档 OpenSpec 和
实现验收范围不一致。与此同时，归档 R2 要求空 `RunnableConfig` 也能创建 Agent，和 R1
要求身份缺失时 fail-closed 存在安全冲突，需要冻结为一个不允许匿名补身份的合同。

## What Changes

- **BREAKING** 将 `workflow_demo` 的 Typed StateGraph、条件分支和本地 Interrupt/Resume
  能力加入 `runtime-agent-service-integration` active spec。
- 要求 Workflow 的本地 Resume 从服务端声明的恢复点继续，并通过测试证明已完成节点不重复执行。
- 将 `get_agent({})` 的旧默认成功场景改为：没有已验证 Auth facts 时稳定失败；本地测试必须
  使用显式 test-only model/identity fixture，不能从空配置隐式补 Principal 或 Policy。
- 明确 R2 只验证本地 Workflow 组合行为；PostgreSQL、Redis、Worker 重启和生产 Durable
  Run 仍由 R6 验证。
- 保持 `graphs/<graph_id>.py` 只做稳定导出，不增加公共 Workflow Builder、通用 Factory
  或第二套 Auth 实现。

## Capabilities

### New Capabilities

无。Workflow 属于现有 Agent Service integration 能力。

### Modified Capabilities

- `runtime-agent-service-integration`: 增加 `workflow_demo` 的分支和本地恢复合同，并修正
  `reference_agent` 空配置的身份缺失语义。

## Impact

- **Owning locus**：`apps/runtime-service`。
- **Execution band**：B3 Governed；active spec、认证失败语义和恢复行为是受治理合同。
- **Affected code**：`src/runtime_service/demo/workflow_demo/`、
  `src/runtime_service/services/reference_agent/`（仅在实现阶段按批准设计调整）、
  `tests/services/` 和必要的 Agent Server 集成测试。
- **Affected docs**：11、28、31 号 R2 对齐矩阵，以及 R2 verification evidence。
- **Compatibility**：生产匿名/缺失 Auth 请求继续被拒绝；本地调用从隐式空配置改为显式测试
  配置。R6 的真实 Durable 合同不在本变更中提前宣称完成。
- **Rollback**：若 Workflow 本地恢复验证失败，回退本变更的 Service/spec 增量；不修改
  已有 Thread/Checkpoint 数据格式。
