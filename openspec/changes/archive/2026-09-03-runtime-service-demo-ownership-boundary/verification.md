# Verification

- Harness verification schema: v1
- Status: Complete
- Disposition: Accepted
- Pre-apply review: Approved
- Change: `runtime-service-demo-ownership-boundary`
- Locus: `apps/runtime-service`
- Chain: `langgraph*.json -> graphs/<graph_id>.py -> Demo implementation -> tests/scripts`
- Band: B3 Governed

## Pre-apply Review

- Owner decision: Approved。Owner 在 2026-09-03 明确同意将 Demo 迁入 `src/runtime_service/demo/`，
  保留 `reference_agent` 于 `services/`。
- Scope: 迁移六个 Demo 的内部包路径；保持 graph ID、Graph adapter 配置路径和 production
  `langgraph.json` 行为不变。
- Non-goals: 不执行外部 PostgreSQL/Redis/模型验收，不修改 archive，不改变 Runtime Auth 或数据。

## Planned Evidence

- `rg` 不再命中活动代码、测试、脚本和 current docs 中的旧 Demo import/path。
- `langgraph.json`、`langgraph.demo.json`、`langgraph.r6.json` 保持有效 JSON 和既有 graph ID/path。
- R0 baseline、Demo/Workspace/Resource 定向测试与不含 integration/durable/e2e 的完整 Runtime 测试通过。
- `scripts/check_docs.py`、`openspec validate --all --strict --no-interactive`、`git diff --check` 通过。

## Results

| Check | Result |
| --- | --- |
| 活动路径静态检查 | 未命中 `runtime_service.services.<demo>`、`src/runtime_service/services/<demo>` 或旧 Demo OpenSpec 路径；archive 保持历史原文。 |
| Graph 配置稳定性 | `langgraph.json`、`langgraph.demo.json`、`langgraph.r6.json` 均有效 JSON；既有 graph ID 顺序不变，所有 path 仍指向 `./src/runtime_service/graphs/`。 |
| R0 + Demo/Workspace 定向回归 | `77 passed`：R0 baseline、R4 Demo、Workspace policy/demo 与 resource reconnect。 |
| 完整本地 Runtime 回归 | `uv run --frozen --group dev pytest tests -m "not integration and not durable and not e2e" -q`：`191 passed, 21 deselected`。 |
| 编译 | `uv run --frozen --group dev python -m compileall -q src tests scripts` 通过。 |
| 文档 | `uv run --frozen python scripts/check_docs.py` 通过。 |
| OpenSpec | 本 change strict validation 通过；`openspec validate --all --strict --no-interactive`：`30 passed, 0 failed`。 |
| Diff | `git diff --check` 通过。 |

实现将六个 Demo 移至 `src/runtime_service/demo/`，仅更新 `graphs/*.py` 的内部 import。
`langgraph*.json`、Agent Protocol、graph ID 与生产 `reference_agent` 的 Service 路径未改变。

## Residual Risk

- 本 change 不执行真实 Durable 或外部 Provider 验收；它们由现有 R6 证据和后续 change 负责。
- Python 内部旧 Demo import 已移除；仓库内私有调用方必须使用 `runtime_service.demo.<name>`，
  这不构成对外兼容承诺。

## Docs / Runbook Impact

- 更新 13 号目标目录、当前对齐文档和 active OpenSpec 的源码路径。
- Owner 于 2026-09-03 确认 acceptance；`runtime-agent-service-boundary` delta 已同步，随后归档。
