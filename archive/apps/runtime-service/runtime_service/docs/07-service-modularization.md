# runtime_service 业务服务模块化开发规范

本文定义在 **同一运行时（单进程/单部署）** 内做“多业务智能体服务”的推荐组织方式。

目标：

- 让 `agents/` 只承担 demo/范例，不承载业务落地代码
- 让业务能力以“服务模块”的方式沉淀，可独立演进、可测试、可注册
- 让共享能力留在公共层，避免服务之间形成网状依赖

## 1. 目录约定

### 1.1 分层与职责

- 公共层（跨服务复用、稳定契约）：
  - `runtime/`：运行时参数解析与统一契约
  - `tools/`：公共工具池与装配
  - `mcp/`：MCP server 清单与装配
  - `auth/`：鉴权
  - `middlewares/`：横切能力（例如多模态）
  - `custom_routes/`：跨服务通用的能力查询/健康检查类路由

- 业务层（按服务模块沉淀）：
  - `services/<service_name>/...`

- 范例层（仅 demo，不承载业务）：
  - `agents/`：保留演示图与范例，不再作为业务默认落点

### 1.2 每个服务的最小目录

建议每个服务至少包含：

```text
runtime_service/services/<service_name>/
  __init__.py
  graph.py
  tools.py
  prompts.py
  schemas.py
  README.md
  tests/
```

要求：

- `graph.py` 必须导出 `graph`（默认推荐静态顶层导出）
- `README.md` 说明该服务的用途、入口 graph id、最小运行参数、验证方式
- `tests/` 至少包含一个“注册/冒烟”层面的测试（不要依赖外部服务）

## 2. graph 注册约定

### 2.1 统一注册点

所有对外可用的 graph 必须注册到：

- `runtime_service/langgraph.json`
- 如需鉴权对照，再同步到 `runtime_service/langgraph_auth.json`

### 2.2 命名约定

建议用“服务前缀 + 功能后缀”的 graph id：

- `text_to_sql`（服务默认入口）
- `text_to_sql_debug`
- `text_to_sql_eval`

要求：

- 每个 graph 条目必须写清 `description`（仓库有测试要求）
- 同一服务的多个 graph，描述要区分“入口/用途/是否 debug/是否 destructive”

## 3. 依赖边界（最重要）

### 3.1 禁止服务之间直接依赖

禁止：

- `services/a` import `services/b`
- 服务 A 直接复用服务 B 的 prompt、tool、schema

理由：服务之间一旦互相 import，会把“模块化”退化成“隐式单体”，最终难以演进。

允许：

- 服务依赖公共层（`runtime/*`、`tools/*`、`middlewares/*` 等）
- 如果某段能力真的跨服务共享：下沉到公共层，或在服务内复制一份（优先避免耦合）

### 3.2 私有优先：tools / MCP / skills 默认都不共享

默认规则：

- 新增业务服务时，`tools`、`MCP`、`skills` 一律先按“服务私有”设计
- 没有明确的跨服务复用诉求前，不要把服务能力放进公共 `tools/registry.py`
- 没有明确的跨服务复用诉求前，不要把服务内 MCP 放进公共 `runtime_service/mcp/servers.py`
- 服务的私有 skill 只放在 `services/<service>/skills/`，不要抽到公共目录

公共层与私有层的分工：

- 公共工具池（`tools/registry.py`）只放“跨服务通用、稳定、低业务耦合”的工具
- 服务私有工具放在 `services/<service>/tools.py`，由该服务 graph 显式装配
- 服务私有 MCP 放在 `services/<service>/` 内部模块中，由该服务 graph 显式装配
- 只有在用户或架构明确要求“做成跨服务共享能力”时，才进入公共 `mcp/` 模块与公共 catalog

推荐范式：

- 服务 graph 默认不要无脑调用公共 `build_tools(options)` 作为起点
- 优先在服务内显式组装“该服务真正需要的最小工具集合”
- 如果某个服务确实要接入公共工具，必须是显式 opt-in，而不是默认全量继承

简单说：

- 公共层是“被批准后共享”
- 服务层是“默认私有”

补充推荐：

- 如果服务私有 MCP 未来可能独立部署到另一台机器，默认优先选 `SSE/HTTP` 这类网络传输
- `stdio` 只适合本机联调或单机进程内临时验证，不应作为长期默认方案
- 服务 graph 内部应只关心“私有 MCP spec 如何装配”，不要把部署耦合写死在公共 catalog 里

这样做的目的不是故作姿态，而是避免两个常见烂坑：

- 一个服务新增的 MCP/server 被别的服务意外继承，污染 agent 工具面
- 一个强业务耦合 tool 被误放进公共层，后续改一个服务把其他服务一起打穿

### 3.3 服务私有工具装配范式

推荐结构：

```python
tools: list[Any] = []

# 1. 服务私有 MCP
tools.extend(await build_service_private_mcp_tools(service_config))

# 2. 服务私有业务工具
tools.extend(build_service_private_tools(service_config))

# 3. skills 相关文件系统能力
# 由 create_deep_agent(..., skills=[...], backend=...) 自动提供
```

约束：

- `services/<service>/graph.py` 对最终进入 agent 的工具集合负责
- 如果没有特殊说明，服务 graph 不应默认装配公共 builtin tools、公共 MCP tools
- `runtime_service/mcp/servers.py` 只登记“明确对多个服务开放”的共享 MCP server
- `runtime_service/tools/registry.py` 只处理公共能力，不承担服务私有装配职责

## 4. 运行时配置与服务配置

统一要求：

- 服务必须走同一套运行时解析链路（`RuntimeContext + RuntimeRequestMiddleware + resolve_runtime_settings(...)`），不要重新发明一套配置入口
- 服务级的默认值（例如默认 system prompt、默认工具集合）应写在服务模块内部

推荐约定（便于跨服务共存）：

- 服务特有的可配置项使用“服务前缀”命名，例如：
  - `text_to_sql_*`
  - `review_bot_*`

## 5. 测试与验证

### 5.1 最小测试要求

每个服务至少提供：

- 1 个注册测试：确保 `langgraph.json` 中存在对应 graph id
- 1 个本地冒烟测试：在不依赖外部系统的情况下验证关键逻辑（可 mock）

### 5.2 变更验证清单

- 跑 `uv run python -m compileall runtime_service`
- 跑与改动服务相关的 pytest
- 若更改了对外 graph 行为或参数，更新该服务的 `README.md`

## 6. 文档约定

必须维护：

- `services/<service>/README.md`：面向开发者的“如何使用/如何验证”
- `docs/README.md`：只做入口与阅读顺序，不要把服务细节堆进去

## 7. 迁移策略（从 agents 走向 services）

建议按服务逐步迁移：

1. 新服务一律从 `services/` 起步
2. 旧的 demo 仍留在 `agents/`，但不再作为新增功能默认落点
3. 若需要从 demo 升格为业务服务：复制到 `services/<service>/` 并重新注册 graph id
