## Why

当前 Harness 规则、理念、使用指南和 Runtime/Platform 验收资料分布在多个目录，虽然职责已经分层，但缺少一个明确的仓库级入口；同时部分标准仍保留过期的 Runtime 测试路径。现在需要把 Harness 提升为适用于前端、Platform API、Runtime、数据服务、部署和发布的通用 AI 工程范式，避免它被误解成 R0-R6 专用流程。

本变更属于 B3 Governed，owner locus 是仓库级 AI 执行系统，最短影响链是 `AGENTS.md -> docs/harness/README.md -> repo/leaf standards -> verification evidence`。

## What Changes

- 新增 `docs/harness/README.md` 作为 Harness 的唯一仓库级导航入口。
- 明确 Harness 的通用模型：Goal、Locus、Chain、Authority、Band、Evidence、Acceptance。
- 明确 Harness 与 `docs/standards/`、`docs/knowledge/`、服务文档、测试、交付清单和 OpenSpec 的职责边界。
- 将 R0-R6 定义为 Runtime 领域的一个应用实例，不再作为 Harness 的上位定义。
- 在根文档索引和 AI 执行入口中链接统一 Harness 入口。
- 修正正式执行标准中已过期的 Runtime 测试路径，指向当前 `apps/runtime-service/tests/`。
- 不迁移历史 Harness 文档，不复制现有标准内容，不新增第二套执行规则。

## Capabilities

### New Capabilities

- `repo-wide-ai-harness`: 提供仓库级 AI 任务路由、风险分级、验证深度和验收闭环的通用范式与唯一入口。

### Modified Capabilities

- 无。此次只新增仓库级 Harness 能力和导航，不修改现有业务 API 或服务运行时契约。

## Impact

- **Standards**：`docs/standards/01-ai-execution-system.md`，修正过期路径并补充统一入口关系。
- **Navigation**：`docs/README.md`、`AGENTS.md`，增加 Harness 入口和最短阅读路径。
- **New docs**：`docs/harness/README.md`。
- **Verification**：新增入口、链接、状态和过期路径检查；运行 OpenSpec 严格校验与文档差异检查。
- **Compatibility**：不改变应用 API、数据库、部署方式、GraphHarbor 或任何业务代码。
- **Rollback**：删除新增入口并恢复标准/索引中的导航和路径文字即可回滚。
