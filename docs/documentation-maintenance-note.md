# Documentation Maintenance Note

- 文档类型：Maintenance Standard
- 状态：Current

## 1. 文档状态

每份受治理文档应能明确归入一种状态：

- **Current**：当前标准、事实、接口或操作入口
- **Supporting**：解释、示例和使用指南
- **Draft**：未批准方案，不能当作实现依据
- **Archived**：历史记录，不能作为当前入口

Archived 文档应在开头指出当前替代文档。历史命名可以保留，但只能出现在
Archived、release 或 archive 路径中。

## 2. 权威位置

- repo 执行标准：`docs/standards/`
- app/service 标准：leaf 自己的 `docs/standards/` 或明确标记的 current doc
- 部署事实：contract + current deployment/runbook
- 背景知识：`docs/knowledge/`
- 历史：`docs/archive/`、`docs/releases/` 或明确标记 Archived 的文件
- 持久化 B2/B3 change：使用 `openspec/`

`.harness` 是 helper/report/history host，不定义业务政策。

## 3. 更新顺序

当正式链路、宿主、端口、契约或默认入口变化时：

1. code / schema / executable contract
2. canonical contract and standards
3. app current docs
4. runbook / operational guide
5. supporting knowledge and diagrams
6. archive completed change artifacts

不要先改知识说明，再让 current docs 追赶。

## 4. Current 文档要求

Current 文档必须：

- 使用仓库相对链接
- 不包含 `/Users/<name>/...` 本机路径
- 不引用已退役宿主名作为当前事实
- 明确自己的 owner/scope 或能从目录确定 owner
- 与代码、contract 和 leaf standard 对齐
- 避免重复定义另一个 current standard 已经拥有的规则

## 5. 计划生命周期

- active change 只有一个产物源
- B1 默认不创建计划文件
- B2 默认使用会话内短计划；持久评审、多会话或 handoff 时使用 OpenSpec
- B3 必须使用 OpenSpec change
- `.harness/plans/` 只允许 Archived 文件；CI 拒绝新的 active plan
- 已产生 `tasks.md` 的持久 change 必须维护 `verification.md`
- accepted change 有 delta specs 时必须先 sync 再 archive
- 不 sync 的 archive 只能是明确记录的 Rejected 或 Abandoned
- 完成、取消或被替代的计划必须标记 Archived
- Current guide 可以链接 Archived 作为历史，但必须明确标注，不得称为“当前跟踪面”

## 6. Diagram 规则

正式架构图变更时，source 与 export 必须同时更新。更新后扫描：

- 旧宿主名
- 旧端口
- 旧链路
- SVG fallback 文本
- draw.io XML 标签

## 7. 自动门禁

CI 至少检查：

- Markdown 中的本机绝对路径
- 非历史文档中的退役宿主名

自动检查负责确定性规则；“哪份文档应该是 Current”仍由 owner 评审决定。

## 8. 最小审查清单

- 当前入口是否唯一？
- leaf authority 是否仍靠近代码？
- 当前与历史是否明确分开？
- 链接是否可在其他机器使用？
- 计划是否在完成后归档？
- 文档规则是否能转成测试或 CI？

原则：保留有价值的历史，但缩短当前阅读路径。
