## Why

OpenSpec 产物主要由中文开发团队评审和使用；采用英文权威文档再补中文摘要，会增加维护成本并产生内容漂移。仓库需要使用一套中文权威内容，同时保留 OpenSpec 必需的英文结构关键字和技术标识。

## What Changes

- OpenSpec 规划、实施、验证、同步和归档所使用的标准产物统一采用中文正文。
- OpenSpec schema 要求的标题、关键字、文件名、路径、命令、代码标识和 API 名称保留英文。
- LLM 直接读取并执行中文权威产物，不再生成或维护英文镜像与 `summary.zh-CN.md`。
- token 成本只作为实测信息，不作为选择文档语言的前提。
- 保持官方 `spec-driven` schema、标准文件名和生命周期不变。
- 非目标：完整双语镜像、自动翻译服务、自定义 OpenSpec schema。

## Capabilities

### New Capabilities

- `openspec-language-policy`：规定 OpenSpec 中文权威正文、必须保留的英文机器结构，以及单一事实源原则。

### Modified Capabilities

无。

## Impact

- Owning locus：仓库级 OpenSpec 与 AI 执行系统。
- Affected chain：`openspec/config.yaml` 和仓库指南 → 产物生成 → LLM apply 上下文 → 开发人员评审。
- Band：B3 Governed，因为本变更修改仓库级 AI 执行政策。
- Standards loaded：`AGENTS.md`、`docs/standards/01-ai-execution-system.md`。
- 预计影响：仓库 AI 执行标准、使用指南和 OpenSpec 项目上下文。
- 兼容性：标准文件名和结构关键字不变；现有 change 无需批量迁移。
- 回滚：撤销语言政策即可，不涉及运行时或数据回滚。
