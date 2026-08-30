## ADDED Requirements

### Requirement: 新 Runtime 包必须可安装和导入

Runtime Service SHALL use `apps/runtime-service/src/runtime_service/` as the new importable package,
and installation SHALL NOT require importing the legacy `apps/runtime-service/runtime_service/` package.

#### Scenario: 从项目根安装后导入新包

- **WHEN** 在 `apps/runtime-service` 执行锁定依赖安装并运行 Python import 检查
- **THEN** `runtime_service` resolves to the `src/runtime_service` package and import succeeds

#### Scenario: 新包导入不触碰旧实现

- **WHEN** 新 Graph modules are imported
- **THEN** no module under the legacy package is imported as a dependency

### Requirement: 生产和 Demo Graph 注册必须明确隔离

Runtime Service SHALL provide a root `langgraph.json` that registers only `reference_agent`, and a
separate `langgraph.demo.json` that registers `reference_agent` and `workflow_demo`.

#### Scenario: 生产配置加载

- **WHEN** LangGraph CLI loads `apps/runtime-service/langgraph.json`
- **THEN** it discovers exactly the new `reference_agent` Graph and its non-empty description

#### Scenario: Demo 配置加载

- **WHEN** LangGraph CLI loads `apps/runtime-service/langgraph.demo.json`
- **THEN** it discovers `reference_agent` and `workflow_demo`, each with a non-empty description

#### Scenario: 旧 Graph 不进入新配置

- **WHEN** either new configuration is inspected
- **THEN** it contains no path under `runtime_service/agents`, `runtime_service/services`, or other legacy locations

### Requirement: Agent Service 必须暴露标准异步入口

Each R0 reference Service SHALL expose `async def get_agent(config: RunnableConfig) -> Pregel`, and the
stable Graph module SHALL only re-export that entrypoint.

#### Scenario: reference_agent returns a Pregel

- **WHEN** `runtime_service.graphs.reference_agent.get_agent` is awaited with a RunnableConfig
- **THEN** it returns a compiled Pregel without contacting Platform API or a model provider

#### Scenario: workflow_demo returns a Pregel

- **WHEN** `runtime_service.graphs.workflow_demo.get_agent` is awaited with a RunnableConfig
- **THEN** it returns a compiled StateGraph Pregel without external side effects

### Requirement: R0 必须支持无 Platform API 的本地验证

The R0 baseline SHALL run with fake model or deterministic nodes and SHALL provide a minimal test path
that does not require Platform API, provider credentials, MCP, database, Redis, or Sandbox.

#### Scenario: 最小 Graph 执行

- **WHEN** the R0 tests invoke `reference_agent` with a user message
- **THEN** execution completes with a deterministic assistant response

#### Scenario: workflow deterministic execution

- **WHEN** the R0 tests invoke `workflow_demo` with its typed input
- **THEN** the graph returns the expected deterministic state transition

### Requirement: 模型行为 E2E 必须使用真实中转模型

R0 SHALL keep fake-model tests for fast feedback and SHALL provide an explicitly enabled real-model E2E
path. Text E2E MUST use the configured DeepSeek proxy; multimodal E2E MUST use the configured GPT proxy.
Missing credentials when E2E is enabled MUST fail or report not executed, and MUST NOT silently fall back
to a fake model.

#### Scenario: 显式开启真实文本模型 E2E

- **WHEN** `RUNTIME_E2E=1` and the DeepSeek proxy variables are present
- **THEN** the E2E invokes the real DeepSeek proxy model through the new Runtime entrypoint

#### Scenario: 真实模型凭据缺失

- **WHEN** `RUNTIME_E2E=1` and required proxy variables are absent
- **THEN** the E2E fails with a clear configuration result and does not substitute a fake model

#### Scenario: 默认快速测试

- **WHEN** `RUNTIME_E2E` is not enabled
- **THEN** fake-model tests remain runnable without provider credentials and are not reported as real-model E2E
