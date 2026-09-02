# 仓库级 Harness

- 文档类型：Current Navigation
- 适用范围：仓库内人和 AI 的任务路由、验证与交付闭环

Harness 是本仓库的工程操作范式，不是 Runtime R0-R6 的专用流程，也不是单个测试工具、
Prompt 或目录。它负责让任务在明确的 owner、契约、验证和验收边界内完成。

## 1. 从这里开始

处理非 trivial 任务时，按以下顺序阅读：

1. [根级 AI 路由](../../AGENTS.md)：确定仓库级约束和当前任务的初始入口。
2. 本文：确认通用 intake、证据等级和需要跳转的资料。
3. 最窄的 app/service current standard：确认该领域的 owner、契约和局部规则。
4. [AI 执行系统当前标准](../standards/01-ai-execution-system.md)：仅在跨 leaf 路由、Band 或治理升级需要时读取。
5. 相关代码、测试、delivery checklist、runbook 或 OpenSpec：获取实现事实和验收证据。

不要默认读取整个 `docs/`、`docs/knowledge/` 或所有历史 change。

## 2. 通用 Intake

每项非 trivial 工作先回答以下七项：

| 字段 | 要回答的问题 |
| --- | --- |
| Goal | 期望什么可观察结果成立？ |
| Locus | 哪个 app、service、模块或仓库表面对结果负责？ |
| Chain | 从输入到结果的最短真实调用、数据或契约链是什么？ |
| Authority | 哪些 leaf standard、repo standard 或公开契约生效？ |
| Band | B1 Local、B2 Chain 还是 B3 Governed？ |
| Evidence | 什么是覆盖该边界的最小充分证据？ |
| Acceptance | 谁需要确认，哪些边界仍未覆盖或被后置？ |

这七项适用于页面、API、Runtime、数据服务、配置、部署、发布和文档规则。它们不替代
具体领域的输入模型、测试策略或运维流程。

## 3. Band 与验证

| Band | 使用条件 | 默认交付 | 验证 |
| --- | --- | --- | --- |
| B1 Local | 单一 locus，未修改受治理边界 | 会话内最小闭环 | local/minimal |
| B2 Chain | 单一 locus 的有意义改动，或最短相邻链 | 短计划；需要持久评审时使用 OpenSpec | local + shortest chain |
| B3 Governed | 公开契约、权限、审计、所有权、迁移、发布、外部兼容或真实用户输入 | OpenSpec change 与 owner review | 对应边界的正式证据 |

验证顺序固定为：

```text
local/minimal -> shortest relevant chain -> formal/human when required
```

状态必须与证据深度一致：

- `local-complete`：只有本地证明成立。
- `chain-complete`：最短真实链成立。
- `formal-complete`：所需正式或人工验收成立。
- `blocked` / `not-executed`：真实条件缺失，不能声明通过。
- `deferred`：明确后置，不计入当前完成度。

mock、fake、in-memory 和 skip 只能证明它们实际覆盖的层级，不能冒充真实集成或正式验收。

## 4. 资料归位

| 需要的内容 | 权威位置 |
| --- | --- |
| 当前强制规则 | `docs/standards/` 和各 app/service 的 current standards |
| 使用方式与背景 | `docs/ai-execution-system-usage-guide.md`、`docs/knowledge/` |
| 实现事实与局部验证 | 相关 app/service 的代码与 `tests/` |
| 联调、发布、排障 | `docs/delivery/`、各服务 `docs/delivery/`、`docs/runbooks/`、部署文档 |
| 持久化 B2/B3 变更 | `openspec/changes/`，accepted 后同步到 `openspec/specs/` 并归档 |
| 历史计划和报告 | `.harness/`、archive 或标记为 `Archived` 的文档，仅供追溯 |

Harness 只负责导航、分级、验证深度和人工门禁。它不得复制或覆盖服务标准、业务契约、
运行手册、测试实现或 OpenSpec 的变更生命周期。

新建或主动更新的持久化 B2/B3 change 使用 `verification.md` 的 Harness metadata v1：

```text
- Harness verification schema: v1
- Status: Pending | Complete
- Disposition: Pending acceptance | Accepted | Rejected | Abandoned
- Pre-apply review: Pending | Approved | Waived
```

证据矩阵中的 `local-complete`、`chain-complete`、`formal-complete`、`blocked` 和 `deferred`
描述的是证据深度，不替代上面的 change lifecycle 状态。历史 verification 不要求批量迁移，
但不得覆盖当前标准。

## 5. 领域入口

| Locus | 首选入口 |
| --- | --- |
| `platform-web` | `apps/platform-web/docs/frontend-development-playbook.md`、`apps/platform-web/docs/control-plane-page-standard.md` |
| `platform-api` | `apps/platform-api/docs/handbook/`、`apps/platform-api/docs/standards/`、`apps/platform-api/tests/` |
| `runtime-service` | `apps/runtime-service/docs/`、`apps/runtime-service/tests/` |
| `runtime-web` | `apps/runtime-web/docs/standards/runtime-web-debug-standard.md` |
| `interaction-data-service` | `apps/interaction-data-service/docs/`、`apps/interaction-data-service/tests/` |

Runtime 的 R0-R6 是这个范式在 `runtime-service` 的领域实例。阶段设计、实现对齐和证据
请看 [Runtime R0-R6 对齐审计](../../apps/runtime-service/docs/knowledge/31-runtime-refactor-alignment-audit.md)，
它不是全仓库 Harness 的定义。

## 6. 完成检查

交付前确认：

1. Locus、Chain 和 Authority 已明确。
2. Band 与真实风险匹配，没有为了省事降级或为了形式升级。
3. 先完成了 local proof，再按需完成最短真实链和正式验收。
4. `blocked`、`not-executed`、`deferred` 和未覆盖边界已如实记录。
5. B3 的 OpenSpec、owner review、`verification.md`、spec sync 和 archive 已按生命周期完成。
6. 文档、runbook、交付清单和历史状态没有产生新的重复真源。
