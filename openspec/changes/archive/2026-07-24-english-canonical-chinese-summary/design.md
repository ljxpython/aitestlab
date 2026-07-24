## Context

OpenSpec 使用固定产物和 schema 关键字，但正文语言由仓库决定。团队希望所有人员都能直接查看和维护权威内容，因此不再采用“英文权威 + 中文摘要”的双层方案。本变更只涉及仓库政策，不改变任何应用服务边界。

## Goals / Non-Goals

**Goals：**

- 让开发人员和 LLM 使用同一套中文权威内容。
- 保持 OpenSpec 官方 `spec-driven` schema 可解析、可校验。
- 消除英文镜像或中文摘要造成的重复事实源。

**Non-Goals：**

- 翻译代码、API、命令、路径或 schema 关键字。
- 保证中文对所有模型都更省 token。
- 引入翻译依赖或自定义 schema。

## Decisions

1. 标准 OpenSpec 产物使用中文正文并作为唯一权威来源。LLM 与开发人员读取同一份内容，避免双语同步。
2. schema 需要识别的英文结构保持不变，包括标准文件名、`## ADDED Requirements`、`### Requirement:`、`#### Scenario:`、`WHEN`、`THEN` 和任务复选框格式。技术标识也不翻译。
3. 不创建 `summary.zh-CN.md` 或英文镜像。之前的摘要方案被否决，因为全部人员直接读取中文权威产物后，摘要只会增加重复内容。
4. token 成本不决定语言政策。若需要评估，只能对等语义内容使用实际模型 tokenizer 测量，并明确 tokenizer 差异。
5. 不修改官方 OpenSpec Skills 或 fork schema；语言要求放在仓库标准和 `openspec/config.yaml` 的共享 context 中。

## Risks / Trade-offs

- [中文正文可能比英文消耗更多 token] → 以实际 tokenizer 测量；优先保证单一事实源和团队可读性。
- [翻译 schema 关键字导致校验失败] → 明确保留机器关键字，并运行 strict validation。
- [既有英文 change 风格不一致] → 不批量迁移；新建或主动更新时采用中文正文。
- [LLM 对中文技术描述理解偏差] → 保留代码标识、接口名称、命令和关键术语的英文原文。

## Migration Plan

1. 更新仓库标准、使用指南和 OpenSpec 项目 context。
2. 删除本 change 的 `summary.zh-CN.md`，并把现有规划产物改为中文正文。
3. 验证 schema、apply context 和文档政策。
4. 新建或主动更新的 change 采用新政策，不批量重写历史内容。
5. 回滚时撤销政策文本；标准 OpenSpec 生命周期无需迁移。

## Open Questions

无。
