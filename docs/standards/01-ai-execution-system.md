# AI 执行系统当前标准

- 文档类型：Current Standard
- 适用范围：仓库级 AI 任务路由、风险分级和验证门禁

本文只定义“现在必须怎么做”。背景说明见
`docs/knowledge/harness-engineering.md`，人类使用示例见
`docs/ai-execution-system-usage-guide.md`。
通用任务入口和导航见 `docs/harness/README.md`；该入口不覆盖本文或 leaf-local standard。

## 1. 权威顺序

同一问题按下面顺序解析：

1. 最窄的 leaf-local current standard
2. 本文
3. supporting knowledge / rationale
4. `.harness` 或 `openspec` 过程产物

代码是实现事实，不自动升级为标准。`.harness` 和 `openspec` 是执行工具，
不能反向覆盖 repo/leaf authority。

## 2. Intake 顺序

开始实现前依次确认：

1. **Locus**：哪个 app/service/repo surface 拥有该问题？
2. **Chain**：本地、最短相邻链，还是受治理跨边界链？
3. **Standards**：哪份最窄 leaf 文档生效？
4. **Band**：B1 Local、B2 Chain、B3 Governed？
5. **Verification**：最小充分证据是什么？

先定边界，再定流程深度。不能根据“代码多不多”选择 band。

所有 band 都必须完成同一个闭环：

```text
分析 -> 定界/分级 -> 规划 -> 必要时实施前审批 -> 实施 -> 检查 -> 验收 -> 总结
```

band 只决定过程是否持久化、验证做到多深，不决定是否分析、规划和检查。

## 3. B1 / B2 / B3

| Band | 定义 | 默认产物 | 验证 |
| --- | --- | --- | --- |
| B1 Local | 单一 locus 内闭环，不改受治理面 | 默认不落文件、不创建 OpenSpec change | local/minimal |
| B2 Chain | 单一 locus 的有意义改动，或一条最短相邻链 | 短计划；需要持久对齐时使用 OpenSpec | local + shortest chain |
| B3 Governed | 政策、公开契约、所有权、迁移、发布或跨边界风险 | OpenSpec change | 对应边界的正式证据 |

### 3.1 B1 Local

适合明确的小改动，例如局部 UI、内部 resolver、单模块 bug。

只需说明：

- Goal
- Scope
- Change
- Verify

默认直接实现，不写 PRD，不创建 OpenSpec change。

### 3.2 B2 Chain

适合需要设计或相邻服务配合，但不改变受治理面的工作。

短计划最多覆盖：

- Goal / Scope
- Owning locus / shortest chain
- Standards loaded
- Implementation steps
- Acceptance criteria
- Local + shortest-chain verification

出现以下任一情况时，B2 使用 OpenSpec change；否则计划保留在会话中或使用
一份短计划：

- 行为或验收标准需要持久评审
- 工作跨多个会话、多人协作或需要 handoff
- 现有需求文档需要转成可验证的 delta spec

如果实施中发现受治理风险，必须升级为 B3。

### 3.3 B3 Governed

以下任一条件命中时进入 B3：

- public/governed contract 或 repo/leaf policy 改变
- auth、permission、audit、data ownership 或 migration 语义改变
- 责任从一个 locus 转移到另一个 locus
- 生产发布、回滚或外部兼容需要正式评审
- 可信验收依赖用户拥有的 secret、account 或 dataset
- local + shortest-chain 无法证明结果

“需要查资料”本身不是 B3。只有调研结论将改变受治理边界时才升级。

B3 在 apply 前必须完成 proposal/specs/design/tasks 的整体 owner review，并把结果
记录到该 change 的 `verification.md`。只有 owner 明确授权的紧急或 bootstrap
waiver 可以跳过评审；waiver 的授权、原因和范围必须在 apply 前持久化。Agent
不得自行声明豁免。

## 4. OpenSpec 参与方式

OpenSpec 已在仓库初始化，使用官方 `core` profile 和默认 `spec-driven` schema。
Harness 与 OpenSpec 的职责不能混用：

- Harness 负责 locus、authority、band、验证深度和人工门禁
- OpenSpec 负责需要持久化的 change artifacts 及其生命周期
- B1 可以使用 `openspec-explore` 调研，但默认不创建 change
- B2 只在第 3.2 节的持久对齐条件命中时创建 change
- B3 实施前必须创建 change

OpenSpec 的标准产物（`proposal.md`、`specs/**/*.md`、`design.md`、`tasks.md`
和 `verification.md`）统一使用中文正文，并作为规划、实施、验证、同步和归档的
唯一权威内容。Agent 与开发人员直接读取同一套产物，不维护完整英文镜像、中文
镜像或 `summary.zh-CN.md`，避免产生重复事实源。

OpenSpec schema 需要识别的英文文件名、标题关键字、场景关键字和任务复选框格式
必须保留；代码标识、路径、命令、API 名称和其他技术标识也保留英文原文。现有
change 无需批量迁移，新建或主动更新的 change 采用本约定。任何语言 token 成本
结论都必须使用实际执行模型对应的 tokenizer 和对等语义输入测量；无法取得对应
tokenizer 时不得声称具体差异。

默认流程：

```text
proposal -> specs -> design (when needed) -> tasks
         -> owner review -> apply -> verification
         -> accepted: sync -> archive
         -> rejected/abandoned: archive without sync
```

职责映射：

| Repo concern | OpenSpec artifact |
| --- | --- |
| Why / Scope / Impact / Non-goals | `proposal.md` |
| Requirements / acceptance scenarios | `specs/<capability>/spec.md` |
| Architecture / ownership / contract decisions | `design.md`，仅需要时 |
| Implementation and verification checklist | `tasks.md` |
| Review decision and executable evidence | `verification.md` |
| Approved current capability behavior | `openspec/specs/`，accepted archive 前先 sync |

保持官方默认 `spec-driven` schema，不 fork custom schema，不重复包装官方生成的
OpenSpec Skills。只有多个真实 change 反复暴露相同缺口时才重新评估。

下列产物按条件生成，不做全家桶：

- ADR/design：存在真实架构取舍时
- dedicated Test Spec：高风险契约或复杂验证矩阵需要时
- real-input checklist：确实依赖用户输入时
- runbook：部署、运维或恢复路径改变时
- repo-level report：跨 change 汇总时

同一 change 不能同时维护在 `openspec/changes/` 和 `.harness/plans/`。
`.harness/plans/` 只保留历史或已明确归档的旧计划。

每个已产生 `tasks.md` 的持久化 B2/B3 change 必须同时维护 `verification.md`。
最晚在任务生成后创建验证计划，实施和检查过程中持续更新；不能用 tasks 的勾选
状态替代验证结果。

新建或主动更新的 `verification.md` 使用 `docs/harness/README.md` 定义的 Harness metadata
v1；历史 verification 不要求批量迁移，但不得作为当前状态格式的先例。

## 5. Leaf Resolver

### `platform-web`

- 页面 archetype / UI composition：
  `apps/platform-web/docs/frontend-development-playbook.md`
- 正式控制面行为：
  `apps/platform-web/docs/control-plane-page-standard.md`

### `platform-api`

- 模块与 code shape：`apps/platform-api/docs/handbook/*.md`
- permission / audit / operations：
  `apps/platform-api/docs/standards/*.md`

### `runtime-service`

- 标准：`apps/runtime-service/docs/standards/*.md`（绿色重构标准待重新生成）
- 可执行门禁：`apps/runtime-service/tests/` 中与本次 concern 对应的测试；Runtime R0-R6
  阶段证据和缺口见 `apps/runtime-service/docs/knowledge/31-runtime-refactor-alignment-audit.md`

### `runtime-web`

- `apps/runtime-web/docs/standards/runtime-web-debug-standard.md`

### `interaction-data-service`

- 当前 API：`apps/interaction-data-service/docs/test-case-service-api-design.md`
- 结果域边界：
  `apps/interaction-data-service/docs/standards/result-domain-boundary-standard.md`

只加载本次 concern 所需的最窄文档，不加载整个知识树。

## 6. Verification Doctrine

验证顺序固定为：

1. local/minimal
2. shortest relevant chain
3. formal chain only when B3 风险需要

高 band 不允许跳过低层验证；低 band 也不应默认扩大到全链路。

验证证据至少回答：

- 跑了什么
- 使用什么输入
- 结果是什么
- 哪些边界没有覆盖
- 是否需要 docs/runbook 更新

持久化证据统一放在 change 根目录的 `verification.md`，至少包含：

- Status：`Pending` 或 `Complete`
- Disposition：`Pending acceptance`、`Accepted`、`Rejected` 或 `Abandoned`
- Pre-apply review：`Pending`、`Approved` 或 `Waived`
- owner/授权或 waiver 依据
- local、shortest chain、formal/human 的命令或检查、输入和结果
- 未覆盖边界、残余风险以及 docs/runbook 决策

archive 前必须满足：

- `Accepted`：evidence 为 `Complete`，pre-apply review 为 `Approved` 或有明确
  owner 记录的 `Waived`；存在 delta specs 时必须先 sync
- `Rejected` / `Abandoned`：允许 evidence 未完成和不 sync，但 disposition 必须
  明确，不能伪装成已接受交付

## 7. 文档生命周期

文档只允许四种状态：

- **Current**：当前事实或标准
- **Supporting**：解释和使用指南
- **Draft**：未批准方案
- **Archived**：历史，不得作为当前入口

Current 文档不得包含本机绝对路径或已退役宿主名。历史计划完成或失效后必须
标记 Archived，并从 Current 指南中解除链接。

## 8. Completion Gate

完成必须满足：

- locus、chain 和 band 选择合理
- 最窄 leaf standard 已加载
- 所需验证证据存在
- B3 change 已通过实施前 review/waiver 和 verification
- accepted change 的 delta specs 已 sync，随后必须 archive
- rejected/abandoned change 已记录 disposition，随后可以无 sync archive
- docs/runbook 影响已处理或明确说明无需处理

存在需求歧义、主观产品验收、用户自有输入或受治理/生产状态变化时，必须等待
对应人工确认。`git commit` 和 `git push` 只在用户明确授权后执行。

禁止把 helper、计划、历史文档或 OpenSpec change 当成 shadow canon。
