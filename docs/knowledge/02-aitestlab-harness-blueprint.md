# AITestLab Harness Blueprint（仓库级 Harness 蓝图）

> 状态：Archived Knowledge。当前简明说明见 `docs/knowledge/harness-engineering.md`。
> 本文保留历史蓝图，不作为当前任务入口或 current standard。

文档类型：`Knowledge Blueprint`

这篇蓝图解释当前仓库为什么按 `platform-web -> platform-api -> runtime-service -> interaction-data-service` 这条正式主链组织，但它不是本地部署 contract 本身。

如需当前正式部署口径，请优先看：

- `docs/local-deployment-contract.yaml`
- `docs/local-dev.md`
- `docs/deployment-guide.md`

## 这篇文档解决什么问题

上一份文档已经把 Harness Engineering 的思想讲清楚了，但光讲思想还不够。工程里最怕的就是话说得漂亮，落地时还是一团浆糊。

所以这篇文档专门回答一个更具体的问题：

> 对当前 `AITestLab` 仓库来说，Harness 到底落在哪些目录、哪些服务、哪些脚本、哪些文档、哪些测试上？

换句话说，这是一份仓库级 Harness 地图。

它的目标不是讲抽象概念，而是把下面这些事情钉死：

- 当前仓库的 Harness 分几层
- 每一层落在哪些目录和服务上
- 哪些应用是正式链路，哪些只是历史参考或兼容入口
- 日常开发、联调、验收、排障、发布分别应该从哪里进入
- 后续继续扩展时，应该优先把东西放在哪一层，而不是到处乱塞

---

## 1. AITestLab 的 Harness 北极星

对当前仓库，我建议统一用下面这句话做顶层定义：

> AITestLab 不是“几个应用拼在一起的演示仓库”，而是一套支持 AI 持续开发、持续联调、持续验收、持续排障、持续发布的工程 Harness。

这个定义有几个关键含义：

1. **平台治理和 Runtime 执行必须分层**
2. **调试链路和正式产品链路必须分开**
3. **运行时契约必须稳定，不允许每个 graph 自创一套规则**
4. **标准必须进入文档，文档必须有自动化守门员**
5. **排障和验收不能靠人肉感觉，必须有脚本、测试、runbook 和 smoke 路径**

只要这个北极星不变，后续无论你是继续重构 `runtime-service`，还是扩展平台能力，或者新增业务 agent，都不会偏航。

---

## 2. 当前仓库的正式主链路

### 2.1 正式平台链路

当前仓库的正式平台链路是：

```text
platform-web -> platform-api -> runtime-service -> interaction-data-service
```

职责分别是：

- `apps/platform-web`：正式平台前端宿主 / 工作台入口
- `apps/platform-api`：正式平台控制面 / 治理层 API / Runtime 网关
- `apps/runtime-service`：LangGraph Runtime / Agent 执行层
- `apps/interaction-data-service`：结果域服务 / 落库与查询

这条链路代表“产品化、治理化、可交付”的主路径。

### 2.2 正式调试链路

当前仓库的正式调试链路是：

```text
runtime-web -> runtime-service
```

职责分别是：

- `apps/runtime-web`：通用 Runtime 调试前端
- `apps/runtime-service`：统一执行层

这条链路代表“快速验证、聚焦 Runtime、自我排障”的主路径。

### 2.3 历史与参考入口

当前仓库还保留了一些历史应用或迁移参考资源，例如：

- `apps/platform-web`
- `apps/platform-api`
- `apps/platform-web-v2`
- `apps/platform-web-sub2api-base`

这些内容不应继续充当“默认开发主战场”，而应按照下面几种身份管理：

- 历史兼容入口
- 迁移对照源
- UI / 架构参考源
- 局部功能回看样本

也就是说：

> 正式开发默认看正式主链路，历史目录是参考，不是默认主入口。

---

## 3. AITestLab 的四层 Harness 结构

推荐把整个仓库的 Harness 拆成四层。

### 3.1 L1：Philosophy / Standards（哲学与现行标准层）

回答的问题：

- 我们信什么
- 我们按什么原则设计
- 哪些是现行有效规则

当前落点：

- 根目录 `docs/development-paradigm.md`
- 根目录 `docs/development-guidelines.md`
- 各服务内部的 `docs/standards/`

这一层的价值是：

- 帮团队统一判断标准
- 帮 AI 代理理解“什么是对的做法”
- 防止每次设计都从零吵起

### 3.2 L2：Knowledge（知识解释层）

回答的问题：

- 为什么这样做
- 官方怎么推荐
- 我们为什么做这个折中
- 某个复杂概念到底该怎么理解

当前落点：

- 根目录 `docs/knowledge/`
- 各服务内部 `docs/knowledge/`

这一层的价值是：

- 帮新人补认知
- 帮 AI 代理减少误解
- 把“经验主义”变成“可学习知识”

### 3.3 L3：Runbooks / Operations（运维与排障层）

回答的问题：

- 出问题怎么查
- 先看哪个服务
- 用什么命令验证
- 哪些现象说明是平台问题，哪些说明是 runtime 问题

当前落点：

- 根目录脚本：`scripts/*.sh`
- 各服务 `docs/runbooks/`
- release runbook、部署文档、环境矩阵

这一层的价值是：

- 把排障路径固定下来
- 把“经验老手才能查出来”的事变成可复制流程

### 3.4 L4：Harness Tests / Acceptance（验收守门层）

回答的问题：

- 什么叫合格
- 违反哪条标准时必须失败
- 哪些检查应该自动化
- 提交前应该跑什么

当前落点：

- `apps/runtime-service/runtime_service/tests/harness/`
- 各服务单测 / 冒烟 / 集成测试
- 根级健康检查脚本

这一层的价值是：

- 把标准从“文档”变成“门禁”
- 把回归风险前置
- 把“人肉感觉没问题”替换成“自动化告诉你哪里不合格”

---

## 4. 仓库级职责矩阵

下面这张表，是当前仓库最重要的一张 Harness 地图。

| 层级 | 组件 / 目录 | 角色定位 | 主要职责 | 不是它该干的事 |
| --- | --- | --- | --- | --- |
| 平台前端层 | `apps/platform-web` | 正式工作台宿主 | 用户入口、页面工作区、平台交互、管理台 UI | 不直接承载 Agent 内部编排逻辑 |
| 平台治理层 | `apps/platform-api` | 正式控制面 / Runtime 网关 | 鉴权、项目边界、审计、catalog、能力治理、Runtime 网关 | 不改写 Runtime 内部 graph 范式 |
| Runtime 执行层 | `apps/runtime-service` | Agent Runtime Platform | graph、middleware、model、tools、MCP、运行时契约、Agent 服务 | 不吞平台治理职责 |
| 调试前端层 | `apps/runtime-web` | 通用 Runtime 调试器 | 直连 Runtime、发送 context、快速调试与排查 | 不做 graph 专属平台逻辑 |
| 结果域层 | `apps/interaction-data-service` | 结果数据承接层 | 结果落库、结果查询、结果域隔离 | 不反向污染平台主数据模型 |
| 仓库级知识层 | `docs/` | 仓库级真源 | 开发范式、部署、环境矩阵、发布、知识文档 | 不替代服务内部细节标准 |
| 仓库级脚本层 | `scripts/` | 快速操作入口 | 启停、健康检查、联调脚本 | 不写复杂业务逻辑 |

这张表要守住，不然仓库迟早又会变回一个大泥球。

---

## 5. 当前仓库里每一层 Harness 的正式落点

### 5.1 Repo 级 Harness

Repo 级 Harness 负责定义整个仓库的共同规则和操作入口。

当前应重点看这些内容：

- `README.md`：仓库主入口与系统总览
- `docs/development-paradigm.md`：当前项目开发范式总说明
- `docs/development-guidelines.md`：仓库级开发约束
- `docs/deployment-guide.md`：部署与运行说明
- `docs/env-matrix.md`：环境变量矩阵
- `docs/releases/`：发布与回归 runbook
- `scripts/dev-up.sh`
- `scripts/check-health.sh`
- `scripts/dev-down.sh`

Repo 级 Harness 要解决的是：

- 新人怎么快速上手
- AI 代理怎么看懂仓库
- 默认联调怎么启动
- 正式链路是什么
- 发布链路如何验收

### 5.2 Runtime-Service 级 Harness

`runtime-service` 是当前仓库里最需要被工程化约束的地方。

当前应重点看这些内容：

- `apps/runtime-service/docs/knowledge/`
- `apps/runtime-service/runtime_service/docs/knowledge/`
- `apps/runtime-service/runtime_service/docs/runbooks/`
- `apps/runtime-service/runtime_service/tests/harness/`
- `apps/runtime-service/langgraph.json`

它的核心目标不是“graph 能跑”，而是：

- graph 形态稳定
- runtime contract 单一
- middleware 职责统一
- tool registry 有唯一真源
- Agent 能持续新增但不失控

### 5.3 Platform 层 Harness

平台层的 Harness 核心不在 graph，而在治理一致性。

正式主入口是：

- `apps/platform-web`
- `apps/platform-api`

这一层要守住：

- 用户 / 项目 / 权限边界
- Runtime 网关能力
- 平台级 metadata / policy / audit
- 页面工作区与交互稳定性

### 5.4 Debug Harness

`runtime-web` 是非常关键的一层，因为它能让 Runtime 在不经过整个平台链路的情况下被单独验证。

这层的原则必须保持克制：

- 它是通用 Runtime 调试 UI
- 它不是 graph 专属开发后台
- 它应该透传通用运行时字段，而不是承载各 graph 私有配置面板

这层越克制，越有利于长期复用。

---

## 6. AITestLab 的标准开发流

下面这条流，建议当作当前仓库最推荐的开发主路径。

### 6.1 做需求前

先判断这个需求属于哪一层：

- 平台治理问题
- Runtime 执行问题
- 调试问题
- 结果域问题
- 文档 / 验收 / 排障问题

不要一上来就写代码。

### 6.2 做设计时

先补齐这四样：

1. 契约边界
2. 目录落点
3. 不做清单
4. 验收标准

没有这四样，后面十有八九会返工。

### 6.3 做实现时

默认按这条原则：

- 仓库级规则看根目录 `docs/`
- Runtime 规则看 `runtime-service/docs/standards/`
- 平台规则看对应服务内部 docs
- 调试优先走 `runtime-web`
- 联调整体验证再走平台正式链路

### 6.4 做验证时

至少分三步：

1. **本地静态验证**：语法、类型、构建、单测
2. **最小链路验证**：目标服务 smoke / harness tests
3. **跨服务验证**：正式链路联调或调试链路验证

### 6.5 做收尾时

至少补齐：

- 文档更新
- runbook 更新（如果排障路径变化）
- 变更清单 / release 说明
- 已知遗留项

---

## 7. AITestLab 的标准验收流

对于当前仓库，我建议把验收分成四类。

### 7.1 Contract 验收

检查：

- 运行时字段是否归位正确
- 公共接口是否仍然单一
- 是否出现隐式兜底、隐式推断、跨层偷读

### 7.2 Structure 验收

检查：

- 功能是否落在正确服务
- graph / middleware / tools 是否职责清晰
- 调试逻辑有没有反向污染正式产品逻辑

### 7.3 Behavior 验收

检查：

- 构建是否通过
- 测试是否通过
- 最小业务链路是否可跑
- 错误是否直接可见

### 7.4 Operational 验收

检查：

- 是否有对应 runbook
- 是否有最小 smoke 路径
- 是否能快速定位失败层级
- 是否具备基本回归说明

---

## 8. AITestLab 的标准排障流

当前仓库后续排障，建议统一按下面的缩圈方式来。

### 8.1 先判定是平台链路问题还是 Runtime 本体问题

优先问：

- `runtime-web -> runtime-service` 是否正常？
- 如果调试链路正常，但平台链路异常，优先查 `platform-api` 或 `platform-web`
- 如果调试链路都不正常，优先查 `runtime-service`

### 8.2 再判定是契约问题、实现问题还是数据问题

分类查：

- 契约问题：参数入口、字段归位、上下文注入
- 实现问题：graph、middleware、tool、model、MCP
- 数据问题：project、result persistence、query isolation

### 8.3 最后才去怀疑模型本身

很多人一看到 AI 结果不对就甩锅模型，实际上大量问题都出在：

- 输入契约错了
- middleware 没生效
- tool 集合错了
- 项目上下文没传进去
- 平台网关注入有偏差

所以排障顺序必须对，不然纯属瞎折腾。

---

## 9. 当前仓库最值得持续建设的 Harness 资产

如果站在长期视角，我认为这个仓库最值钱的不是某个单独 Agent，而是下面这些资产。

### 9.1 Standards

把“应该怎么做”稳定下来。

### 9.2 Knowledge

把“为什么这样做”稳定下来。

### 9.3 Runbooks

把“坏了怎么查”稳定下来。

### 9.4 Harness Tests

把“什么算合格”稳定下来。

### 9.5 Sample / Template

把“新功能应该从哪里起步”稳定下来。

### 9.6 Release Discipline

把“交付前必须看什么、跑什么、记录什么”稳定下来。

这几样资产一旦成型，团队和 AI 代理才真的具备持续开发能力。

---

## 10. 当前仓库的硬规则建议

为了避免后续再长歪，建议至少长期坚持下面这些硬规则：

1. **正式开发默认沿正式主链路推进，不拿历史目录当主入口。**
2. **新知识优先进入 repo 文档，不停留在聊天记录。**
3. **Runtime 公共契约必须单一，不允许 graph 各自发明输入规则。**
4. **调试前端保持通用，不为单 graph 堆私货。**
5. **标准必须对应 harness tests 或 smoke 路径。**
6. **排障必须有缩圈顺序，不搞玄学定位。**
7. **历史方案、过时模板必须及时归档，不能和现行标准并列。**

---

## 11. 推荐的仓库级后续建设顺序

如果后续继续建设 AITestLab 的 Harness，推荐顺序如下：

### 第一阶段：把规则钉牢

- 根目录 `docs/knowledge/` 持续补齐
- `runtime-service` 继续收紧运行时契约
- 补齐更多 Harness Tests

### 第二阶段：把流程钉牢

- 完善 smoke / live / release checklists
- 完善 runbooks
- 完善平台链路与调试链路的验收矩阵

### 第三阶段：把产物钉牢

- 任务模板
- 变更模板
- 验收报告模板
- 故障复盘模板

### 第四阶段：把自动化钉牢

- CI 门禁
- 发布门禁
- 自动 smoke
- 自动结构检查

顺序别搞反。先有规则，再有流程，再有产物，再有重自动化。

---

## 12. 一句话总结

对当前 `AITestLab` 来说，Harness Blueprint 的核心不是“再加一套框架”，而是：

> 把平台治理、Runtime 执行、调试验证、结果承接、文档知识、验收门禁、排障路径，收拢成一套边界清晰、职责稳定、可持续演进的工程系统。

后续只要所有改动都能回答清楚下面四个问题，这个仓库就不会跑偏：

1. 这次改动属于哪一层？
2. 它应该落在哪个目录 / 服务？
3. 它遵守了哪条现行标准？
4. 它怎么被验收、怎么被排障？

这四个问题答不出来的改动，十有八九就有问题。
