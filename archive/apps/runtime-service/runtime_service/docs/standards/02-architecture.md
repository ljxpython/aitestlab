# LangGraph v2 架构说明（Graph-Native + Runtime Contract）

## 作用范围

- `runtime_service` 是 `runtime-service` 下独立维护的执行层。
- 目标是保持一个统一且简单的心智模型：`静态 graph 导出 + RuntimeContext + 共享 runtime middleware`。

## 核心约定

统一采用四条运行时通道，各干各的，别串味：

1. `RuntimeContext`
2. `config`
3. `config.configurable`
4. `env`

约定如下：

- `RuntimeContext` 是唯一主业务输入通道
- `config` 只承担执行控制
- `config.configurable` 只承担线程、平台、鉴权、服务私有字段
- `env` 只承担部署默认值与 secrets
- graph 默认静态导出，不默认使用 `make_graph(...)`
- 动态行为优先放进共享 middleware / resolver，不靠每次 run 重建 graph

## 关键目录

- `runtime_service/langgraph.json`：graph 注册表、HTTP app 挂载点、CORS 与 `.env` 加载入口。
- `runtime_service/runtime/context.py`：共享 `RuntimeContext` 定义，约束模型、工具、租户等运行时字段。
- `runtime_service/runtime/runtime_request_resolver.py`：运行时解析入口，负责把 `RuntimeContext` + 默认值收敛成模型、prompt、tools。
- `runtime_service/runtime/modeling.py`：模型 ID -> ChatModel 解析入口。
- `runtime_service/tools/registry.py`：工具 catalog 唯一真源，负责统一注册内建工具与 MCP 工具。
- `runtime_service/custom_routes/tools.py`：工具能力对外暴露层，不是工具真源。
- `runtime_service/middlewares/`：共享横切能力目录，后续公共 runtime 解析层也应收敛在这里。
- `runtime_service/services/`：业务服务模块目录，推荐承载生产智能体能力。
- `runtime_service/agents/`：demo / 范式样板目录。

说明：

- `agents/` 作为 demo/范例保留。
- 新增业务能力优先落在 `services/`，目录规范见 `docs/07-service-modularization.md`。

## graph 形态约定

默认推荐三种静态导出方式：

- `graph = create_agent(...)`
- `graph = create_deep_agent(...)`
- `graph = builder.compile()`

默认不推荐：

- 把 `make_graph(config, runtime)` 当成所有 graph 的标准入口
- 仅为了动态切模型、改 prompt、筛工具而重建 graph

只有满足下面条件时，才允许保留薄 factory：

- 工厂期必须读取 `ServerRuntime`
- 工厂期必须装配执行期无法延迟解析的重资源
- 无法通过静态 graph + `RuntimeContext` + middleware 完成
- 即便使用 factory，graph 拓扑仍必须稳定

## 运行时流程

1. LangGraph 根据 `langgraph.json` 定位 graph 入口与自定义 HTTP app。
2. graph 静态导出，并声明 `context_schema=RuntimeContext`。
3. `platform-api` 注入可信身份字段，run payload 通过 `context` 和 `config` 进入运行时。
4. 共享 runtime middleware / resolver 读取 `RuntimeContext`，解析模型、prompt、工具集合等动态能力。
5. middleware 在模型调用前完成 override，工具在运行时通过 `ToolRuntime.context` 读取业务上下文。
6. graph 用静态结构执行本次任务，不在 run 期间重建拓扑。

## 动态能力规则

动态能力不是不能做，而是要走对位置：

- 模型切换：通过共享 middleware / resolver 完成
- `system_prompt` 覆盖：通过 `RuntimeContext` + middleware 完成
- 工具动态控制：通过静态 registry + 运行时筛选完成
- `skills` / `subagents`：当前只作为 deepagent 内部静态能力，不进入公开 runtime contract

明确禁止：

- 前端上传任意工具实现
- run payload 动态改 graph 拓扑
- 把公共业务字段长期塞进 `config.configurable`
- 把 secrets 放进 assistant `context` / `config`

## 多 Graph 设计规则

- `assistant`、`research_demo`、`deepagent_demo`、`test_case_agent` 共享同一套 runtime contract。
- `deepagent` 默认也按静态 graph 收敛，`skills` / `subagents` 保持静态注册。
- 不再保留 `graph_entrypoint.py` 这类兼容导出文件。
- 工具对外展示可以走 `custom_routes/tools.py`，但 graph 内部仍以 `tools/registry.py` 为唯一真源。

## 当前状态说明

本文描述的就是 `runtime_service` 当前主线架构。

已经明确完成的收口：

- `runtime/options.py` 已删除
- `graph_entrypoint.py` / `graph_legacy.py` 已删除
- `usecase_workflow_agent` 已删除
- 主线 graph 已不再使用 `make_graph(...)` 作为默认导出
- live/debug 脚本已切到 `RuntimeContext + RuntimeRequestMiddleware`

如果其他应用层仍然引用旧入口，直接改调用方；**不在 `runtime_service` 内保留 compat 层**。

## 启动示例

```bash
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser
```
