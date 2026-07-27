# runtime-agent-service-boundary Specification

## Purpose

定义生产业务 Agent、共享 runtime 能力与 platform-api runtime gateway 的职责边界。

## Requirements

### Requirement: 业务 Agent 必须保持服务模块所有权
每个生产业务 Agent SHALL 位于 `apps/runtime-service/runtime_service/services/<agent>/`，并在该模块内维护其 graph、prompt、私有工具和 Agent 默认运行时配置。共享代码只可用于跨多个 Agent 复用的 middleware、runtime context 或公共工具能力。

#### Scenario: 新增生产业务 Agent
- **WHEN** 开发者新增一个生产业务 Agent
- **THEN** graph 及其私有行为位于对应的 `services/<agent>/` 模块，且该模块显式声明其 public 工具默认值

#### Scenario: 单 Agent 私有逻辑
- **WHEN** 某个工具或 prompt 仅被一个业务 Agent 使用
- **THEN** 该逻辑保留在该 Agent 的服务模块，不创建共享框架抽象

### Requirement: platform-api 必须保持 runtime 控制面边界
platform-api SHALL 将调用方可配置的运行字段归一化到 runtime `context`，并继续注入受信任项目范围；它不得解析工具 registry、选择 MCP 工具或执行 Agent graph。

#### Scenario: runtime gateway 转发工具选择
- **WHEN** 调用方通过 platform-api 提交 `enable_tools` 或 `tools`
- **THEN** platform-api 将这些字段归一化后转发到 runtime `context`，不扩展为未请求的工具名称

#### Scenario: runtime gateway 接收项目范围
- **WHEN** 已授权项目调用通过 platform-api 进入 runtime gateway
- **THEN** platform-api 继续将受信任项目范围注入 runtime context，且不将其作为调用方可覆盖的业务参数
