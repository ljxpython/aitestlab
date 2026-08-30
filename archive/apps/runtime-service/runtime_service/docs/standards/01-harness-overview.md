# runtime_service Harness 总览

`runtime_service` 的核心目标不是只跑通几个 graph，而是建立一套可以持续开发、持续验收、持续排障的工程 harness。

这里的 harness 指的是：

- 有统一开发范式
- 有统一运行时契约
- 有可执行验收标准
- 有稳定排障路径
- 有清晰的文档分层

一句话：

> 文档告诉团队怎么做，样板告诉团队怎么写，测试告诉团队哪里不合格，runbook 告诉团队出问题怎么查。

## 1. harness 的四层结构

### 1.1 Standards

标准层定义“现行规则”。

当前包括：

- `standards/02-architecture.md`
- `standards/03-agent-development-playbook.md`
- `standards/08-middleware-development-playbook.md`
- `standards/04-agent-scaffold-templates.md`
- `standards/05-template-to-runnable-agent-10min.md`
- `knowledge/04-runtime-contract-v1.md`
- `knowledge/06-runtime-blueprint-pseudocode.md`

用途：

- 统一 graph 形态
- 统一 `RuntimeContext/config/configurable/env`
- 统一 middleware 设计
- 统一 tools registry 规则

### 1.2 Knowledge

知识层解释“为什么这样做”。

当前包括：

- LangGraph 官方概念对照
- `create_agent(...)` 参数理解
- SDK / curl 传参方式
- 运行时蓝图伪代码

用途：

- 帮新人补认知
- 解释官方推荐范式
- 减少拍脑袋设计

### 1.3 Runbooks

排障层定义“出问题怎么查”。

当前包括：

- `runbooks/09-test-case-service-skills-troubleshooting.md`

后续应继续增加：

- runtime 参数错误排查
- tools catalog / tool filtering 排查
- model resolver 排查
- multimodal 排查

### 1.4 Harness Tests

验收层定义“什么算合格”。

目录：

- `runtime_service/tests/harness/`

用途：

- 把开发范式变成自动检查
- 避免文档和代码长期脱节

## 2. 文档分层规则

`docs/` 目录统一按下面规则维护：

- `docs/standards/`
  现行标准，团队必须遵守
- `docs/knowledge/`
  学习材料和官方对照，不直接当实施模板
- `docs/runbooks/`
  排障手册、故障复盘、调试路径
- `docs/archive/`
  历史范式、已过时模板、背景资料

硬规则：

- 已不代表现行开发范式的模板文档必须移入 `archive/`
- 新成员默认先看 `standards/`，不是先看 `archive/`
- `README.md` 只能指向现行有效入口，不能把历史模板挂在前排

## 3. harness 最小验收面

第一阶段至少覆盖这些检查：

1. graph contract 检查
2. runtime context 检查
3. middleware contract 检查
4. tool registry contract 检查
5. graph registration 检查
6. 最小 smoke 检查

## 4. 第一阶段禁止项

第一阶段先别搞花活：

- 不搞兼容迁移校验
- 不搞过度动态能力
- 不搞过度抽象的测试框架
- 不搞跨服务泛化大一统

原则：

> 先用最少的 harness 把最核心的范式钉死，再逐步扩大覆盖面。

## 5. 当前推荐阅读顺序

1. `standards/01-harness-overview.md`
2. `standards/02-architecture.md`
3. `standards/03-agent-development-playbook.md`
4. `standards/08-middleware-development-playbook.md`
5. `knowledge/04-runtime-contract-v1.md`
6. `knowledge/06-runtime-blueprint-pseudocode.md`
7. `runbooks/`

## 6. 当前结论

`runtime_service` 后续不再以“单个 graph 能跑”为完成标准，而以“是否符合 harness”作为完成标准。
