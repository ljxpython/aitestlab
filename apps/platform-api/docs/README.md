# Platform API 文档导航

文档类型：`Docs Index`

`apps/platform-api` 是当前正式 control plane 宿主；本目录文档应放在仓库总 harness 之下理解，而不是脱离根文档单独阅读。

推荐事实源顺序：

1. 代码与模块接口：`app/modules/**`
2. `handbook/project-handbook.md`
3. `handbook/architecture.md`
4. 本导航页

`apps/platform-api/docs` 现在按“主手册、标准、交付、决策、归档”五类组织。

如果你是第一次接手，不要先翻 `phase-*`，先看主手册。

当前阶段状态：

- `Phase B: Control Plane Freeze` 已完成
- `Phase C: Data & Delivery Freeze` 已完成
- `Phase D: Final Standard Freeze` 已完成

## 1. 新同事先看什么

1. `handbook/project-handbook.md`
   - 这套服务做什么、上层业务怎么用、权限怎么判、模块怎么拆
2. `handbook/architecture.md`
   - 服务边界、模块职责、长期架构形态
3. `handbook/development-playbook.md`
   - 人和 AI 的统一开发规范与 Harness 工作流

## 2. 正式标准放哪

- `standards/permission-standard.md`
- `standards/audit-standard.md`
- `standards/operations-standard.md`
- `standards/runtime-gateway-interface-standard.md`

这些文档是长期生效的规则，不是阶段性纪要。

## 3. 交付和运维资料放哪

- `delivery/change-delivery-checklist.md`
- `delivery/circular-import-remediation-checklist.md`
- `delivery/module-delivery-template.md`
- `delivery/platform-web-gap-closure-checklist.md`
- `delivery/runbook.md`
- `delivery/postgres-baseline.md`
- `delivery/release-template.md`
- `delivery/runtime-contract-three-wave-checklist.md`
- `delivery/runtime-contract-manual-integration-checklist.md`
- `delivery/platform-runtime-graphharbor-integration-checklist.md`

其中：

- `circular-import-remediation-checklist.md`
  - 当前 `platform-api` 的循环导入治理清单与回归记录；`identity / projects / runtime_gateway` 首轮治理已完成
- `platform-web-gap-closure-checklist.md`
  - 说明 `platform-api` 与 `platform-web` 的正式能力边界、前端收口任务和执行顺序
- `runtime-contract-three-wave-checklist.md`
  - 当前 runtime contract 三波次改造的执行单
- `runtime-contract-manual-integration-checklist.md`
  - runtime contract 的手工联调与验收清单

## 4. 迁移决策和历史方案放哪

- `decisions/frontend-switch-strategy.md`
- `decisions/langgraph-sdk-migration-plan.md`
- `decisions/legacy-solution-inheritance-checklist.md`
- `decisions/first-batch-module-map.md`
- `decisions/platform-capability-reconciliation.md`

其中：

- `platform-capability-reconciliation.md`
  - 说明当前后端能力哪些已经被前端正式消费，哪些只是弱接入，哪些应该暂时收成 internal

## 5. 历史阶段记录放哪

- `archive/phases/`

这里保留 phase-1 到 phase-8 的执行清单、验收记录和冻结过程，主要用于回看演进过程，不再作为新人第一入口。

## 6. 常用启动入口

- 仓库根目录：`bash "./scripts/platform-web-demo-up.sh"`
- 健康检查：`bash "./scripts/platform-web-demo-health.sh"`
- 停止：`bash "./scripts/platform-web-demo-down.sh"`
