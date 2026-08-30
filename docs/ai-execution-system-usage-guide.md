# AI 执行系统使用指南

- 文档类型：Current Usage Guide
- 面向对象：给 AI 提任务、评审方案和验收结果的人

正式规则见 `docs/standards/01-ai-execution-system.md`。本文只讲日常怎么用。

## 1. 先记住四句话

1. 先找对 locus。
2. 先读最窄 leaf standard。
3. 按风险选择 B1/B2/B3，不按代码量。
4. 先定验证，再开始实现。

## 2. 提任务时给什么

最低限度提供：

- **Goal**：希望什么结果成立
- **Scope**：这次做什么、不做什么
- **Evidence**：报错、截图、接口、相关文档或已知约束
- **Real inputs**：是否需要账号、密钥、模型、数据集或环境参数
- **Delivery**：先调研、先规划，还是直接实现

不知道的内容可以明确写“待确认”，不要让 AI 编造真实输入。

## 3. AI 开始前应该回答什么

对非平凡任务，AI 先给出：

- Locus
- Affected chain
- Standards loaded
- Band
- Verification plan

B1 可以一句话完成这一步；B2/B3 再按需要展开。

需要显式执行这套判断时，在 Codex 中调用：

```text
$route-project-change <你的任务描述>
```

这个 Skill 只在显式调用时触发，固定输出下面五个字段并选择 B1/B2/B3；需要
持久化时再转给官方 OpenSpec Skills。它不会覆盖 `AGENTS.md` 或 leaf standard。

常用写法：

```text
# 只判断，不实施
$route-project-change 只做路由判断：修复项目列表页的按钮间距

# 判断后按合适流程继续实施
$route-project-change 判断并按合适流程实施：前端展示 API 已有的 status 字段

# 明确要求正式治理流程
$route-project-change 按 B3 路由：修改项目删除接口的权限和审计行为
```

新增或更新项目 Skill 后，需要重新启动一次 Codex，让它重新扫描 `.codex/skills/`。

### 3.1 五个字段的白话解释

可以把这五个字段理解成开工前必须回答的五个问题：

| 字段 | 白话问题 | 实际含义 | 常见错误 |
| --- | --- | --- | --- |
| **Locus** | 这件事主要归谁管、应该改在哪里？ | 对结果负责的 app/service/repo surface，例如 `platform-web` 或 `runtime-service` | 把所有可能改到的目录都列成 locus；实际上 locus 是主要 owner |
| **Affected chain** | 这个改动真正会经过谁、影响谁？ | 从入口到结果的最短真实调用、数据或契约链 | 把五个服务全部列上；没有经过的服务不算 affected chain |
| **Standards loaded** | 开工前实际读了哪些生效规则？ | 本次已经加载的最窄 leaf standard，以及确有需要的 repo standard | 写“已读文档”却不列路径，或者把整个 `docs/` 全读一遍 |
| **Band** | 这件事要用多重的流程？ | 根据边界和风险选择 B1 Local、B2 Chain 或 B3 Governed | 按代码行数、开发天数或优先级选 Band |
| **Verification plan** | 做完拿什么证明真的好了？ | 开工前约定的最小充分证据，包括 local、shortest chain 和必要的 formal/human proof | 写完代码才临时想怎么测，或者小改动默认跑整条系统 |

一句话记忆：

```text
Locus 定主人，Affected chain 定影响范围，Standards loaded 定规则，
Band 定流程深度，Verification plan 定完成证据。
```

判断顺序不能反过来。先确定 locus 和 affected chain，才能知道该读哪些
standards；读完规则后再选 Band，最后写出与影响范围匹配的 verification plan。

### 3.2 案例一：调整前端按钮间距

```text
Locus: apps/platform-web
Affected chain: platform-web 页面/组件内部
Standards loaded: apps/platform-web/docs/frontend-development-playbook.md
Band: B1 Local
Verification plan: 运行相关 lint/typecheck；检查目标页面桌面和移动视口截图
```

解释：虽然用户能看到变化，但没有改接口、权限或跨服务行为。前端自己能闭环，
所以是 B1，不需要 OpenSpec change。

### 3.3 案例二：修复 Runtime 内部 resolver 的空值 bug

```text
Locus: apps/runtime-service
Affected chain: runtime-service 内部 resolver -> 调用方
Standards loaded:
  - apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md
  - 与该 resolver 所属模块最相关的 leaf playbook
Band: B1 Local
Verification plan: 先写/运行复现空值的局部测试；再运行 resolver 相关测试
```

解释：要检查共享调用方，避免只修表面症状；但只要行为没有越过 Runtime 的公开
契约边界，仍然是 B1。

### 3.4 案例三：前端展示后端已有字段

```text
Locus: apps/platform-web
Affected chain: platform-web typed client -> platform-api 现有 endpoint
Standards loaded:
  - apps/platform-web/docs/frontend-development-playbook.md
  - apps/platform-web/docs/control-plane-page-standard.md
  - apps/platform-api/docs/handbook/development-playbook.md
Band: B2 Chain
Verification plan:
  - local: 前端组件/类型检查
  - shortest chain: 使用 platform-api 的真实响应验证字段展示、空态和错误态
```

解释：字段已经由后端提供，公开契约没有变化，但可信结果需要前后端最短链路，
所以是 B2。单次会话能完成时可只用短计划；需要评审或 handoff 时再创建
OpenSpec change。

### 3.5 案例四：修改平台接口的权限和审计行为

```text
Locus: apps/platform-api
Affected chain: platform-web action -> platform-api route/use case -> permission -> audit
Standards loaded:
  - apps/platform-api/docs/standards/permission-standard.md
  - apps/platform-api/docs/standards/audit-standard.md
  - apps/platform-web/docs/control-plane-page-standard.md
Band: B3 Governed
Verification plan:
  - local: permission allow/deny 和 audit event 单元测试
  - shortest chain: 前端动作到 API 的允许、拒绝和错误响应
  - formal/human: 审核公开行为、审计字段、兼容性和回滚方式
```

解释：即使最终只改几行代码，只要权限或审计语义变化就是受治理面，必须先创建
OpenSpec change，评审 proposal/spec/design/tasks 后再实施。

## 4. 快速选择 Band

### B1 Local

使用条件：

- 单一 locus
- 不改受治理契约
- 不涉及权限、数据所有权、迁移或发布风险
- 本地证据足够

交付方式：在会话中完成 Goal / Scope / Change / Verify，直接修改并给出本地
验证结果。可以调用 `openspec-explore` 帮助分析，但默认不创建 OpenSpec change。

例子：

- 修复一个页面局部样式
- 修复 runtime 内部 resolver 的明确 bug
- 更新不改变行为的局部文案

### B2 Chain

使用条件：

- 有一定设计或拆解
- 仍在一个 locus，或只需要一条最短相邻链
- 不改变 public/governed surface

交付方式：分析 -> 短计划 -> 实现 -> local + shortest-chain verification。

以下情况使用 OpenSpec change 持久化 B2：

- 行为或验收标准需要评审
- 工作跨多个会话、多人协作或需要 handoff
- 需要把现有需求转成可验证的 delta spec

否则短计划保留在当前会话中，不额外制造文件。

例子：

- 前端适配后端已有字段
- 平台 API 内部模块重组但不改变公开行为
- runtime-web 对现有 runtime contract 的调试能力适配

### B3 Governed

使用条件：

- 改公开契约、权限、审计、数据所有权或迁移
- 改 repo/leaf standard
- 改跨服务 owner 边界
- 涉及正式发布、回滚或外部兼容
- 可信验收依赖用户拥有的真实输入

交付方式：使用 OpenSpec proposal/spec/design/tasks，owner 整体评审并记录到
`verification.md` 后才能 apply；实施后补齐证据，accepted change 先 sync 再 archive。

例子：

- 新增正式平台管理接口
- 修改 RuntimeContext 公开字段
- 调整平台到结果域的访问责任
- 修改本仓 Harness 标准

调研本身不自动等于 B3；看调研结论是否改变受治理边界。

## 5. OpenSpec 怎么参与

仓库已经使用官方 `core` profile 和默认 `spec-driven` schema 初始化。OpenSpec
生成的 6 个 Codex Skills 是：

- `openspec-explore`：只分析和澄清，不实施代码
- `openspec-propose`：创建 change 并生成规划产物
- `openspec-update-change`：修订已有 change 产物
- `openspec-apply-change`：按 tasks 实施并更新清单
- `openspec-sync-specs`：把 delta specs 同步到 current specs
- `openspec-archive-change`：完成验证后归档 change

Codex 以 `.codex/skills/openspec-*` 为仓库内可移植入口。可以直接用自然语言
要求调用对应 Skill；具体斜杠形式以当前 Codex 自动补全为准。

日常最小流程：

```text
分析不确定问题：openspec-explore
创建持久变更：openspec-propose <change-name>
创建 verification.md 并写验证计划
B3 owner review：Approved；或记录明确授权的 Waived
实施：openspec-apply-change <change-name>
完成 Harness 验证并把证据写入 verification.md
Accepted 且有 delta specs：openspec-sync-specs <change-name>
最后归档：openspec-archive-change <change-name>
```

终端中的 `openspec` CLI 用于初始化、检查和维护，不要把聊天 Skill 当成终端
命令：

```bash
npm install --global @fission-ai/openspec@latest
openspec update
openspec list
openspec status --change <change-name>
openspec validate --all --strict --no-interactive
```

`core` profile 没有单独的 verify Skill。本仓库仍按 local -> shortest chain ->
formal 的 Harness 规则验证，并把命令、输入、结果、未覆盖边界和文档影响写入
`verification.md`；不要因为 OpenSpec tasks 全部勾选就宣称完成。

OpenSpec 负责 change lifecycle；下面这些仍由仓库 Harness 负责：

- locus 和 owner 判断
- leaf authority
- B1/B2/B3 选择
- 最小/最短链/正式链验证顺序
- secrets 和真实输入门禁

人工门禁放在真正需要决策的位置：

- B3 在 apply 前整体评审 proposal/spec/design/tasks，并记录 `Approved`
- 只有 owner 明确授权并记录原因、范围的 `Waived` 才能跳过；Agent 不能自批
- 主观 UI、产品行为或真实账号/数据需要 owner 验收
- 权限、迁移、发布和回滚需要对应 owner 确认
- accepted archive 前必须完成 evidence；有 delta specs 时先 sync
- 不 sync 的 archive 只能标记为 `Rejected` 或 `Abandoned`
- `git commit` 和 `git push` 必须由用户明确授权

不要 fork schema，不要修改 OpenSpec 自动生成的 Skill，也不要在
`.harness/plans/` 再复制一套 PRD/TODO。多个真实 change 反复暴露同一缺口后，
再评估自定义 schema。

### 5.1 OpenSpec 文档语言

OpenSpec 标准产物使用中文正文，开发人员和 LLM 直接读取同一套权威内容。不要
再生成完整英文镜像、中文镜像或 `summary.zh-CN.md`，否则既增加上下文成本，又
制造容易漂移的第二份事实源。

下列机器结构和技术标识仍保留英文：

- 标准文件名，例如 `proposal.md`、`design.md`、`tasks.md`
- schema 关键字，例如 `## ADDED Requirements`、`### Requirement:`、
  `#### Scenario:`、`WHEN` 和 `THEN`
- 任务复选框格式 `- [ ]`
- 代码标识、路径、命令、API 名称和协议字段

示例：

```markdown
## ADDED Requirements

### Requirement: 用户可以导出数据
系统 SHALL 允许用户导出 CSV 文件。

#### Scenario: 导出成功
- **WHEN** 用户点击“导出”
- **THEN** 系统下载包含用户数据的 CSV 文件
```

现有 change 无需批量迁移；新建或主动更新的 change 采用中文正文。是否增加或
减少 token，必须用实际模型 tokenizer 对同等语义的中英文内容测量；没有测量就
不要写具体差异或百分比。

## 6. Ponytail 和 Caveman 怎么参与

它们都不是 Harness 或 SDD 框架，也不管理 OpenSpec change：

| 工具 | 作用 | 推荐默认状态 | 自动触发 |
| --- | --- | --- | --- |
| Ponytail | 用 YAGNI/KISS 约束设计和实现，优先复用、标准库和最小改动 | 编码、设计、重构和代码评审时启用 | 相关编码任务可由 Codex 自动匹配；需要确定性时显式调用 |
| Caveman | 压缩回复文字，减少 token，不改变代码或流程 | 默认关闭 | 普通编码任务不会自动启用；明确要求简短、节省 token 或调用 `/caveman` 时触发 |

推荐组合：

```text
Harness：决定任务边界、Band、验证和人工门禁
OpenSpec：管理需要持久化的 B2/B3 change
Ponytail：约束实现不要过度设计
Caveman：只在需要时压缩沟通输出
```

Skill 的自动匹配由 Codex 根据名称和 description 判断，不是可依赖的强制门禁。
关键任务可以直接说“使用 Ponytail full”或“使用 Caveman full”。任一模式激活后，
默认持续到当前会话结束；说“stop ponytail”“stop caveman”或“normal mode”可以关闭。

Ponytail 和 Caveman 可以同时使用：前者决定“做多少”，后者决定“说多少”。它们
都不得跳过安全检查、输入验证、测试、OpenSpec artifacts 或人工确认。

## 7. 三种常用提问方式

小改动：

> 先确认 locus 和 B1 条件；若不触及受治理面，直接实现并给出本地验证。

普通需求：

> 先给出 locus、最短影响链、standards loaded、B1/B2/B3 和验证计划；按最轻安全流程执行。

需要持久评审的普通变更：

> 按 B2 处理并创建 OpenSpec change。先写清可验证行为、最短影响链和验收标准，评审后实施。

正式变更：

> 按 B3 处理。先创建 OpenSpec proposal/spec/tasks，列出受影响契约和真实输入，评审通过后再实施。

## 8. 文档入口

- AI 路由：`AGENTS.md`
- 正式执行标准：`docs/standards/01-ai-execution-system.md`
- Harness 概念：`docs/knowledge/harness-engineering.md`
- Leaf 标准：各 app/service 自己的 `docs/standards/`
- B1/B2 轻量 helper：`.harness/templates/ai-execution-system/`
- 持久化 B2/B3 lifecycle：`openspec/`
- OpenSpec Codex Skills：`.codex/skills/openspec-*/`
- 显式 Harness 路由 Skill：`.codex/skills/route-project-change/`

## 9. 验收时问什么

- 是否改在正确 locus？
- 是否加载了正确 leaf standard？
- band 是否过重或过轻？
- 是否先完成 local proof？
- 验证是否覆盖真实受影响边界？
- 是否留下重复、过期或不可移植文档？

只要这六个问题有清楚答案，Harness 就在工作。
