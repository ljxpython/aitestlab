# Harness Engineering 在本仓库中的含义

- 文档类型：Supporting Knowledge
- 状态：Current

## 1. 定义

Harness 是围绕人和 AI 的工程操作系统，不是单个 prompt、测试工具或目录。

它负责让任务在稳定边界内完成：

- 入口清楚
- owner 清楚
- 契约清楚
- 验证清楚
- 失败可以定位
- 过程可以交接

Prompt 决定这次让模型做什么；Context 决定模型看见什么；Harness 决定模型
在什么规则、环境和反馈回路里工作。

## 2. 本仓库为什么需要 Harness

这是一个多服务 Agent 平台：

```text
platform-web -> platform-api -> runtime-service -> interaction-data-service
runtime-web ------------------> runtime-service
```

平台治理、Runtime 执行、调试入口和结果域有不同 owner。AI 如果不先识别
locus，很容易把权限写进 Runtime、把 Agent 逻辑写进平台，或用全链路验证
替代本地排查。

## 3. 五个核心机制

### Locus-first

先确认问题属于哪个 app/service，再选择流程。边界比任务大小重要。

### Leaf authority

最窄的 app-local current standard 优先。repo standard 只处理跨 leaf 路由和升级。

### Progressive execution

- B1 Local：单一 locus 的最小闭环
- B2 Chain：单一 locus 或最短相邻链
- B3 Governed：受治理边界和正式变更生命周期

### Progressive verification

```text
local/minimal -> shortest relevant chain -> formal chain when required
```

高风险任务仍要先通过本地证明；低风险任务不默认跑全链。

### Canon/helper separation

- `docs/standards/` 和 leaf standards：当前规则
- `docs/knowledge/`：原因和背景
- `.harness/`：模板、历史计划和 repo 级报告
- `openspec/`：需要持久评审的 B2 和全部 B3 change lifecycle

Helper 不能成为 shadow canon。

## 4. Harness 不是什么

- 不是要求每个任务都写 PRD
- 不是把所有调研都升级成正式流程
- 不是让 AI 读取整个文档树
- 不是用文档替代自动测试
- 不是让 OpenSpec 取代 Harness 的路由、风险分级和验证门禁

好的 Harness 应该让小任务更快、重大变更更可控。

## 5. 成熟度标准

Harness 变好时应该出现：

- active 文档更少、更短
- 当前和历史状态可识别
- 约束尽量由测试和 CI 执行
- B1 不产生过程文件
- B2 只验证最短链
- B3 change 可以评审、验证和归档

如果每次改动都要读很多文档、填很多字段、跑整条链，说明 Harness 已经从
保护机制变成流程负担。

## 6. 当前入口

- AI 路由：`AGENTS.md`
- 正式规则：`docs/standards/01-ai-execution-system.md`
- 人类指南：`docs/ai-execution-system-usage-guide.md`
- Leaf 标准：各 app/service 自己的 `docs/`

历史长篇说明保留用于追溯，但不再属于默认阅读路径。
