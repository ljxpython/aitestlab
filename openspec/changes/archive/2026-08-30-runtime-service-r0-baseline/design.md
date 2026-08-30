## Context

R0 只建立新 Runtime Service 的可启动基线。现有 `apps/runtime-service/runtime_service/` 是旧
实现，包含旧 Graph、旧 Auth、旧 HTTP 路由和旧配置；本次绿色重构不允许从中导入或复制代码。
目标入口是 `apps/runtime-service/langgraph.json`，Python 包采用 `src` layout。

本阶段属于 `runtime-service` 单一 locus 的 B3 变更：它改变部署入口和 Agent Service 物理归属，
但不修改 Platform API。实施前批准依据是用户明确要求“调用 OpenSpec，开始 R0”。

## Goals / Non-Goals

**Goals:**

- 让 `src/runtime_service` 可安装、可导入并被 LangGraph CLI 发现。
- 建立根级生产配置和独立 Demo 配置，避免旧 Graph 注册进入新链路。
- 提供 `reference_agent`（`create_agent`）和 `workflow_demo`（`StateGraph`）的最小正式入口，
  两者都使用 `async def get_agent(config: RunnableConfig) -> Pregel`。
- 用 fake model 和本地测试证明 Graph 注册、描述字段和无 Platform API 启动路径；在显式提供凭据时，
  用真实中转模型完成 E2E，文本走 DeepSeek，中转多模态走 GPT。

**Non-Goals:**

- 不实现 RuntimeContext、Auth、Resolver、Modeling、Middleware、Tool Policy、MCP、Backend、
  Checkpoint、Trace 或 Platform Gateway。
- 不迁移或适配旧运行行为，不双读旧包、旧配置、旧 Graph 和旧数据；旧代码仅作为已归档历史留存。
- 不创建公共 Builder、Factory、Registry、Plugin 或 Custom Route。
- 不在 R0 注册 Deep Agent、MCP、Backend 或生产业务 Agent。
- 不把真实模型密钥写入仓库、fixture、日志或 OpenSpec；只从本机 `.env`/CI Secret 注入。

## Decisions

### 1. 采用 `src` layout 和根级配置

`pyproject.toml` 使用 setuptools 的 `src` 包发现配置；`langgraph.json` 和
`langgraph.demo.json` 放在 `apps/runtime-service/` 根目录，Graph 路径指向
`./src/runtime_service/graphs/*.py`。

备选方案：继续使用旧 `runtime_service/` 目录，或创建 `runtime_service_v2/`。前者会把旧代码
带入新链路，后者会制造第二个顶层包；两者都违反绿色重构约束。

### 2. 两份配置只区分 Graph 集合

生产 `langgraph.json` 只注册 `reference_agent`；`langgraph.demo.json` 额外注册
`workflow_demo`。两份配置共享同一 Python 包和依赖，不复制 Auth、HTTP app 或环境解析。
R0 暂不配置 Auth，认证入口随 R1 一起加入；本地 fake model 不需要 Platform API 或凭据。

备选方案：直接把五个 Demo 全部注册到生产配置，或复制一份旧配置并删字段。前者扩大生产暴露面，
后者会保留旧入口漂移。

### 3. Service 组合根直接返回已编译 Graph

每个 Service 的 `agent_server.py` 在模块级完成最小组合，`get_agent` 只返回已编译的
`Pregel`。`graphs/<graph_id>.py` 只重导出该函数，不承载业务装配。

备选方案：新增统一 `build_graph()` 或公共 Factory。R0 没有跨 Service 的重复实现，增加抽象只会
隐藏官方构造函数和资源生命周期。

### 4. 使用无外部依赖的 fake model

`reference_agent` 使用 LangChain 官方 fake chat model；`workflow_demo` 使用纯函数节点。这样
Graph import、introspection 和最小 Run 不需要 Provider secret，也不会在模块导入时产生网络或
文件副作用。

备选方案：R0 直接绑定真实 Provider。真实 Provider 留到后续 smoke test；把网络凭据作为基线依赖
会让本地安装和测试不可重复。

### 5. 快速测试与真实模型 E2E 分层

快速单测固定使用 fake model，保证无凭据也能反馈；E2E 通过 `RUNTIME_E2E=1` 显式开启，必须
使用 `.env` 中的真实中转配置，缺凭据直接失败或标记未执行，不得自动改用 fake model。

备选方案：所有测试都调用真实模型。这样会让导入和配置回归依赖网络、额度和 Provider 可用性，
无法提供稳定的快速反馈。

## Risks / Trade-offs

- [R0 暂无 Auth] -> 生产配置只用于本地基线验证，不宣称可接入生产流量；R1 必须在开放生产部署前加入新 Auth。
- [旧配置已归档] -> 新根级配置和新包测试禁止引用旧路径；归档文件不属于运行时输入。
- [fake model 不代表真实模型行为] -> R0 只验证导入、注册和最小执行；模型、Tool 和 Context 行为由 R2/R3 单独验收。
- [真实中转不可用或产生费用] -> 只在 `RUNTIME_E2E=1` 时执行，并在 CI 使用 Secret/预算/超时门禁；缺凭据不能伪装通过。
- [LangGraph CLI 对 async factory 的导入行为受版本影响] -> 用锁定版本执行 config load 和 `langgraph dev` smoke；失败即修正导出形态，不增加兼容入口。

## Migration Plan

本变更不做运行时迁移。部署验证使用新根级配置和新包；回滚仅指停止使用新配置并保留旧部署，
不在新代码中增加旧入口适配。R0 验收前不得切换 Platform API 或生产流量。

## Open Questions

- R1 需要根据锁定的 LangGraph SDK 版本冻结新 Auth 的具体实现和测试向量。
- R2 再决定 `reference_agent` 的 RuntimeContext、Tool 和 Middleware 最小组合。
