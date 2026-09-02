## ADDED Requirements

### Requirement: Harness SHALL provide one repo-wide task intake and navigation entry

仓库级 Harness SHALL 为人和 AI 提供一个唯一的总入口，说明任务开始时必须识别的 Goal、Locus、Chain、Authority、Band、Evidence 和 Acceptance，并将调用方导航到最窄的有效标准、实现位置和验证证据。该入口不得复制服务标准、业务契约或 OpenSpec 内容。

#### Scenario: New task starts from the Harness entry
- **WHEN** 人或 AI 开始处理仓库内任意 app、service、文档、部署或发布任务
- **THEN** 可以从 `docs/harness/README.md` 找到任务 intake 字段、阅读顺序和对应的服务级入口

#### Scenario: Harness does not become a second source of truth
- **WHEN** 任务需要读取具体服务规则、业务契约或变更方案
- **THEN** Harness 只导航到 `docs/standards/`、leaf-local docs、代码/测试、delivery docs 或 `openspec/`，不复制其正文

### Requirement: Harness SHALL classify work by ownership, chain and governance risk

每项非 trivial 工作 SHALL 先确定主要负责的 Locus、实际受影响的最短 Chain 和执行 Band。Band SHALL 按边界和风险选择 `B1 Local`、`B2 Chain` 或 `B3 Governed`，不得按代码行数、工期或主观优先级选择。涉及公开契约、权限、审计、数据所有权、迁移、跨 owner、生产发布回滚、外部兼容或用户真实凭据的工作 MUST 使用 B3。

#### Scenario: Local change uses the lightest band
- **WHEN** 一个改动只影响单一 locus，且不修改受治理契约
- **THEN** Harness 将其归为 B1，并要求 local/minimal verification，不默认创建 OpenSpec change 或运行全链路测试

#### Scenario: Governed boundary escalates to B3
- **WHEN** 一个改动修改权限、公开 API、跨服务 owner、迁移、生产发布或需要用户凭据的真实验收
- **THEN** Harness 将其归为 B3，并要求 OpenSpec、owner review 和对应正式证据

### Requirement: Harness SHALL define progressive verification and honest completion states

验证 SHALL 按 `local/minimal -> shortest relevant chain -> formal/human` 递进，验证深度由 Band 和受影响边界决定。缺失环境、凭据或外部依赖时 MUST 标记 `blocked` 或 `not-executed`；主动后置的能力 MUST 标记 `deferred`；skip 不得计为 pass。完成状态 SHALL 明确区分 `local-complete`、`chain-complete`、`formal-complete`、`blocked` 和 `deferred`。

#### Scenario: Missing real input does not create a false pass
- **WHEN** 真实集成所需服务、凭据或数据集不可用
- **THEN** 验证结果记录缺失输入和 `blocked`/`not-executed`，不会用 mock、fake 或 skip 宣称正式链路通过

#### Scenario: Completion matches evidence depth
- **WHEN** 只有本地测试通过而最短真实链路尚未验证
- **THEN** 任务最多标记为 `local-complete`，不得标记为 `chain-complete` 或 `formal-complete`

### Requirement: Harness SHALL separate current authority, supporting knowledge, helpers and change lifecycle

Harness SHALL 明确以下职责：`docs/standards/` 和 leaf-local current standards 定义当前规则；`docs/knowledge/` 解释背景；`tests/`、delivery docs 和 runbooks 提供可执行证据和操作步骤；`openspec/` 管理需要持久评审的 B2/B3 变更生命周期。helper、历史计划和归档文档不得覆盖当前标准或成为 shadow canon。

#### Scenario: Accepted governed change reaches a stable record
- **WHEN** B3 变更完成实现并获得 owner acceptance
- **THEN** 其 verification evidence 完整，accepted delta spec 先同步到 `openspec/specs/`，再归档 change

#### Scenario: Historical material is not a current instruction
- **WHEN** 人或 AI 查阅已标记为 `Archived` 的 Harness 背景或历史过程文档
- **THEN** 该文档只能用于追溯，不能被当作当前执行规则或完成证据
