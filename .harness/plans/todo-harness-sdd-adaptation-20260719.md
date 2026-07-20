# Harness + SDD 适配 TODO

> Status: Archived. Superseded by `openspec/changes/adopt-openspec-harness/`.

## 已完成

- [x] 建立 `feat/harness-sdd-optimization` 分支
- [x] 核对 repo/leaf authority、B1-B3、L1-L4 和 `.harness` helper 边界
- [x] 分析现有 PRD/Test Spec/TODO/verification 产物链
- [x] 对照 OpenSpec 与 Spec Kit 官方工作流
- [x] 记录选型、权威矩阵、试点验收和退出条件

## 等待用户授权

- [ ] 安装 OpenSpec CLI
- [ ] 初始化 `openspec/`
- [ ] 使用官方默认 `spec-driven` schema
- [ ] 配置 repo context、authority rules 和 B3-only routing
- [ ] 选择一个真实 B3 变更完成试点
- [ ] 按 Test Spec 验证 validate、tracking、verification、archive 和 protocol-only 回归

## 试点通过后

- [ ] 更新 `docs/standards/01-ai-execution-system.md`
- [ ] 更新 `docs/ai-execution-system-usage-guide.md`
- [ ] 更新 `.harness/README.md`，明确 `.harness/plans/` 的历史/非重复策略
- [ ] 决定是否把 OpenSpec 纳入默认开发环境
- [ ] 仅在 2-3 个真实 B3 change 反复缺少专用 artifact 时评估 custom schema
