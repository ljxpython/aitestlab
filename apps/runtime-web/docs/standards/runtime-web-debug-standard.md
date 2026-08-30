# Runtime Web Debug Shell 标准

文档类型：`Current Standard`

这份文档定义 `runtime-web` 作为 **runtime 调试壳** 的当前标准。

它回答的是：

> 当一个需求落在 `runtime-web`，AI 应该把它当成什么样的入口来设计和验证？

---

## 1. 适用范围

下面这些情况优先读本文：

- 调试 UI 行为
- `runtime-web -> runtime-service` 的最短调试链
- Run Context / artifact context / debug mode / thread 调试交互
- graph-agnostic 的运行时验证入口
- 判断某个需求应该留在 `runtime-web` 还是移到正式平台链路

---

## 2. 核心边界

### 2.1 `runtime-web` 是调试入口，不是正式平台入口

它负责：

- 直接连接 `runtime-service`
- 调试 graph / tools / streaming / run context 行为
- 在不引入控制面复杂度的情况下验证 runtime 行为

它不负责：

- 正式平台治理
- 平台权限 / 项目边界
- 结果域管理与展示
- 正式控制面工作区体验

### 2.2 graph-agnostic 优先

`runtime-web` 优先提供：

- 通用调试壳
- 最小输入与上下文透传
- graph-agnostic 的运行时验证

不要把它写成某个 graph 的专属平台页面。

### 2.3 先服务层，再调试壳

如果问题已经能在 `runtime-service` 脚本或 harness 里复现：

- 先在 `runtime-service` 排查
- 再决定是否需要 `runtime-web` 做交互验证

不要让 `runtime-web` 代替服务层排障。

### 2.4 Run Context 只做薄透传

对于 `Run Context` / 调试输入：

- `runtime-web` 只做最薄 JSON object 校验
- 不负责 graph-specific schema 表单
- 不负责替服务端兜底 runtime contract 错误

---

## 3. leaf resolver rule

### Leaf A：debug-shell role / UI boundary

先读本文。

适用于：

- `runtime-web` 应不应该承接这个交互
- 它是不是会漂移成正式平台入口
- run context / debug mode / artifact context 这类调试壳边界

### Leaf B：runtime behavior truth

先读：

- `apps/runtime-service/docs/knowledge/*.md`
- `apps/runtime-service/runtime_service/tests/harness/*.py`

适用于：

- 真正的 runtime contract / graph / tool / middleware 行为
- 服务层应该如何证明正确

### Leaf C：正式平台页 / 正式治理行为

先读：

- `apps/platform-web/docs/control-plane-page-standard.md`
- `apps/platform-web/docs/frontend-development-playbook.md`

适用于：

- 页面是不是正式控制面页面
- 正式 service/state/permission/audit 是否应按平台规则处理

### 组合规则

- 如果问题是 **“这个能力该不该放在调试壳？”**
  - 先读 **Leaf A**
- 如果问题是 **“runtime 真正的 contract 行为是什么？”**
  - 转到 **Leaf B**
- 如果问题已经变成正式平台页：
  - 转回 `platform-web` 的 leaf resolver

---

## 4. 验证规则

`runtime-web` 的验证顺序固定为：

1. 先确认 `runtime-service` 本地证明是否已经成立
2. 再用 `runtime-web -> runtime-service` 做交互验证
3. 除非需求本身升级为正式平台行为，否则不自动要求 `platform-web -> platform-api -> runtime-service` 链路验证

一句话：

> `runtime-web` 用来把 runtime 行为调通，不用来替正式平台验收一切。
