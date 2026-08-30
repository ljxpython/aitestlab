## Why

当前 `apps/runtime-service` 的可执行入口仍位于旧 `runtime_service/` 包，Graph 注册、依赖安装和
本地调试配置也绑定在旧目录。绿色重构需要先建立一个独立、可启动、可验证的 `src` 包基线，
为后续 Runtime Contracts 和 Agent Service 实现提供唯一入口。

## What Changes

- **BREAKING**：新增 `apps/runtime-service/src/runtime_service/` 作为唯一新 Python 包，R0 新代码不导入旧包。
- **BREAKING**：新增根级 `apps/runtime-service/langgraph.json`，生产配置只注册 `reference_agent`。
- 新增 `apps/runtime-service/langgraph.demo.json`，本地学习配置注册 `reference_agent` 和 `workflow_demo`。
- 新增最小 `reference_agent` 和 `workflow_demo` Service/Graph 导出骨架，统一暴露异步 `get_agent(config)`。
- 调整 Runtime Service 的 Python 打包配置，使 `src` 包可被 `uv`/LangGraph Server 导入。
- 为包导入、Graph 注册、描述字段和 fake model 启动路径增加 R0 测试，并增加显式启用的真实模型 E2E。
- 从本机 `~/.my_best/.env` 注入 DeepSeek 文本中转和 GPT 多模态中转配置到未跟踪的 Runtime `.env`。
- 将旧 `apps/runtime-service/runtime_service/` 移出活动导入路径并归档为历史代码；本变更不适配、不兼容旧运行行为。

## Capabilities

### New Capabilities

- `runtime-service-baseline`: 提供新 `src` 包、Graph 注册配置、两个最小参考 Service 和本地启动验证。

### Modified Capabilities

- `runtime-agent-service-boundary`: 将新 Agent Service 的正式归属从旧包路径收敛到
  `apps/runtime-service/src/runtime_service/services/<agent>/`，并将 Graph 导出层收敛到
  `src/runtime_service/graphs/`。

## Impact

- 影响 `apps/runtime-service/pyproject.toml`、根级 LangGraph 配置、`src/runtime_service/` 新包和
  `apps/runtime-service/tests/` R0 测试。
- 生产 LangGraph 启动入口切换到新配置；旧配置和旧 Python 包不作为新链路输入。
- 本阶段不修改 `apps/platform-api`，不实现 Runtime Context、Auth、Middleware、模型解析或 Durable Run；
  真实模型 E2E 只验证 Runtime 基线，不冻结后续模型解析契约。
