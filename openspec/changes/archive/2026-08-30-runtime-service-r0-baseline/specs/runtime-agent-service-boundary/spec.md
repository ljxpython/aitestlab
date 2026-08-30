## MODIFIED Requirements

### Requirement: 业务 Agent 必须保持服务模块所有权

每个新生产或参考 Agent SHALL 位于 `apps/runtime-service/src/runtime_service/services/<agent>/`，
并在该模块内维护其 graph、prompt、私有工具和 Agent 默认运行时配置。部署配置 SHALL 只通过
`apps/runtime-service/src/runtime_service/graphs/<graph_id>.py` 的稳定入口暴露 Service；共享代码
只可用于跨多个 Agent 复用的 middleware、runtime context 或公共工具能力。旧
`apps/runtime-service/runtime_service/` 路径不属于新实现的可导入边界。

#### Scenario: 新增参考 Agent Service

- **WHEN** R0 新增 `reference_agent` 或 `workflow_demo`
- **THEN** Service 代码位于 `src/runtime_service/services/<agent>/`，Graph 导出位于
  `src/runtime_service/graphs/`，且不依赖旧包

#### Scenario: 新增生产业务 Agent

- **WHEN** 开发者新增一个生产业务 Agent
- **THEN** graph 及其私有行为位于 `src/runtime_service/services/<agent>/` 模块，且该模块显式声明其 public 工具默认值

#### Scenario: 单 Agent 私有逻辑

- **WHEN** 某个工具、prompt 或 workflow 仅被一个新 Service 使用
- **THEN** 该逻辑保留在对应 Service 模块，不创建共享框架抽象
