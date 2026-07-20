# Harness Engineering 学习与实践总纲

> 状态：Archived Knowledge。当前简明说明见 `docs/knowledge/harness-engineering.md`。
> 本文仅保留完整背景、历史建议和外部参考，不属于默认阅读路径。

文档类型：`Knowledge`

这是一篇方法论文档，用来解释为什么这个仓库会以 `AI Harness` 为总哲学。它不是当前架构事实源，也不直接定义启动链路或接口契约。

## 这篇文档解决什么问题

这篇文档不是在讲某个单点工具、某个 prompt 技巧，或者某种 LangGraph 写法，而是想把一个更上位的工程思想讲清楚：

> 当 AI / Agent 不再只是“回答问题”，而是开始持续参与需求分析、编码、联调、验收、排障和交付时，团队到底该如何为它构建一套可长期运行的工程外壳。

这里所说的这套工程外壳，就是 Harness Engineering。

对当前仓库来说，它不只是 `runtime-service` 的局部话题，而是整个仓库后续持续开发、持续验收、持续排障、持续演进的共同方法论。

---

## 1. 什么是 Harness Engineering

### 1.1 定义

Harness Engineering 可以理解为：

> 围绕 AI / Agent 构建一整套可持续运行、可持续验收、可持续排障、可持续迭代的工程操作系统。

这里的 “Harness” 不是单个测试工具，也不是单个 `AGENTS.md` 文件，而是一个受控的工程外壳。它至少包括：

- 清晰的运行时契约
- 明确的系统边界与分层
- 可执行的开发范式
- 可自动化的验收标准
- 稳定的排障路径
- 能沉淀知识和过程产物的仓库结构

一句话说：

> Prompt 决定模型怎么想，Context 决定模型看见什么，Harness 决定模型在什么制度、环境和反馈回路里工作。

### 1.2 它不是 Prompt Engineering 的同义词

Prompt Engineering 关注的是：

- 怎么写指令
- 怎么组织 few-shot
- 怎么让模型更听话

Harness Engineering 关注的是：

- 模型通过什么入口接收输入
- 运行时参数从哪里来
- tool / middleware / session / checkpoint 如何装配
- 什么叫“完成”，什么叫“失败”
- 出错后怎么定位和恢复
- 团队如何持续让 AI 参与工程工作而不失控

所以它是一个更高层的工程命题，而不是 prompt 技巧集合。

### 1.3 它也不只是 Test Harness

传统软件工程里的 test harness，通常是指：

- 测试驱动程序
- 测试数据
- stub / mock
- 结果比较器
- 自动化执行环境

这是 Harness Engineering 里的一个子集，但不是全部。

Harness Engineering 关心的不只是“怎么测”，而是：

- 怎么开发
- 怎么运行
- 怎么验收
- 怎么排障
- 怎么知识沉淀
- 怎么形成团队统一范式

---

## 2. 为什么 AI / Agent 项目尤其需要 Harness Engineering

传统后端服务的行为通常更稳定，输入与输出边界也更容易固定。

但 AI / Agent 系统有几个天然麻烦：

1. **输入通道容易失控**  
   context、config、env、state、prompt、metadata、tool 参数很容易乱成一锅粥。

2. **动态能力天然强，但也天然危险**  
   模型切换、tool 启停、system prompt 覆盖、多模态增强、skill 拼装，如果没有统一约束，很快就不可复现。

3. **很多失败不是代码异常，而是系统行为异常**  
   例如：工具选错、上下文不足、模型输出跑偏、任务没收敛、检查点恢复错位。

4. **口头规范非常容易失效**  
   如果规则只存在于人脑、聊天记录或某个临时文档里，AI 和新成员都无法稳定复用。

5. **“能跑一次”不等于“能持续开发”**  
   很多 Agent 项目能跑 demo，但一旦多人协作、持续迭代、接入平台治理，马上就开始失控。

所以，AI / Agent 项目真正缺的往往不是“更强的模型”，而是：

> 一套能把模型能力组织成稳定工程生产力的 Harness。

---

## 3. Harness Engineering 和几个常见概念的区别

| 概念 | 主要回答什么问题 | 所在层级 |
| --- | --- | --- |
| Prompt Engineering | 应该如何写提示词 | 最内层 |
| Context Engineering | 应该给模型哪些上下文 | 提示词外一层 |
| Workflow / Graph Design | 多步骤流程如何编排 | 执行流程层 |
| Test Harness | 如何自动执行测试并判定结果 | 验收子系统 |
| **Harness Engineering** | **如何把 Agent 放进可运行、可验证、可恢复、可演进的工程系统中** | **最顶层工程范式** |

可以用一句很直白的话理解：

- Prompt 是一句话怎么写
- Context 是把什么资料喂进去
- Graph 是任务怎么流转
- Harness 是整个系统怎么活、怎么查、怎么稳、怎么持续干活

---

## 4. Harness Engineering 的核心对象

我建议把 Harness Engineering 拆成 7 个核心对象来理解。

### 4.1 Contract（契约）

契约定义：

- 对外公开输入是什么
- 哪些字段允许传
- 哪些字段禁止传
- 默认值从哪里来
- 错误如何直接暴露

在当前项目里，典型例子就是：

- `RuntimeContext`
- `config`
- `config.configurable`
- `env`

它们各自的职责边界必须稳定，否则后续所有 agent / middleware / 调试前端都会被污染。

### 4.2 Runtime（运行时）

运行时定义：

- agent 怎么启动
- graph 怎么装配
- middleware 怎么生效
- session / checkpoint 怎么保存
- tools / model / prompt 如何在执行期解析

这一层决定的是：系统实际如何跑。

### 4.3 Knowledge（知识系统）

知识系统定义：

- 现行标准放哪里
- 学习材料放哪里
- 排障手册放哪里
- 历史文档放哪里
- 哪些文档是现行有效入口

如果知识不进 repo，而是只存在于群聊和脑子里，那么 AI 和新人都无法稳定继承经验。

### 4.4 Artifact（过程产物）

过程产物定义：

- plan
- spec
- run report
- smoke report
- evaluator report
- 故障快照
- handoff 记录

长流程、多轮交接、多人协作、Agent 接续执行，都需要靠结构化产物来承接，而不是指望模型“自己记住”。

### 4.5 Evaluation（评测 / 验收）

评测定义：

- 什么叫完成
- 什么叫不合格
- 什么叫回归风险
- 谁来做评估
- 是人评、规则评，还是 agent 评

对于 AI 系统，验收不能只看“有没有报错”，还要看：

- 契约是否被遵守
- 输出是否可接受
- 行为是否可复现
- 回归是否被守住

### 4.6 Observability（可观测性）

可观测性定义：

- 日志
- trace
- tool 调用记录
- 运行参数快照
- UI 行为快照
- 网络请求与错误上下文

AI 系统排障时，最怕的是“只看到最后一句报错，看不到行为过程”。

### 4.7 Governance（治理）

治理定义：

- 开发标准
- harness tests
- CI 门禁
- smoke / live check
- runbook
- 变更验收清单

也就是说，团队规范不能停留在“说过了”，必须变成“能被自动检查”。

---

## 5. Harness Engineering 的核心原则

结合当前项目与外部资料，推荐采用下面这些原则。

### 5.1 Contract First

先定义运行时契约，再写功能。

不要先把功能做出来，再去解释参数是从哪来的。

### 5.2 Static First

默认优先静态图、静态注册、静态边界。

能静态确定的能力就不要做成运行期任意拼接，否则系统可读性和可测性会迅速下降。

### 5.3 Middleware First

横切能力优先进入统一 middleware / resolver 层，而不是散落到各个 graph 里各写一套。

例如：

- 模型切换
- system prompt 覆盖
- tools 动态筛选
- 多模态增强
- 通用参数校验

### 5.4 Direct Error

运行时契约错误优先直接报错，不搞静默兜底。

错误不可见，排障就会变成玄学。

### 5.5 Repo as Source of Truth

标准、知识、样板、runbook、验收规则必须收敛进仓库。

不是靠某个人记得，也不是靠群聊翻记录。

### 5.6 Acceptance is Code

验收标准不是会议纪要，而是：

- harness tests
- smoke scripts
- live checks
- CI gate

### 5.7 Recovery Path Matters

一个能开发但不能排障的系统，不算成熟 harness。

runbook、日志、trace、失败快照、最小复现路径都必须纳入设计。

---

## 6. 当前仓库应该如何理解 Harness Engineering

对当前仓库，Harness Engineering 不应该被理解成某个单服务内部的话题，而应该是整个仓库的共同开发哲学。

### 6.1 仓库级理解

当前仓库已经具备了形成 Harness 的基础条件：

- 平台治理层：`apps/platform-api`
- 平台前端宿主：`apps/platform-web`
- Runtime 执行层：`apps/runtime-service`
- Runtime 调试入口：`apps/runtime-web`
- 结果域服务：`apps/interaction-data-service`
- 根级脚本、部署文档、环境矩阵、release runbook

所以这个仓库不应该再被当成“几个应用的集合”，而应该理解成：

> 一个可以支持 AI 持续开发、持续调试、持续联调、持续验收、持续交付的工程 Harness。

### 6.2 对 `runtime-service` 的理解

`runtime-service` 不是“多个 graph 文件堆在一起”，而应该被定义为：

> 一个受运行时契约、middleware、tool registry、知识文档和 harness tests 共同约束的 Agent Runtime Platform。

在这个定义下：

- graph 是工作单元
- `RuntimeContext` 是公开业务契约
- middleware 是统一运行时解析层
- tool registry 是公开能力目录
- harness tests 是开发范式守门员
- runbooks 是故障处置路径
- `runtime-web` 是通用调试前端，不是 graph 专属定制页面

### 6.3 当前项目里的推荐分层

推荐至少维护下面四层：

1. **Standards**  
   说明现行规则，告诉团队必须怎么做。

2. **Knowledge**  
   说明为什么这样做，补齐官方概念理解和设计背景。

3. **Runbooks**  
   说明出问题怎么查、怎么缩小范围、怎么复现。

4. **Harness Tests**  
   把开发范式转成自动校验，避免“文档是文档，代码是代码”。

---

## 7. 在当前项目中的具体落地方式

### 7.1 Repo 级落地

仓库级建议持续固定下面这些东西：

- 应用边界图
- 本地启动 contract
- 环境变量矩阵
- 默认联调链路
- 变更清单和 release runbook
- 统一文档入口

根目录 `docs/` 负责仓库级知识真源。

### 7.2 Service 级落地

每个关键服务都应该有自己的 harness 子系统。

例如 `runtime-service`：

- `docs/standards/`：当前开发范式和契约
- `docs/knowledge/`：官方资料学习和设计背景
- `docs/runbooks/`：排障路径
- `tests/harness/`：范式验收测试

### 7.3 Task / Change 级落地

每次较大改造都应有：

- 目标文档
- 约束边界
- 不做清单
- 验收标准
- smoke / test 结果
- 下一步遗留项

否则改造过程本身不可追踪，知识无法沉淀。

### 7.4 Release 级落地

每次准备交付或发布时，应该具备：

- 版本变更说明
- 回归检查列表
- 最小冒烟结果
- 已知风险
- 回滚方式

---

## 8. 对当前项目的关键实践建议

### 8.1 把 Runtime Contract 当成 Harness 底座

当前项目最关键的一条主线，就是把运行时输入统一收拢。

推荐持续坚持：

- `RuntimeContext`：唯一公共业务运行时通道
- `config`：只负责执行控制
- `config.configurable`：只负责线程、平台、鉴权、服务私有字段
- `env`：只负责部署默认值与 secrets

这不是“代码风格问题”，而是 harness 能否稳定成立的底层问题。

### 8.2 把 graph 当成稳定工作单元，而不是动态拼装场

推荐范式：

- `graph = create_agent(...)`
- `graph = create_deep_agent(...)`
- `graph = builder.compile()`

默认不把 `make_graph(config, runtime)` 当总范式。

原因很简单：

- graph 拓扑稳定，系统更可读
- 中间件职责稳定，系统更可测
- 调试链路更清晰，系统更可查

### 8.3 把 shared middleware 当成统一运行时解析层

共享 middleware / resolver 应负责：

- 读取 `RuntimeContext`
- 合并可信默认值
- 解析模型和运行时参数
- 覆盖 `system_prompt`
- 根据 `enable_tools/tools` 筛选工具
- 对非法运行时输入直接报错

graph 本身尽量只保留：

- 业务默认值
- 稳定工具全集
- 最薄装配

### 8.4 把 tool registry 当成公开能力目录

统一公开入口、统一命名、统一能力边界。

重点不是“能不能动态”，而是：

- 哪些工具是公开可选的
- 哪些工具是 graph 内部固定依赖
- 上层传入的工具集合如何被验证
- 无效工具如何失败

### 8.5 把 `runtime-web` 保持为通用调试前端

`runtime-web` 的职责应保持克制：

- 直连 runtime
- 传递 `context`
- 帮助调试运行时行为
- 不做 graph-specific 规则面板

它是通用调试 UI，不是某个 graph 的专用后台。

### 8.6 把 Harness Tests 做成硬规则守门员

推荐优先把这些规则自动化：

- graph 默认静态导出
- `context_schema=RuntimeContext` 明确存在
- 运行时业务字段不乱塞到 `configurable`
- tool registry 是公开能力唯一真源
- 非法 runtime 参数直接失败
- graph 注册信息完整有效

---

## 9. 超出当前项目，Harness Engineering 如何通用落地

Harness Engineering 不是这个仓库的私有玩法，它可以推广为一套更通用的方法。

### 9.1 适用于任何 AI Agent 仓库的最小框架

至少建立下面这些东西：

1. **边界图**  
   谁负责治理，谁负责执行，谁负责调试，谁负责持久化。

2. **运行时契约**  
   哪些参数能传，哪些参数不能传，默认值从哪里来。

3. **现行标准**  
   graph、middleware、tools、测试、目录结构怎么写。

4. **知识材料**  
   官方推荐范式、参数解释、架构说明、反模式说明。

5. **排障手册**  
   参数错误怎么查，tool 问题怎么查，模型问题怎么查，多模态问题怎么查。

6. **验收门禁**  
   harness tests、smoke checks、CI gates。

### 9.2 适用于更大团队的进阶框架

如果项目继续扩大，可以继续加：

- evaluator 体系
- replay / trace 回放
- 任务产物存档
- run manifest
- live benchmark
- 变更审批与 release checklists

但顺序不要反。先把最小 harness 钉牢，再逐步扩展。

---

## 10. 反模式：哪些不属于好的 Harness Engineering

下面这些做法很常见，但都不应该成为长期范式：

### 10.1 口头约定代替显式契约

“大家都知道这个字段要这么传。”

这种做法迟早出事。

### 10.2 每个 graph 自己发明一套运行时读取方式

今天从 `configurable` 读，明天从 `state` 读，后天从 system prompt 里反推。

这是最典型的 harness 崩坏源头。

### 10.3 只重视 demo 跑通，不重视验收和排障

一次能跑，不等于长期可维护。

### 10.4 把 AI 相关知识放在聊天记录里

知识不进 repo，就无法被 AI、CI、团队稳定复用。

### 10.5 一开始就搞过度动态和过度抽象

动态能力不是越多越高级。很多时候只是把排障成本和认知成本一起抬高。

---

## 11. 当前项目的 Harness Engineering 宣言（建议版）

建议把当前项目的工程哲学收敛成下面这组规则：

1. **先定契约，再写功能。**
2. **先让系统可验收，再让系统可扩展。**
3. **先让知识进入仓库，再谈 Agent 自主。**
4. **先让错误可见，再谈优雅降级。**
5. **先让标准可执行，再谈团队共识。**
6. **先让排障有路径，再谈复杂能力。**
7. **先做最小可持续 Harness，再逐步加厚。**

这七条，适合作为后续所有 Agent / Runtime / Platform 改造的总原则。

---

## 12. 建议的后续动作

对当前仓库，建议后续工作按下面顺序推进：

1. **先把 Harness 总纲、标准、知识、runbook 的目录体系钉牢。**
2. **再收紧运行时契约，统一 RuntimeContext / config / configurable / env 的职责。**
3. **再把 graph、middleware、tool registry 统一收敛到现行范式。**
4. **再补 harness tests，把规则变成自动门禁。**
5. **最后再做更复杂的 evaluator、benchmark、长期任务治理能力。**

不要顺序反过来。

---

## 13. 参考资料

以下资料用于建立本文的外部参考背景；请以阅读时的最新官方内容为准。

- OpenAI, *Harness engineering: leveraging Codex in an agent-first world*  
  https://openai.com/index/harness-engineering/
- OpenAI, *Unlocking the Codex harness: how we built the App Server*  
  https://openai.com/index/unlocking-the-codex-harness/
- Anthropic, *Harness design for long-running application development*  
  https://www.anthropic.com/engineering/harness-design-long-running-apps
- Anthropic, *Scaling Managed Agents: Decoupling the brain from the hands*  
  https://www.anthropic.com/engineering/managed-agents
- arXiv, *Natural-Language Agent Harnesses*  
  https://arxiv.org/abs/2603.25723
- TechTarget, *What is test harness?*  
  https://www.techtarget.com/searchsoftwarequality/definition/test-harness

---

## 14. 一句话总结

Harness Engineering 的本质，不是让模型更聪明，而是：

> 让模型在一个边界清晰、契约稳定、验收明确、排障可循、知识可沉淀的工程系统里持续产出价值。

这也是当前项目后续所有开发范式、架构收敛和 Harness 测试建设的总起点。
