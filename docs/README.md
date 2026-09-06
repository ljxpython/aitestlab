# Docs 文档导航

目标：让人和 AI 只读取当前任务需要的最小文档集合。

## 1. 开始一个任务

按顺序读取：

1. [Root AGENTS Routing Surface](../AGENTS.md)
2. [仓库级 Harness](./harness/README.md)
3. 最窄的 app/service leaf standard
4. [AI 执行系统当前标准](./standards/01-ai-execution-system.md)（跨 leaf 路由或治理升级时）

人类使用示例见 [AI 执行系统使用指南](./ai-execution-system-usage-guide.md)。

不要默认读取整个 `docs/` 或 `docs/knowledge/`。

## 2. 理解 Harness

唯一导航入口：

- [仓库级 Harness](./harness/README.md)

当前简明背景：

- [Harness Engineering 在本仓库中的含义](./knowledge/harness-engineering.md)

Runtime 的 R0-R6 是领域实例，其设计和证据看
`apps/runtime-service/docs/knowledge/31-runtime-refactor-alignment-audit.md`，不定义仓库级
Harness。

以下长篇文档已退出默认阅读路径，仅作历史背景：

- `knowledge/01-harness-engineering-foundation.md`
- `knowledge/02-aitestlab-harness-blueprint.md`
- `knowledge/03-harness-operating-model.md`
- `knowledge/04-ai-execution-system-rationale.md`
- `development-paradigm.md`

## 3. 启动、部署和运维

- [本地开发说明](./local-dev.md)
- [环境变量矩阵](./env-matrix.md)
- [部署文档](./deployment-guide.md)
- [本地部署契约](./local-deployment-contract.yaml)
- [容器化交付指南](../deploy/README.md)
- [从零到一容器化部署](./zero-to-one-container-deploy.md)
- [容器更新 Runbook](./runbooks/container-update-runbook.md)

## 4. 变更与发布

- [提交与 Changelog 规范](./commit-and-changelog-guidelines.md)
- [更新日志](./CHANGELOG.md)
- [发布记录](./releases/)

需要持久评审的 B2 变更和全部 B3 变更使用 `openspec/changes/` 管理。历史
`.harness/plans/` 不再作为 active change 的位置。

当前 Draft 方案：

- [Platform Runtime Integration 项目文档](./platform-runtime-integration/README.md)：Harness intake、决策记录、实施计划和证据状态。
- [Platform Runtime Integration 专项](../apps/runtime-service/docs/knowledge/platform-runtime-integration/README.md)
- [React Agent Web 重设计](./agent-web-redesign/README.md)

## 5. 文档状态

文档状态定义和更新顺序见
[Documentation Maintenance Note](./documentation-maintenance-note.md)。

- **Current**：当前事实或标准
- **Supporting**：解释或使用指南
- **Draft**：未批准方案
- **Archived**：历史，不得作为当前入口

Current 文档不得包含本机绝对路径或已退役宿主名。

## 6. 权威原则

- “现在必须怎么做”：`standards/` 或 app-local leaf standard
- “为什么这么做”：`knowledge/`
- “怎么启动/排障”：`runbooks/` 和 operational docs
- “历史发生过什么”：`releases/`、archive 或 Archived 文档

历史和 helper 可以提供上下文，但不能覆盖 Current 标准。
