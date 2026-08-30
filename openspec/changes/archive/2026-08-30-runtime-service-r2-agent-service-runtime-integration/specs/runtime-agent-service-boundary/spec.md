## MODIFIED Requirements

### Requirement: 业务 Agent 必须保持服务模块所有权

每个新生产或参考 Agent SHALL 位于 `apps/runtime-service/src/runtime_service/services/<agent>/`，并在该模块内维护其 graph、prompt、私有工具和 Agent 默认运行时配置。部署配置 SHALL 只通过 `apps/runtime-service/src/runtime_service/graphs/<graph_id>.py` 的稳定入口暴露 Service；共享代码只可用于跨多个 Agent 复用的 middleware、runtime context 或公共工具能力。旧 `apps/runtime-service/runtime_service/` 路径不属于新实现的可导入边界。使用公共 Runtime 的 Service MUST 在其 `agent_server.py` 中显式调用 `resolve_runtime_config` 和 `build_model`，不得由 `graphs/` 层或隐式扫描完成装配。

#### Scenario: 新增生产业务 Agent
- **WHEN** 开发者新增一个生产业务 Agent
- **THEN** graph 及其私有行为位于 `src/runtime_service/services/<agent>/` 模块，服务组合根显式声明默认值并在构图前完成 Runtime 解析

#### Scenario: 新增参考 Agent Service
- **WHEN** R2 使用 `reference_agent`
- **THEN** Service 代码位于 `src/runtime_service/services/reference_agent/`，Graph 导出位于 `src/runtime_service/graphs/`，并通过 LangChain `context_schema` 接收新 Context

#### Scenario: 单 Agent 私有逻辑
- **WHEN** 某个工具或 prompt 仅被一个业务 Agent 使用
- **THEN** 该逻辑保留在该 Agent 的服务模块，不创建共享框架抽象
