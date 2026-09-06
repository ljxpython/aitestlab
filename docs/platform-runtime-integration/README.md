# Platform Runtime Integration 项目文档

> 方案处置（2026-09-04）：旧统一模型代理、execution reference/revision、Secret Store 编排和 RS256/JWKS
> 设计已 `Superseded/Rejected`。当前实施依据为七字段模型配置、API key 只写不读、服务端加密；本目录
> 中旧段落仅保留追溯意义。

- 文档类型：Draft Supporting Project Documentation
- 状态：`pre-apply-approved; L1 partial; L2 local-complete; L3 partial`
- 项目 owner：用户
- 主要 locus：`apps/platform-web`、`apps/platform-api`
- 相邻执行 locus：GraphHarbor Compatibility Profile、`apps/runtime-service`
- Execution band：B3 Governed
- 更新时间：2026-09-05

## 1. 文档目的

本文档组记录 Platform Runtime Integration 的项目级方案、讨论结论、Harness 路由、实施计划和证据状态。
它解决两个问题：

1. 让项目成员能在 `docs/` 下读到完整的背景、边界、决策和交付计划；
2. 让每个方案都能回到 owner 决策、OpenSpec 任务和可执行验证，而不是停留在聊天记录里。

本文档组是 supporting material，不替代任何当前标准，也不复制 OpenSpec 的任务和证据真源。

## 2. 项目目标与最短链

目标是让 Platform Web 通过官方 LangGraph SDK，经 Platform API 治理后稳定使用 GraphHarbor 执行面：

```text
platform-web
  -> official LangGraph SDK
  -> platform-api /api/langgraph Gateway
  -> GraphHarbor API
  -> Redis
  -> GraphHarbor Worker
  -> runtime-service graph
  -> GraphHarbor PostgreSQL
```

P1 不重写 Runtime Durable Core，不把 Platform 业务模型搬进 GraphHarbor，也不新增万能透明代理。

## 3. Harness Intake

| 字段 | 本项目结论 |
| --- | --- |
| Goal | 标准 SDK 请求经过 Platform 治理后，能够安全创建、读取、流式观察、恢复、响应和取消 GraphHarbor Run |
| Locus | `platform-web` 与 `platform-api` 负责产品和控制面；GraphHarbor 只负责通用兼容；Runtime 负责 graph/runtime contract |
| Chain | Web -> Gateway -> GraphHarbor API -> Redis -> Worker -> Runtime graph -> GraphHarbor PostgreSQL |
| Authority | leaf current standards、Runtime executable contracts、GraphHarbor Compatibility Profile、active OpenSpec specs |
| Band | B3 Governed：公开协议、认证授权、数据所有权、迁移、发布和跨仓库兼容均受影响 |
| Evidence | local contract tests -> GraphHarbor 最短真实链 -> 浏览器真实链 -> owner UAT |
| Acceptance | owner 接受方案后才能 apply；真实链和 UAT 完成后才能清理 legacy 内容并归档 |

## 4. 文档地图

1. [决策记录](./01-decision-record.md)：D01–D12、GATE-10、Deferred 边界和 owner 决策记录。
2. [Harness 实施与验收计划](./02-harness-delivery-plan.md)：生命周期、分阶段计划、门禁和证据矩阵。
3. [证据与开放约束](./03-evidence-and-open-constraints.md)：当前已执行检查、未执行边界和实施前约束。
4. [专项导航与详细技术材料](../../apps/runtime-service/docs/knowledge/platform-runtime-integration/README.md)：Runtime 侧的现状、目标契约、迁移和推荐基线。
5. [本地三阶段交付计划](./04-local-three-stage-delivery-plan.md)：本地合同闭环、最短真实链和生产形状模拟的阶段出口与状态。
6. [专项实施状态与验证记录](../../apps/runtime-service/docs/knowledge/platform-runtime-integration/10-implementation-status.md)：按 Harness 记录功能点、代码落点、命令结果和未覆盖边界。
7. [模型目录与前端信息架构简化方案](../../apps/runtime-service/docs/knowledge/platform-runtime-integration/12-simplified-model-and-ui-plan.md)：移除 profile/E2E 门禁，收敛 Agent、Graph、Models 和 Runtime Policy 的产品边界。
8. [Chat 前端文字 Harness](../../apps/platform-web/docs/chat-frontend-harness.md)：人工/AI 执行卡、通过标准、停止条件和脱敏证据模板。

## 5. 权威关系

| 内容 | 唯一真源 | 本文档组的作用 |
| --- | --- | --- |
| 为什么做、范围和非目标 | `openspec/changes/redesign-platform-runtime-integration/proposal.md` | 解释项目背景和入口 |
| 公开需求与验收场景 | `openspec/changes/redesign-platform-runtime-integration/specs/` | 说明决策如何落成可验证要求 |
| 架构取舍与契约 | `openspec/changes/redesign-platform-runtime-integration/design.md` | 记录项目级阅读摘要和决策背景 |
| 实施任务 | `openspec/changes/redesign-platform-runtime-integration/tasks.md` | 唯一任务清单，本目录不复制勾选状态 |
| 命令、输入、结果和未覆盖边界 | `openspec/changes/redesign-platform-runtime-integration/verification.md` | 唯一证据记录，本目录只做导航和解释 |
| 当前强制规则 | `docs/standards/`、各 app/service leaf standards | 本文档不得覆盖 |

## 6. 当前状态摘要

- D01–D12 架构决策：已由 owner 逐项确认。
- GATE-13 Run consistency：已确认统一 launch use case、Run intent/outbox、幂等和 reconciliation。
- GATE-10 历史 Thread：仍为 `Pending inventory`，需要真实数据盘点和脱敏 fixture。
- 旧模型代理 owner、Secret Store、服务身份和 Provider proxy 兼容性方案已废弃，不再收集或作为门禁。
- OpenSpec pre-apply review：`Approved`；七字段模型管理已有局部代码和测试证据。
- GraphHarbor 本机最短真实链：已完成；浏览器完整 E2E、API/Worker 重启恢复和 owner UAT：尚未完成。真实 Provider smoke 不属于当前最小方案门禁。
- Gateway 已收窄为正式 Chat allowlist；旧 Debug 页面、debug service 和 Chat/Assistant 工具选择入口已删除。Thread 删除与 state update 因当前产品工作流仍在使用而保留。
- Chat 前端文字 Harness 已落地到 `apps/platform-web/docs/chat-frontend-harness.md`；它强制新 Thread、双轮唯一标识、刷新恢复和 state/history/Run 一致性证据。自动化脚本只作辅助，不作为验收真源。
- 新增并获 owner 接受的简化规划：模型目录成为唯一模型配置来源；`RUNTIME_MODEL_PROFILE`、`RUNTIME_E2E` 进入移除任务；用户界面以 Agent、Models、Chat、Threads 为主，Graph/Policy 保留为内部或管理员能力。代码实施尚未开始。
- change lifecycle：`Status: Pending`；实现和证据仍以 OpenSpec 为准，不能称为完成。

## 7. 讨论和实施顺序

```text
方案讨论完成
  -> OpenSpec 与 docs 项目记录同步
  -> GATE-10 inventory / 模型代理边界确认
  -> owner pre-apply evidence review
  -> /opsx:apply
  -> local verification
  -> shortest real chain
  -> browser E2E + owner UAT
  -> accepted delta specs sync
  -> cleanup and archive
```

任何一层证据缺失，都不能把下一层的计划写成已完成事实。
