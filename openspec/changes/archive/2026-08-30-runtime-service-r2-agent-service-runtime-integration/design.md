## Context

R1 的 Runtime 层已经把不可信 Context、Principal、Policy 和 AgentDefaults 解析为不可变的 `ResolvedRuntimeConfig`，并提供 `build_model`。R0 的 `reference_agent` 仍在模块导入时创建固定 fake graph，因此无法证明 Service 组合根会使用这些边界。

本变更只覆盖 `apps/runtime-service` 的新 `src/runtime_service` 包。LangGraph Server 仍通过 `graphs/<graph_id>.py:get_agent` 导入，Service 自己负责组合；Platform API、旧归档包、Middleware、Tool Registry、MCP 和 Durable Checkpoint 不在本阶段实现。

## Goals / Non-Goals

**Goals:**

- 让 `reference_agent` 在 `get_agent(config)` 中显式完成 Context 解析、默认值合并、策略校验和模型选择。
- 使用 LangChain 官方 `create_agent` 的 `context_schema=RuntimeContext`，让每次 invoke 的 `context` 保持只读且类型明确。
- 保留无外部依赖的 fake model 测试，同时允许配置真实 DeepSeek/GPT Provider 做 E2E。
- 让本地直接调用 `get_agent({})` 可以工作，便于不启动 Platform API 调试。
- 让静态 `workflow_demo` 保持原有确定性 StateGraph 实现。

**Non-Goals:**

- 不创建通用 `build_graph`、Builder、Factory、Registry 或新的公共运行时层。
- 不把 Platform 身份、JWT 或数据库接入 Service；R2 使用本地明确声明的演示 Principal/Policy。
- 不把 fake model 作为生产模型 fallback；真实模型凭据缺失时必须显式失败。
- 不修改旧目录、旧 Graph ID、Platform API、langgraph Server 路由或持久化格式。

## Decisions

### 1. 组合根直接调用 R1 公共函数

`reference_agent/agent_server.py` 保留一个很小的私有 `_resolve(config)`：从 `config.get("context")` 读取新 Context，使用服务声明的 `AgentDefaults`、演示 `RuntimePrincipal` 和 `RuntimePolicy` 调用 `resolve_runtime_config`，再由 `build_model` 构造模型。这样依赖方向清晰，且没有万能 Builder。

替代方案：在 Runtime 新增 Agent Factory 或在 `graphs/` 统一解析。前者增加单实现抽象，后者会把业务默认值和外部资源带入部署契约层，均拒绝。


### 2. Fake 模型只通过显式测试注入

Service 组合根支持一个仅供测试的 `config["configurable"]["model"]` 注入对象；未提供时严格使用 `build_model(resolved)`。测试注入不改变 Context/Policy 解析，也不进入生产配置文件。

替代方案：在 `build_model` 内增加 fake fallback。该方案会掩盖 Provider 配置错误并违反 R1 的 fail-closed 要求，拒绝。

### 3. Graph 生命周期按资源需求选择

`reference_agent` 的模型和图不依赖 Thread 外部资源，因此每次 `get_agent` 可返回同一个已编译 graph；但 Context 仍在每次 invoke 时由 LangGraph 传入。为保证不同运行配置不会共享错误模型，只有默认配置路径缓存静态 graph，测试注入或显式 Context 模型覆盖路径按调用重新构建。

替代方案：所有调用都动态编译。虽然简单但浪费模型/图构造，且没有 Open SWE 的线程资源需求；拒绝。

### 4. `with_config` 只绑定 Server 构建配置

`get_agent(config)` 返回的 graph 使用 `graph.with_config(config)`，用于保留 LangGraph Server 的 tags、metadata 和 configurable。业务 Runtime Context 不塞进 `configurable`，而在 invoke 的 `context` 字段传递，避免把身份和模型配置混入持久化线程配置。

## Risks / Trade-offs

- [演示 Principal/Policy 不是生产授权] -> R2 README 和测试明确标注；R3/R4 前不宣称 Platform 集成完成。
- [每次显式 Context 模型覆盖都重新编译 graph] -> 只在覆盖路径发生；默认路径使用静态缓存，后续有 Thread 资源时再采用异步工厂。
- [LangChain 版本的 `context_schema` 行为变化] -> 锁定当前依赖并用 `ainvoke(..., context=RuntimeContext(...))` 做组合测试。
- [真实 Provider 不可用导致 E2E 失败] -> 单元测试使用 fake 注入；真实 E2E 仅在 `RUNTIME_E2E=1` 且环境变量齐全时执行，不把跳过当作通过。

## Migration Plan

无数据迁移。实现完成后只切换新 `reference_agent` 组合根，旧包继续留在 `archive/`。失败时回滚本 OpenSpec 变更的代码即可。

## Open Questions

无。Platform 注入真实 Principal/Policy 的契约留到 P1 讨论。
