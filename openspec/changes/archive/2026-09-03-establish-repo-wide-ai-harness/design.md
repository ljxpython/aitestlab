## Context

当前仓库已经有根级 AI 执行标准、使用指南、Harness 知识文档、各服务标准、阶段审计、交付清单和 OpenSpec。它们的职责可以分开，但入口不够明显，且 Runtime 标准中残留过期测试路径。R0-R6 是 Runtime 的领域计划，不应继续承担仓库级 Harness 的定义。

本变更只调整仓库级导航和范式表达，不改变任何应用 API、数据库、部署拓扑或 GraphHarbor 通用代码。

## Goals / Non-Goals

**Goals:**

- 建立 `docs/harness/README.md` 作为唯一总入口。
- 用通用的七个 intake 维度统一前端、后端、Runtime、数据、部署和发布任务。
- 保留 authority separation：服务规则仍归服务，变更生命周期仍归 OpenSpec。
- 修正当前标准中的 Runtime 测试路径，并为入口提供可验证链接。

**Non-Goals:**

- 不把所有 Harness 文档搬到 `docs/harness/`。
- 不迁移或删除历史文档，不重写现有服务标准。
- 不为 Harness 新增框架、CLI、依赖、CI 平台或测试 runner。
- 不把 R0-R6 扩展成全仓库阶段，也不修改 GraphHarbor、Runtime 或业务 API。

## Decisions

### Decision: Add a navigation entry instead of centralizing all documents

新增短入口而不是合并文档。入口只承载定义、阅读顺序、分类规则和链接；详细规则保留在现有权威文件中。

备选方案是把所有文档搬进 `docs/harness/`，但会制造新的重复真源、增加维护成本，也会让服务标准脱离 owner 边界，因此不采用。

### Decision: Use one generic intake model across domains

统一使用 Goal、Locus、Chain、Authority、Band、Evidence、Acceptance。它们描述任务治理所需的信息，而不是 Runtime 特有字段；R0-R6 只作为 Runtime 的示例或证据集合。

备选方案是为每个 app 建一套独立流程，但这会让跨服务任务重复学习多个入口，且无法稳定判断 owner 和验证深度，因此不采用。

### Decision: Keep progressive verification and explicit status vocabulary

验证按最小充分证据递进，真实依赖不可用时保留 blocked/deferred。这样本地测试、mock、真实链路和正式验收不会被混为同一等级。

备选方案是规定所有任务都跑全量或真实环境；这会增加无意义成本，并不能提高局部任务的证据质量，因此不采用。

### Decision: Correct stale references in current standards only

只修正当前有效标准中指向已不存在路径的引用，历史文档和归档资料保留原貌，以免破坏历史追溯。

## Risks / Trade-offs

- [入口仍依赖链接维护] -> 在文档测试中检查入口链接、关键目录和禁止的过期路径。
- [通用范式被误解为强制所有任务创建 OpenSpec] -> 入口明确 B1 默认不创建，只有 B2/B3 的持久化条件才使用 OpenSpec。
- [状态词被滥用] -> 验收要求同时记录证据等级、未覆盖边界和 blocked/deferred，不以 checkbox 单独证明完成。

## Migration Plan

1. 新增 Harness 总入口并更新根索引和 `AGENTS.md`。
2. 修正当前标准中的 Runtime 测试路径。
3. 运行文档链接/过期路径检查、OpenSpec strict validate 和 `git diff --check`。
4. 若发现导航问题，删除新增入口并恢复受影响链接即可回滚；不涉及数据库或运行时迁移。

## Open Questions

- 后续是否需要把相同的入口链接补到更多 leaf-local README，由各服务 owner 在实际使用中决定；本变更不批量修改所有服务文档。
