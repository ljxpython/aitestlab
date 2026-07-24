## ADDED Requirements

### Requirement: OpenSpec 使用中文权威正文
仓库 SHALL 将标准 OpenSpec 产物中的中文正文作为规划、实施、验证、同步和归档的唯一权威内容。

#### Scenario: Agent 执行变更
- **WHEN** Agent 规划或 apply 一个 OpenSpec change
- **THEN** Agent 直接使用该 change 的中文权威正文

#### Scenario: 开发人员评审变更
- **WHEN** 开发人员查看 OpenSpec change
- **THEN** 开发人员与 Agent 使用同一套权威产物，无需查阅语言镜像

### Requirement: 保留 OpenSpec 机器结构
仓库 MUST 保留 OpenSpec schema 所需的英文文件名、标题关键字、场景关键字和任务复选框格式，并保留代码、路径、命令、API 与其他技术标识的英文原文。

#### Scenario: OpenSpec 校验中文产物
- **WHEN** 中文正文的 change 运行 strict validation
- **THEN** 标准 schema 能识别全部产物、requirements、scenarios 和 tasks

### Requirement: 禁止双语重复事实源
仓库 MUST NOT 为同一 OpenSpec change 维护完整英文镜像、中文镜像或 `summary.zh-CN.md`；除非未来存在另一个经治理变更批准的明确需求。

#### Scenario: 创建新的 OpenSpec change
- **WHEN** Agent 生成规划产物
- **THEN** Agent 只生成中文权威正文，不生成第二语言副本或摘要

### Requirement: Token 成本按对等内容测量
仓库 MUST 仅基于同等语义内容和实际执行模型对应 tokenizer 的计数声明语言 token 成本差异。

#### Scenario: 实际 tokenizer 可用
- **WHEN** 团队评估中文与英文的 token 成本
- **THEN** 验证记录 tokenizer、对等输入、两组计数和结果

#### Scenario: 实际 tokenizer 不可用
- **WHEN** 无法取得实际执行模型对应的 tokenizer
- **THEN** 验证记录未覆盖边界，且不声明具体成本差异
