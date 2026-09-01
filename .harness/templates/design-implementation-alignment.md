# 设计实现对齐目录模板

> Helper-only template。不是领域规范，也不能覆盖 `AGENTS.md`、Current Standard
> 或设计文档本身。

## 使用规则

- 每一行只记录一个可验证的原子要求。
- 必须同时填写设计来源、实现位置、测试位置和验证记录。
- 代码存在、测试存在或 `tasks.md` 勾选，单独都不能判定完成。
- 后续阶段能力标记为 `deferred`；当前文档的要求被后续阶段实现污染时标记为
  `phase-contaminated`。
- 缺少真实外部依赖时标记为 `blocked` 或 `not-executed`，不能用 skip 伪装通过。

## 状态

| 状态 | 含义 |
| --- | --- |
| `implemented-local` | 本地源码、可失败测试和最小验证闭环 |
| `implemented-chain` | 最短真实调用链已通过 |
| `partial` | 只有局部实现、假依赖或证据不完整 |
| `missing` | 没有承担该要求的实现或测试 |
| `deferred` | 设计明确后置到其他阶段 |
| `phase-contaminated` | 后续阶段内容进入当前阶段产物或门槛，需拆开统计 |
| `blocked` | 必要外部条件未满足 |
| `not-executed` | 要求需要验证，但本轮尚未执行；不能视为通过 |

## 对齐目录

| ID | 设计来源 | 原子要求 | 阶段 | 实现位置 | 测试位置 | 验证记录 | 状态 | 缺口/后续 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `DOC-PHASE-001` | `文档#章节` | 一条可失败的要求 | `R0` | `path:symbol` | `path:test_name` | `command; result; evidence` | `missing` | 下一动作 |
