# Harness + SDD 适配试点 Test Spec

> Status: Archived. Superseded by `openspec/changes/adopt-openspec-harness/`.

- 对应决策：`.harness/plans/prd-harness-sdd-adaptation-20260719.md`
- Execution band：B3

## Verification Matrix

| Proof level | Check | Pass condition |
| --- | --- | --- |
| Local | OpenSpec config validate | 默认 `spec-driven` 配置无错误 |
| Local | artifact dependency check | proposal -> specs -> design（按需）-> tasks 顺序可执行 |
| Local | authority scan | OpenSpec 文件不声明覆盖 repo/leaf standards |
| Shortest chain | one B3 pilot change | 变更可以从 proposal 走到 implementation tracking |
| Formal | verification + archive | 验证证据保留，archive 后 capability spec 正确更新 |
| Regression | protocol-only walkthrough | 不调用 OpenSpec 时 B1/B2 与现有 B3 grammar 仍可工作 |

## Required Cases

### T1 - B1/B2 无侵入

- 输入：一个单 leaf 小改动和一个最短链改动。
- 预期：仍按现有模板执行，不创建 OpenSpec change。

### T2 - B3 单一产物源

- 输入：一个需要调研或跨边界的正式变更。
- 预期：所有进行中产物只存在于一个 `openspec/changes/<id>/`，不复制到 `.harness/plans/`。

### T3 - Authority 冲突保护

- 输入：change spec 与 leaf standard 不一致。
- 预期：停止实施并升级到 leaf/current-standard，不允许 OpenSpec 静默覆盖。

### T4 - 验证闭环

- 输入：已完成 tasks 的试点变更。
- 预期：tasks 中的验证项和所需测试未通过时不得 archive；不强制独立 `verification.md`。

### T5 - 可逆性

- 输入：移除 OpenSpec 命令和试点配置后的仓库。
- 预期：现有 AGENTS 路由、标准解析和 helper 模板仍可独立使用。

## Failure Conditions

- 生成第二套 constitution 或项目标准。
- 同一变更出现两套 PRD/TODO/verification。
- B1/B2 被强制要求创建 OpenSpec change。
- archive 导致 leaf contract 与 capability spec 漂移。
- 工具不可用时现有 Harness 无法继续执行。

## Evidence To Capture

- OpenSpec 版本和初始化命令。
- schema/config validate 输出。
- 试点 change 的 artifact dependency 状态。
- 实施前后 authority/residue scan。
- verification 和 archive 输出。
- protocol-only 回归记录。
