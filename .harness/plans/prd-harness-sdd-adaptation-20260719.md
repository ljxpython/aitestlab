# Harness + SDD 适配决策

- 状态：Archived；已由 `openspec/changes/adopt-openspec-harness/` 取代
- 日期：2026-07-19
- Execution band：B3

## Goal

为当前仓库补齐可追踪的 SDD 变更生命周期，同时保留已经稳定的 locus-first Harness、服务边界和验证门禁。

## Decision

不再自建一套完整 SDD 框架。保留仓库现有 Harness 作为治理协议，适配 OpenSpec 作为 **B3 可选变更生命周期加速器**。

- B1/B2：继续使用现有 `AGENTS.md`、leaf standards、`.harness/templates/` 和最短验证链。
- B3：试点使用 OpenSpec 管理 proposal、spec delta、design（按需）、tasks 和 archive。
- Spec Kit：不作为本仓默认框架，仅保留给独立绿地模块的可选能力。
- Superpowers：属于执行方法/技能，不承担 spec source of truth；只能在选定 execution band 后辅助执行。

## Scope

- In：repo 级 Harness/SDD 选型、权威边界、产物映射、试点和退出条件。
- Out：本次不安装 OpenSpec，不初始化 `openspec/`，不迁移历史 `.harness/plans/`，不改业务代码。

## Not-do List

- 不让任何工具生成第二套 repo constitution。
- 不让 `openspec/` 覆盖 `docs/standards/` 或 leaf-local standards。
- 不在 `.harness/plans/` 和 `openspec/changes/` 重复维护同一变更。
- 不把 B1/B2 强制升级为重型 SDD 流程。
- 不同时启用 OpenSpec 和 Spec Kit 作为默认变更权威。

## Locus / Layer

- Owning locus：repo-level / process / standards
- Harness layer：L1 standards + L4 acceptance，`.harness` 仅承载 helper/runtime artifacts
- Chain map：formal chain
- Escalation rationale：本决策改变后续 B3 产物位置和流程，且需要外部框架调研。

## Standards Loaded

- `AGENTS.md`
- `docs/standards/01-ai-execution-system.md`
- `docs/ai-execution-system-usage-guide.md`
- `docs/knowledge/01-harness-engineering-foundation.md`
- `docs/knowledge/02-aitestlab-harness-blueprint.md`
- `docs/knowledge/03-harness-operating-model.md`
- `docs/knowledge/04-ai-execution-system-rationale.md`
- `.harness/README.md`
- `.harness/reports/verification-omx-independent-harness-20260425.md`

## Evidence

当前仓库已经具备 Harness 的核心治理能力：

- `AGENTS.md` 提供薄路由和执行门禁。
- `docs/standards/` 与 leaf docs 提供现行权威规则。
- B1/B2/B3 决定流程深度，L1-L4 决定知识和验收落点。
- `.harness/templates/` 已定义 locus、artifact grammar、真实输入和验证证据。
- `.harness/plans/` 已出现 PRD、Test Spec、TODO 的正式产物链。
- 既有迁移验收明确要求 protocol-only path 可独立工作，任何 accelerator 都必须可选且不能形成 shadow canon。

Graphify 对 `.harness` 的分析得到 41 个节点、58 条关系，完整性检查无悬空边、缺失端点、自环或折叠边。核心连接集中在 PRD/Test Spec、locus classification、verification evidence 和 optional accelerator boundary。

## Options Considered

### 1. 自建完整 Harness + SDD

拒绝。现有 Harness 已经解决治理、路由、边界和验证；再自建 proposal/spec/archive 引擎只会复制成熟框架的变更生命周期、CLI 校验和归档维护成本。

### 2. Spec Kit 作为默认 SDD

拒绝。它的 constitution、`.specify/`、`specs/` 以及 `specify -> plan -> tasks -> implement` 全流程与本仓现有 routing constitution、标准目录和 B1-B3 产物高度重叠，更适合绿地或独立新模块。

### 3. OpenSpec 作为 B3 加速器

采用。它的 `proposal -> specs -> design -> tasks -> implement -> archive` 适合棕地仓库的增量变更治理，并支持通过 custom schema 增加 test spec 和 verification artifact。

### 4. Superpowers 作为 SDD 主框架

拒绝。它适合增强 brainstorming、planning、implementation 和 review 行为，但不应承担长期规格、变更归档和 repo authority。

## Authority Matrix

| Concern | Authority |
| --- | --- |
| 任务入口、locus、execution band、升级门禁 | `AGENTS.md` + `docs/standards/01-ai-execution-system.md` |
| 服务边界、公开契约、leaf 实现标准 | 最窄的 leaf-local authoritative docs |
| 已批准的能力需求 | 试点通过后由 `openspec/specs/` 承载；不得覆盖上面两类治理/契约 authority |
| B3 进行中的变更产物 | `openspec/changes/<change-id>/` |
| B1/B2 helper 模板 | `.harness/templates/ai-execution-system/` |
| 跨变更或 repo 级报告 | `.harness/reports/` |
| 历史计划 | 现有 `.harness/plans/` 保留，不批量迁移 |

冲突解析顺序固定为：leaf authority -> repo current-standard -> OpenSpec capability spec -> knowledge/helper artifacts。

## Proposed B3 Artifact Mapping

| Repo-native grammar | OpenSpec artifact |
| --- | --- |
| Goal / Scope / Not-do / impact | `proposal.md` |
| capability requirements / acceptance scenarios | `specs/<capability>/spec.md` |
| locus / chain / ownership / decisions / I/O contract | `design.md` |
| verification design and implementation checklist | `tasks.md` |
| complex/high-risk test matrix | dedicated Test Spec，按需生成 |
| executed checks and acceptance evidence | task completion notes / repo tests；跨 change 时再写 report |

试点直接使用官方默认 `spec-driven` schema。至少完成 2-3 个真实 B3 change，
并确认 dedicated Test Spec/verification artifact 是重复缺口后，才评估 custom schema。

## Pilot

1. 用户明确授权后安装并初始化 OpenSpec。
2. 使用默认 `spec-driven` schema，只配置本仓 context/rules。
3. 选一个真实但边界清晰的 B3 变更跑完整生命周期。
4. 验证通过后再更新 current-standard 和 usage guide；失败则删除试点配置，现有 Harness 不受影响。

## Acceptance Criteria

- B1/B2 不依赖 OpenSpec 也能完整工作。
- B3 单个变更只有一套 proposal/spec/design/test/tasks/verification 产物。
- OpenSpec 不复制或覆盖 repo/leaf standards。
- 试点能完成 validate、apply tracking、verification 和 archive。
- 移除 OpenSpec 后，`AGENTS.md` 和现有 Harness 协议仍可独立执行。

## Retro / Doc Decision

本次只记录决策和试点门禁。安装、初始化和 current-standard 改动必须在用户确认后进行。
