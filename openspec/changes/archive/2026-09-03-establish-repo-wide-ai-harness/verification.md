# Verification: Repo-wide AI Harness

## Status

- Harness verification schema: `v1`
- Status: `Complete`
- Disposition: `Accepted`
- Pre-apply review: `Approved`
- Owner: 用户
- Decision: 用户明确批准 apply Harness，并在实施后批准 Harness sync/archive。

## Scope

仓库级 Harness 入口、通用任务 intake、执行分级、验证状态和文档职责边界。

## Planned Checks

- 验证 `docs/harness/README.md`、`docs/README.md` 和 `AGENTS.md` 的入口链接。
- 验证当前标准和非历史文档不再引用已退役的 Runtime Harness 测试路径。
- 运行 OpenSpec strict validate 和 `git diff --check`。
- 不运行真实业务链路；本变更不改变应用运行时。

## Results

| Boundary | Command/check | Result | Evidence status |
| --- | --- | --- | --- |
| Local navigation | `uv run --frozen python scripts/check_docs.py` | `Documentation checks passed.`；验证统一入口、关键目录、当前入口引用、非历史旧 Runtime 路径和 v1 verification metadata | `local-complete` |
| Governance artifact | `openspec validate establish-repo-wide-ai-harness --strict` | change valid | `local-complete` |
| Static hygiene | `git diff --check` | passed | `local-complete` |
| Shortest chain | 文档链接和当前标准检查 | 本变更不改变应用运行时；文档门禁已覆盖其实际链路 | `chain-complete` |
| Formal / human | owner acceptance | 用户已批准 Harness sync/archive | `formal-complete` |

## Documentation Impact

- 新增 `docs/harness/README.md` 作为通用入口。
- 更新根 AI 路由、Docs 索引和当前执行标准，不改变 leaf authority order。
- 修正 Runtime Web 和 repo standard 的旧测试路径。
- `scripts/check_docs.py` 采用 opt-in Harness verification metadata v1；历史 verification 无需批量迁移。

## Uncovered Boundaries

- 各 leaf 文档的内容质量和每个服务的实际测试覆盖不在本变更范围内。
- Harness 入口不能替代具体服务标准、业务契约、部署 runbook 或 OpenSpec 验收证据。
- 历史 `Archived` 知识文档仍保留旧路径作追溯，不计入当前导航或验证依据。

## Completion

- Accepted spec 已同步到 `openspec/specs/repo-wide-ai-harness/spec.md`。
- Owner acceptance 已在本会话记录；本 change 可归档。
