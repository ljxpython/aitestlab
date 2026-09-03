## Why

`runtime_service.services/` 当前同时承载生产基准 Agent 与学习、R4/R6 验收 Demo，目录名称无法
表达两类代码的不同生命周期。Demo 的内部包迁移不应改变已发布的 graph ID 或 `langgraph*.json`
部署入口。

- Locus：`apps/runtime-service`
- Chain：`langgraph*.json -> graphs/<graph_id>.py -> Python implementation -> tests/scripts`
- Band：B3 Governed；改变 Runtime 的代码所有权规则和稳定导入边界。
- Authority：`apps/runtime-service/docs/knowledge/13-runtime-service-target-code-layout.md`、
  `openspec/specs/runtime-agent-service-boundary/spec.md`、仓库 AI 执行系统标准。

## What Changes

- 将学习和验收 Demo 从 `src/runtime_service/services/` 移至 `src/runtime_service/demo/`。
- 保留 `services/reference_agent/` 作为唯一现有生产/参考 Agent Service。
- 保持 `graphs/<graph_id>.py`、graph ID 和 `langgraph*.json` 入口不变，只调整 graph adapter
  的内部导入。
- 更新测试、受控验收脚本、当前知识文档和 active OpenSpec 的源码路径。
- **BREAKING（Python 内部导入）**：Demo 的 `runtime_service.services.<name>` 导入路径移除；
  Runtime 配置和对外 Agent Protocol 不变。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `runtime-agent-service-boundary`：区分生产 Service 与 Demo 的物理所有权，同时要求 graph adapter
  维持稳定部署入口。

## Impact

- 受影响代码：`src/runtime_service/services/`、`src/runtime_service/demo/`、`graphs/`、测试和 R6
  验收脚本。
- 不改依赖、GraphHarbor、Runtime Auth、持久化数据、graph ID 或 `langgraph*.json` 中的路径。
- 不修改 archived OpenSpec 的历史路径；验收仅需本地测试和配置/导入检查，不依赖外部服务。
