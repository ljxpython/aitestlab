## Context

`services/` 当前包含 `reference_agent` 与六个 Demo。生产配置只注册 `reference_agent`，其余
graph 位于本地学习或 R6 验收配置；但它们的实现路径无法表达这一生命周期差异。`graphs/` 已是
所有配置引用的稳定 adapter 层，因此包迁移可以不改变 Agent Protocol、graph ID 或配置路径。

## Goals / Non-Goals

**Goals:**

- 将 Demo 与生产/参考 Service 的物理所有权明确分开。
- 保持 `graphs/*.py`、`langgraph.json`、`langgraph.demo.json` 与 `langgraph.r6.json` 的外部
  导出和 graph ID 稳定。
- 用导入、配置解析和本地回归证明迁移不改变行为。

**Non-Goals:**

- 不移动 `reference_agent`，不重命名 graph ID，不改变 GraphHarbor、Auth、Runtime contracts 或
  PostgreSQL/Redis 数据。
- 不把 Demo 纳入生产 `langgraph.json`，不重写 archived OpenSpec 的历史路径。
- 不把 `tests/services/` 批量重命名；测试分层不因源码所有权调整而改变。

## Decisions

1. **`services/` 只保留生产/参考 Agent。** `reference_agent` 是唯一当前生产配置注册的 Agent，
   保持原位置。未来业务 Service 同样进入该目录。
2. **Demo 使用 `demo/<name>/`。** 迁移 `workflow_demo`、`deep_agent_demo`、`mcp_demo`、
   `backend_demo`、`failure_demo` 与 `workspace_demo`，并保留各自的私有代码与 README。
3. **Graph adapter 不移动。** `graphs/<graph_id>.py` 只更新 import，所有 `langgraph*.json`
   保持现有 path 和 ID。这避免容器、SDK 或 Platform 上游感知内部目录变化。
4. **只更新当前真源。** 当前文档、脚本、测试、active OpenSpec 与 main spec 更新为新路径；
   archive 是历史证据，不反写。

替代方案“继续将所有目录置于 `services/`”被拒绝：它无法表达 Demo 的非生产生命周期；
替代方案“直接配置指向 `demo/*.py`”被拒绝：会破坏稳定 graph adapter 契约。

## Risks / Trade-offs

- [遗漏 Python import] -> `rg` 检查旧导入，并运行完整无外部 Runtime 测试。
- [遗漏文档或 active OpenSpec 路径] -> 文档检查、OpenSpec strict validate 与范围搜索。
- [配置误改] -> JSON 解析并断言 graph ID/path 未变；不编辑 `langgraph*.json`。

## Migration Plan

1. 移动六个 Demo 包并更新生产、测试和脚本导入。
2. 更新 graph adapter 内部导入与当前文档/active OpenSpec 路径。
3. 执行静态旧路径检查、配置解析、R0/定向/全量本地回归、文档与 OpenSpec 验证。
4. 验收后同步 `runtime-agent-service-boundary` delta spec 并归档本 change。

回滚只需将 Demo 目录和 import 恢复为 `services/<name>`；配置和持久化数据未变。

## Open Questions

无。Owner 已批准该目录边界与迁移范围。
