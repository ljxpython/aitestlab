# AI Execution System Rationale（Locus-First AI 执行系统的知识说明）

> 状态：Archived Knowledge。当前简明说明见 `docs/knowledge/harness-engineering.md`，
> 正式规则见 `docs/standards/01-ai-execution-system.md`。

文档类型：`Knowledge`

本文是对已批准的 locus-first AI execution system 的知识说明，不是可执行的标准文档，也不是门禁定义。

## 这篇文档解决什么问题

仓库已经有了足够多的“为什么”：

- `01-harness-engineering-foundation.md` 解释 Harness Engineering 是什么
- `02-aitestlab-harness-blueprint.md` 解释仓库级 Harness 怎么分层
- `03-harness-operating-model.md` 解释团队和 AI 代理应该按什么顺序做事
- `docs/development-paradigm.md` 解释当前项目的正式开发范式
- 各服务的 `docs/standards/` 解释具体层面的现行规则

现行标准已经落在 `docs/standards/01-ai-execution-system.md`；本文只解释为什么会有这套标准，以及为什么它必须是 locus-first。

所以这份文档不是再补一套哲学，而是解释：

> 为什么仓库还需要一套 AI 执行系统的 routing constitution，而不是继续堆更多方法论。

换句话说，这篇文档回答的是“为什么要有它”，不是“它怎么强制执行”。

---

## 1. 这套执行系统为什么存在

这套系统之所以需要存在，是因为前面几份文档已经把三件事讲清楚了，但还没有把它们收束成一个 AI 可用的入口顺序。

### 1.1 从 Harness Engineering 来

Harness Engineering 讲的是：

- 模型不是靠一句 prompt 变可靠的
- AI 需要被放进可运行、可验证、可恢复、可演进的工程外壳里
- 契约、验证、知识、排障、产物都必须有稳定位置

也就是说，Harness Engineering 提供的是总原则。

### 1.2 从 blueprint 来

`02-aitestlab-harness-blueprint.md` 已经说明仓库不是大泥球，而是有明确主链、调试链、知识层、runbook 层、测试层的分工。

这意味着 AI 任务不能先谈“用什么 workflow”，而要先谈：

- 这件事属于哪条链
- 由哪一层负责
- 哪些标准是 authoritative

### 1.3 从 operating model 来

`03-harness-operating-model.md` 进一步说明，工作顺序必须是：

- 层级判定
- 契约澄清
- 设计落点
- 实现
- 验证
- 文档补齐
- 交付闭环

这已经不是“多讲一点方法”，而是明确告诉我们：

> AI 的入口顺序本身就是系统的一部分。

### 1.4 从 development paradigm 来

`docs/development-paradigm.md` 则把当前项目的正式开发边界说得更具体：平台治理、runtime、调试入口、结果域服务要分开。

所以，repo 需要的不是再来一篇“我们应该认真做事”的说明，而是一套能把这些既有边界变成 AI intake 顺序的 routing constitution。

---

## 2. 为什么 repo 需要 routing constitution，而不是更多哲学

因为哲学已经够多了，缺的是入口治理。

### 2.1 哲学解决“信什么”

现有文档已经回答了：

- 我们信 Harness Engineering
- 我们信分层
- 我们信契约先行
- 我们信验证闭环
- 我们信知识要进 repo

这些是价值与方向。

### 2.2 constitution 解决“先走哪条路”

真正缺的是：当 AI 接到一个任务时，先做什么、后做什么、轻重怎么分、哪个标准先加载、什么时候必须升级。

routing constitution 负责的就是：

1. 先判定 locus / ownership / chain impact
2. 再解析 authoritative leaf standards
3. 再选择 B1 / B2 / B3
4. 再决定需要哪些 artifacts
5. 再决定要做到哪一级 verification

它不是哲学的重复，而是哲学的落地入口。

### 2.3 为什么不能只靠更多文档

如果只继续加文档，会出现三个问题：

- 文档越来越多，但入口还是散的
- AI 还是得猜先看哪份、先服从哪条
- 小任务会被大流程淹没，大任务又会缺少升级门槛

所以 repo 需要的是路由器，不是论文集。

---

## 3. 为什么是 locus-first，而不是 workflow-depth-first

这是这套系统最重要的顺序。

### 3.1 locus-first 的意思

先回答：

- 这件事落在哪个 repo locus
- 是平台、runtime、调试入口、结果域，还是 repo 级知识 / 流程
- 是否触及 governed surface
- 是否跨链、跨层、跨边界

只有 locus 清楚了，workflow depth 才有意义。

### 3.2 workflow-depth-first 的问题

如果先选流程深度，再谈 locus，就会把“怎么做”放在“在哪做”前面，常见后果是：

- 小的本地工作被重流程化
- 需要治理的工作被轻量化
- standards resolver 被粗粒度分类替代
- 验证路径选错
- 该升级的任务没有升级

### 3.3 locus-first 不是反对深度，而是先定边界

locus-first 不是说永远只做轻量工作，而是说：

> 先确认任务属于谁、影响到哪，再决定要不要进入更深的 workflow band。

这与当前仓库的 operating model 一致，也与 blueprint 的分层一致。

---

## 4. B1 / B2 / B3 是什么，和 Harness Layers L1-L4 有什么区别

这两组编号容易看起来像同一件事，但其实不是。

### 4.1 Harness Layers L1-L4：内容位置层

Blueprint 里的 L1-L4 是仓库知识和治理内容的分层：

- **L1**：Philosophy / Standards
- **L2**：Knowledge
- **L3**：Runbooks / Operations
- **L4**：Harness Tests / Acceptance

它回答的是：

- 这类内容应该放哪里
- 哪些是现行标准，哪些是解释材料，哪些是排障材料，哪些是验收材料

### 4.2 B1 / B2 / B3：执行深度层

B1/B2/B3 是 workflow depth / execution band：

- **B1**：轻量本地执行
- **B2**：标准边界内执行
- **B3**：受治理 / 研究 / formal chain 执行

它回答的是：

- 这次 AI 应该走多重的过程
- 需要多重的 artifact
- 验证要走多远
- 是否需要升级到受治理流程

### 4.3 它们的关系

最简单的理解是：

- L1-L4 决定“知识和规则放哪儿”
- B1-B3 决定“这次工作要走多深”

所以它们不是同一维度，也不应该互相替代。

### 4.4 为什么必须分开命名

如果不分开，AI 很容易把“知识层级”误当成“执行层级”，或者把“执行深度”误当成“标准位置”。

分开命名后，判断就会更稳定：

- 先找对标准位置
- 再决定执行 band

---

## 5. 为什么仓库需要这套路由，而不是只让 AGENTS 或 helper host 自己说了算

### 5.1 canonical 不该放进 helper host

当前推荐的 helper host 是 `.harness/`；历史 `.omx/` 只是上一代 helper host。helper host 更适合作为：

- 模板
- 计划草稿
- 会话状态
- 辅助产物
- 工作流工具数据

它可以帮助执行，但不应该成为 canonical source of truth。

### 5.2 root AGENTS.md 只能做 thin routing

现在仓库根部已经引入 `AGENTS.md`，但它只承担轻量路由角色，例如：

- 指向现行标准入口
- 指向知识入口
- 指向本地服务标准

它不应该自己变成一份巨型规范文档，更不应该吞掉 `docs/standards/` 的 canonical 地位。

### 5.3 canonical 应该放在 docs/standards

真正的现行标准应该落在 `docs/standards/`（以及各服务自己的 `docs/standards/`）里。

原因很简单：

- 标准是“该怎么做”
- 知识是“为什么这么做”
- 路由是“先看哪份、先走哪条”

这三个角色不应该混在一起。

---

## 6. 这篇文档的定位：知识说明，不是 enforceable standard

这点要明确。

本文只说明：

- 为什么需要这套执行系统
- 为什么要 locus-first
- 为什么需要 routing constitution
- 为什么 B1/B2/B3 要和 L1-L4 区分
- 为什么 canonical 应该落在 docs/standards
- 为什么 helper host（当前 `.harness/`，历史 `.omx/`）只能做 helper layer

本文**不**负责：

- 定义强制门禁
- 定义具体验收脚本
- 定义某个服务的实现细则
- 替代标准文档

这些内容应该由 `docs/standards/`、服务级标准、runbook 和 harness tests 去承载。

---

## 7. Non-goals

这套执行系统明确不做下面这些事：

1. **不把所有任务都重包装成重流程**
   - 小任务仍然应该轻。

2. **不把 repo 变成文档官僚主义**
   - 这不是要求更多仪式，而是要求更少误路。

3. **不把 app/service 的局部标准 flatten 成一层大标准**
   - leaf standards 仍然是 authoritative。

4. **不允许 AI 编造 real secrets / real params / real datasets**
   - 真实输入必须来自用户或环境，不由 AI 想当然补齐。

5. **不把 helper host（当前 `.harness/`，历史 `.omx/`）当 canonical**
   - 它是 helper/template/state layer，不是标准源。

6. **不让知识文档冒充 enforceable 标准**
   - 本文只解释理由，不负责强制。

7. **不替代现有 Harness L1-L4**
   - 这套系统是在它们之上组织执行，不是重命名它们。

---

## 8. 一句话总结

这套 locus-first AI execution system 的意义，不是再发明一套更华丽的哲学，而是把仓库已有的 Harness Engineering、blueprint、operating model 和 development paradigm 变成 AI 能稳定遵守的路由顺序。

它让 repo 先问“这件事属于哪里”，再问“要走多深”，最后才问“怎么做”。
