# sql_agent 服务设计说明

本文说明 `runtime_service/services/sql_agent/` 的一期设计与当前实现约定。

目标：

- 在 `runtime-service` 内新增一个可注册、可测试、可演进的 SQL Agent 服务
- 一期先跑通 LangChain 官方 SQL Agent 思路，底层数据库固定为 SQLite
- 数据源直接使用官方示例文档里的公开 Chinook SQLite 数据库 URL
- 安全边界明确收敛到“只读查询”，不支持写操作
- 为后续扩展到 MySQL / PostgreSQL 预留结构，但一期不做多数据库实现
- 服务内预留图表可视化 MCP helper，供后续 SQL 结果转图表展示使用

## 1. 一期范围

一期要解决的问题：

- 用户输入自然语言问题
- agent 自动查看表清单
- agent 自动查看相关表 schema
- agent 自动生成 SQL
- agent 先做 SQL 自检，再执行查询
- agent 根据查询结果返回自然语言答案

一期明确不做：

- MySQL / PostgreSQL 连接
- 多租户
- 写操作（INSERT / UPDATE / DELETE / DROP / ALTER 等）
- 数据库连接动态切换
- 平台级权限模型与业务级审计扩展

## 2. 目标落点

代码目录固定放在：

```text
runtime_service/services/sql_agent/
  __init__.py
  graph.py
  prompts.py
  tools.py
  schemas.py
  README.md
  tests/
```

说明：

- `graph.py`：对外 graph 入口，负责装配，不承载复杂业务逻辑
- `prompts.py`：system prompt、只读约束提示、错误提示模板
- `tools.py`：SQL 相关工具装配、只读保护、数据库初始化辅助
- `schemas.py`：服务内部用到的结构定义与常量
- `tests/`：注册测试、只读保护测试、最小冒烟测试

## 3. 对外注册方式

一期只注册到：

- `runtime_service/langgraph.json`

建议 graph id：

- `sql_agent`

建议 description：

- `SQL 问答服务：基于 SQLite Chinook 示例库的只读查询 Agent，自动完成表发现、schema 检查、SQL 生成、自检与执行。`

本阶段先不注册到 `langgraph_auth.json`，避免把实现目标扩大到 OAuth 模式。

## 4. 设计原则

### 4.1 复用现有 runtime contract

该服务必须沿用现有统一链路：

1. 调用方通过 `RuntimeContext` 传公共业务参数
2. `RuntimeRequestMiddleware` 调 `resolve_runtime_settings(...)`
3. `resolve_model_by_id(...)`
4. graph / service 组装 SQL 私有 tools
5. `create_agent(...)`

也就是说：

- 不重新发明配置入口
- 不自己绕开现有模型装配体系
- 不把数据库配置塞进公共 runtime 层

### 4.2 graph 只做装配

`graph.py` 只负责：

- 解析运行时配置
- 构建模型
- 构建 SQL tools
- 挂载必要 middleware
- 返回 `create_agent(...)`

不在 `graph.py` 里：

- 写长段 prompt 模板
- 写数据库下载逻辑细节
- 写 SQL 安全判定细节
- 写测试辅助逻辑

### 4.3 只读优先

一期安全目标不是“尽量不要写”，而是“结构上不允许写”。

因此设计上要同时做三层保护：

1. prompt 约束：明确禁止 DML / DDL
2. 连接约束：SQLite 连接以只读方式打开
3. tool 约束：真正执行 SQL 前，拒绝非只读语句

如果模型生成了非只读 SQL：

- 不执行
- 返回明确错误信息
- 让 agent 自行改写为只读查询

## 5. 一期数据库策略

### 5.1 数据源

使用 LangChain 官方文档示例中的公开 SQLite 文件：

- `https://storage.googleapis.com/benchmarks-artifacts/chinook/Chinook.db`

一期约束：

- 这个 URL 直接内置在服务代码中
- 当前阶段不对外暴露自定义数据库连接能力
- 当前阶段不支持用户传入 MySQL / PostgreSQL / 自定义 SQLite 路径

### 5.2 本地缓存策略

一期建议采用“本地缓存 + 延迟准备”的策略：

- 如果本地缓存文件已存在，则直接复用
- 如果不存在，则自动下载
- 下载后的 DB 文件落到服务模块自己的本地缓存路径
- 下载与本地文件准备不放在 graph import / graph 创建阶段执行

建议缓存路径：

- `runtime_service/services/sql_agent/.cache/Chinook.db`

这样做的原因：

- 避免每次 graph 初始化都重复下载
- 避免 `langgraph dev` 启动阶段被网络 IO 卡住
- 让测试与本地调试更稳定
- 后面切换到其他数据库时，不会污染公共层目录

建议实现方式：

- `graph.py` 只创建 agent 和 tools
- 真正的 Chinook 下载与 SQLite 连接准备在 tool 首次调用时懒执行
- 下载结果做本地缓存，后续请求直接复用

### 5.3 后续演进方向

虽然一期只支持 SQLite，但内部抽象要留好两个扩展点：

- `build_sql_database(...)`：后续可切到 MySQL / PostgreSQL
- `resolve_database_uri(...)`：后续可接环境变量或服务配置

一期先固定返回内置 Chinook URL 对应的本地缓存 SQLite URI。

## 6. 工具设计

一期不建议直接把 LangChain 官方 `SQLDatabaseToolkit` 原样裸暴露后就结束，而是做“受控封装”。

建议分两层：

### 6.1 基础层：官方 SQL toolkit

使用：

- `SQLDatabase.from_uri(...)`
- `SQLDatabaseToolkit(db=db, llm=model)`
- `toolkit.get_tools()`

这会提供官方四个核心工具：

- `sql_db_list_tables`
- `sql_db_schema`
- `sql_db_query_checker`
- `sql_db_query`

### 6.2 安全层：只读执行保护

一期要对真正执行 SQL 的路径增加包装。

核心思路：

- 保留官方 `list_tables / schema / query_checker`
- 对 `sql_db_query` 增加只读校验
- 拒绝包含写操作或多语句执行的 SQL
- SQLite 连接本身也使用只读 URI 打开，而不是普通可写连接

推荐安全基线：

1. 本地缓存好 Chinook 文件
2. 使用 SQLite read-only URI 连接数据库
3. 执行前再做单语句 + 只读 SQL 校验

也就是说：

- 数据库连接层负责“物理上不可写”
- 工具层负责“逻辑上不放行危险 SQL”

最低限度要拦截的关键字：

- `insert`
- `update`
- `delete`
- `drop`
- `alter`
- `truncate`
- `create`
- `replace`
- `attach`
- `pragma`（是否允许可后续再定，一期先保守拒绝）

同时建议拒绝：

- 多条 SQL 语句拼接
- 明显的事务控制语句
- 非 `SELECT` / `WITH ... SELECT ...` 形态的语句

返回错误文案要足够明确，例如：

- `Only read-only SELECT queries are allowed in sql_agent.`

这样模型才能根据错误反馈自动改写查询。

## 7. 可视化 MCP 设计

为了后续支持“SQL 查询结果 -> 图表展示”，图表 MCP 不进入公共 `mcp/` 模块，也不暴露成公共 `mcp:<server>` 能力。

本次改为服务内单独文件封装：

- `runtime_service/services/sql_agent/chart_mcp.py`

目标：

- 图表能力只作为 `sql_agent` 私有辅助能力存在
- 不污染公共 MCP catalog
- 后续在 `create_agent(...)` 前手动把 chart tools 追加到本服务 tools 列表

默认约定：

- 后续新增 MCP，除非特别指明，都按这种方式接入
- 即：在当前服务内单独封装 helper，再在 graph 中显式 `tools.extend(...)`
- 不默认进入公共 `mcp/` 模块

服务内 helper 目标形态：

```python
from langchain_mcp_adapters.client import MultiServerMCPClient


def get_mcp_server_chart_tools():
    client = MultiServerMCPClient(
        {
            "mcp_chart_server": {
                "command": "npx",
                "args": ["-y", "@antv/mcp-server-chart"],
                "transport": "stdio",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools
```

当前实现已经收敛为静态 graph，不再通过异步工厂函数装配整个 agent；需要异步获取的 chart tools 通过 `RuntimeRequestMiddleware` 的 async resolver 在请求期处理。

接入方式：

- SQL agent 自己的只读数据库 tools 作为 required tools
- chart MCP tools 通过 graph 内的 required tool resolver 动态补入
- 最终仍由静态 `create_agent(...)` 导出统一 graph

一期约束：

- 图表 MCP 不进入公共 MCP registry
- 不出现在 `/internal/capabilities/tools`
- `sql_agent` 当前直接在 graph 装配阶段显式追加 chart tools
- 图表生成链路留到 SQL 结果结构化和前端展示协议明确后再接入

## 8. Prompt 设计

一期 prompt 建议基于官方 SQL Agent 文档模板改造，而不是从零重写。

需要保留的核心约束：

- 先看表，再看 schema
- 生成符合方言的 SQL
- 默认限制返回条数
- 先调用 query checker，再调用 query
- 执行失败后允许改写重试
- 不允许查询无关列

需要额外增强的本仓库约束：

- 这是只读服务，只允许 SELECT 类查询
- 禁止任何 DML / DDL / 事务控制语句
- 若用户请求写库、改表、删数据，要明确拒绝
- 回答尽量基于真实查询结果，不编造

建议 prompt 模板支持以下可变项：

- `dialect`
- `top_k`
- `database_name`

一期默认值建议：

- `dialect = sqlite`
- `top_k = 5`
- `database_name = Chinook`

## 9. graph 设计

一期 graph 选择 `create_agent` 范式。

原因：

- SQL Agent 本质是“单智能体 + 工具调用”问题
- 不需要显式状态流
- 不需要 deepagent 级任务分解
- 和 LangChain 官方文档实现最接近，迁移成本最低

建议骨架：

```python
graph = create_agent(
    model=BASELINE_MODEL,
    tools=BASELINE_PRIVATE_TOOLS,
    middleware=[
        RuntimeRequestMiddleware(
            defaults=SQL_AGENT_DEFAULTS,
            required_tool_resolver=_resolve_required_tools,
            arequired_tool_resolver=_aresolve_required_tools,
            system_prompt_resolver=_build_sql_system_prompt,
        )
    ],
    system_prompt=_build_sql_system_prompt(...),
    context_schema=RuntimeContext,
    name="sql_agent",
)
```

说明：

- 一期不强制接入多模态 middleware
- 一期不强制接入 HITL middleware
- 一期先把“只读 SQL 问答主链路”跑通
- graph 顶层不重建拓扑，重资源通过 resolver / lazy helper 延迟处理

如果后续发现需要人工审批，再单独加：

- `HumanInTheLoopMiddleware(interrupt_on={"sql_db_query": True})`

## 10. 配置设计

一期尽量少引入新配置。

建议先把服务内默认值写死在模块内部：

- Chinook 下载 URL
- 本地缓存路径
- 默认 `top_k=5`

如果需要最小可调参数，一期只建议开放：

- `sql_agent_top_k`

这些参数不进入公共 `RuntimeContext`，而是在 `services/sql_agent/` 内部自行解析。

建议读取顺序：

1. `config.configurable`
2. 环境变量
3. 服务模块默认值

建议参数名：

- `config.configurable["sql_agent_top_k"]`
- 环境变量 `SQL_AGENT_TOP_K`

说明：

- `sql_agent_database_url` 暂不对外开放
- Chinook URL 先固定内置在代码里
- MySQL / PostgreSQL 的外部配置能力留到后续版本

## 11. 测试设计

一期至少补三类测试。

### 11.1 注册测试

目标：

- 确保 `langgraph.json` 中存在 `sql_agent`
- 确保注册条目带 `description`

### 11.2 只读保护测试

目标：

- `SELECT ...` 通过
- `INSERT/UPDATE/DELETE/DROP/...` 被拒绝
- 多语句执行被拒绝

### 11.3 最小冒烟测试

目标：

- 能构造 SQLite `SQLDatabase`
- 能成功生成 SQL toolkit
- graph 或 agent 至少可正常创建

### 11.4 真实执行链路只读测试

目标：

- 即使绕过 prompt，执行层仍拒绝写 SQL
- SQLite 连接以只读模式打开时，写入语句会失败

说明：

- 测试不要依赖在线下载成功
- 冒烟测试优先使用本地临时 SQLite 文件或 mock
- 公网 Chinook 下载更适合作为手工验证，不作为单元测试硬依赖

## 12. 手工验证路径

一期代码完成后，建议按这个顺序验证：

1. 跑服务相关 pytest
2. 跑 `uv run python -m compileall runtime_service`
3. 启动：`uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser`
4. 在 `sql_agent` 上发起问题，例如：
   - `Which genre on average has the longest tracks?`
   - `List the top 5 customers by total spending.`
   - `Show the schema of the Invoice table.`
5. 再验证拒绝案例，例如：
   - `Delete all invoices.`
   - `Drop the Artist table.`

期望结果：

- 查询类问题可正常回答
- 写操作类请求被明确拒绝

## 13. 后续演进路线

### Phase 2：MySQL / PostgreSQL

扩展方向：

- 支持从配置读取 DB URI
- 支持切换数据库方言
- 保持同一套 graph 和 prompt 结构

### Phase 3：更强安全策略

扩展方向：

- 加入 HITL 审批 SQL 执行
- 按表白名单限制可访问范围
- 增加 query timeout / row limit / result truncation
- 让查询结果可选接入服务内 chart MCP helper 做图表生成

### Phase 4：平台化能力

扩展方向：

- 接平台数据库配置中心
- 接审计日志
- 接项目级数据源管理

## 14. 本次实现建议顺序

接下来建议按以下步骤开发：

1. 建目录与 `README.md`
2. 写 `chart_mcp.py`
3. 写 `prompts.py`
4. 写 `tools.py`（含 SQLite 下载、本地缓存、只读 SQL 执行保护）
5. 写 `graph.py`
6. 注册 `langgraph.json`
7. 补 `tests/`
8. 跑 pytest + compileall + 本地联调

一句话总结：

> 一期先做一个结构清晰、只读安全、基于官方 SQLite Chinook 示例库的 `create_agent` 型 SQL Agent 服务，先把最短可用链路跑通，再向 MySQL / PostgreSQL 演进。
