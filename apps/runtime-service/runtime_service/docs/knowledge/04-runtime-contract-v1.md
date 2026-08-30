# runtime_service 运行时契约 v1

> 历史讨论：本文不作为新 Runtime 实现依据。新架构契约以
> `14-runtime-contracts-and-resolution-design.md` 为准；本文中的 `enable_tools`、身份字段
> 布局和 Tool Registry 设计均已废弃。

> 本文档用于固化 `runtime_service` 后续重构的统一约束。
> 目标不是解释历史现状，而是给出接下来应收敛到的标准范式。
> 当前讨论按“重做”处理，不考虑旧字段兼容、不考虑旧 assistant 数据迁移。

## 1. 总原则

统一采用四层职责分离：

1. `RuntimeContext`
2. `config`
3. `config.configurable`
4. `env`

统一规则：

- `RuntimeContext` 是唯一主业务输入通道
- `config` 只承担执行控制
- `config.configurable` 只承担线程、平台、服务私有字段
- `env` 只承担部署默认值和 secrets
- 默认优先静态导出 graph
- 只有例外场景才保留薄 `make_graph(config, runtime)`

## 2. graph 形态约定

默认推荐：

- `graph = create_agent(...)`
- `graph = create_deep_agent(...)`
- `graph = builder.compile()`

### 2.1 官方对静态 graph 与 factory 的建议摘要

官方默认推荐的是静态 graph，而不是默认使用 `make_graph(...)` factory。

官方更推荐的常规方式：

- 顶层直接导出已编译 graph
- 大多数定制放在 graph 内部完成
- 通过 `context`、`config`、middleware、tool runtime 做动态行为

官方建议使用 `make_graph(...)` / graph factory 的典型场景：

1. 每次 run 确实需要重建 graph
2. 工厂期需要 setup / teardown 重资源
3. 必须读取服务端工厂上下文（`ServerRuntime`）来决定装配方式
4. 按 graph 做部署层 / tracing 层包装

官方不建议为了下面这些需求引入 factory：

- 普通运行参数动态传入
- 模型、prompt、temperature 这类 run-level 业务输入
- graph 内部可以完成的条件分支
- 仅为了“图看起来更灵活”而动态重建 graph

额外注意：

- factory 不只在 run 执行时被调用
- 也可能在读状态、更新状态、读取 assistant schema 等场景被调用
- 不同 access context 下返回的 graph 拓扑必须一致

因此本项目的统一约定保持不变：

- 默认静态导出 graph
- 只有极少数确实需要 graph rebuild 的例外场景才允许薄 factory

例外才允许：

```python
async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    ...
```

允许保留 factory 的前提：

- 工厂期必须读取服务端上下文
- 工厂期必须装配无法在执行期延迟解析的重资源
- 且无法通过静态 graph + middleware + runtime context 完成

否则一律按静态 graph 收敛。

## 3. 最终运行时契约表

### 3.1 `RuntimeContext`

`RuntimeContext` 是唯一主业务输入通道。

| 字段 | 用途 | 写入方 | 前端可改 | 备注 |
|---|---|---|---|---|
| `user_id` | 当前用户身份 | `platform-api` 鉴权注入 | 否 | 可信只读 |
| `tenant_id` | 当前租户作用域 | `platform-api` 鉴权注入 | 否 | 可信只读 |
| `role` | 当前角色 | `platform-api` 鉴权注入 | 否 | 可信只读 |
| `permissions` | 当前权限列表 | `platform-api` 鉴权注入 | 否 | 可信只读 |
| `project_id` | 当前项目作用域 | `platform-api` 项目注入 | 否 | 前端只切项目，不直写字段 |
| `model_id` | 本次运行模型 | assistant 默认值或 run 覆盖 | 是 | 主业务参数 |
| `system_prompt` | 本次运行业务提示词 | assistant 默认值或 run 覆盖 | 是 | 主业务参数 |
| `temperature` | 采样参数 | assistant 默认值或 run 覆盖 | 是 | 主业务参数 |
| `max_tokens` | 输出长度限制 | assistant 默认值或 run 覆盖 | 是 | 主业务参数 |
| `top_p` | 采样参数 | assistant 默认值或 run 覆盖 | 是 | 主业务参数 |
| `enable_tools` | 是否开启工具 | assistant 默认值或 run 覆盖 | 是 | 主业务参数 |
| `tools` | 可用工具白名单 | assistant 默认值或 run 覆盖 | 是 | 只能传工具名，不传工具实现 |

结论：

- `model_id / system_prompt / temperature / max_tokens / top_p / enable_tools / tools`
  后续统一归 `RuntimeContext`
- 不再把这些字段长期放在 `config.configurable`

### 3.2 `config`

`config` 只承担执行控制。

| 字段 | 用途 | 写入方 | 前端可改 | 备注 |
|---|---|---|---|---|
| `recursion_limit` | 执行深度限制 | assistant 默认值或 run 覆盖 | 是 | 执行控制 |
| `tags` | tracing / 观测标签 | 服务端或调用方 | 是 | 非业务字段 |
| `metadata` | 搜索、审计、观测元数据 | `platform-api` 主注入 | 部分 | `project_id` 可冗余存放 |
| `callbacks` | LangChain callbacks | 服务端 | 否 | 不开放给前端 |
| `run_name` | 执行命名 | 服务端或调用方 | 可选 | 非核心字段 |
| `max_concurrency` | 并发控制 | 服务端 | 否 | 不开放给前端 |

结论：

- `config` 不再承担业务运行参数主入口职责
- `metadata.project_id` 允许保留，但只作为检索与审计字段，不是业务真源

### 3.3 `config.configurable`

`config.configurable` 只承担线程、平台、服务私有字段。

| 字段 | 用途 | 写入方 | 前端可改 | 备注 |
|---|---|---|---|---|
| `thread_id` | 线程绑定 | SDK / 平台 / LangGraph | 间接 | 平台字段 |
| `checkpoint_id` | checkpoint 恢复 | SDK / 平台 / LangGraph | 间接 | 平台字段 |
| `assistant_id` | assistant 目标 | SDK / 平台 / LangGraph | 间接 | 平台字段 |
| `graph_id` | graph 目标 | SDK / 平台 / LangGraph | 间接 | 平台字段 |
| `langgraph_auth_user_id` | 上游 auth 注入 | LangGraph auth | 否 | 可信平台字段 |
| `langgraph_auth_user` | 上游 auth 注入对象 | LangGraph auth | 否 | 可信平台字段 |
| `test_case_multimodal_parser_model_id` | 服务私有 override | 服务端 / debug | 有条件开放 | 私有字段 |
| `interaction_data_service_url` | 服务私有 upstream | 服务端 | 否 | 私有字段 |
| `interaction_data_service_token` | 服务私有 token | 服务端 | 否 | 私有字段 |
| `test_case_backend_root_dir` | 本地调试路径 | 服务端 / devtools | 否 | 仅开发期 |
| `deepagents_backend_root_dir` | 本地调试路径 | 服务端 / devtools | 否 | 仅开发期 |

结论：

- 允许保留少量服务私有字段在 `configurable`
- 不允许继续把公共业务字段长期塞回 `configurable`

### 3.4 `env`

`env` 只承担部署默认值与 secrets。

| 字段类别 | 用途 | 备注 |
|---|---|---|
| 环境标记 | 部署默认值 | 如 `APP_ENV` |
| 模型提供商配置 | 默认 provider / base url / api key | 只作默认值 |
| 三方服务地址 | runtime 默认 upstream | 只作默认值 |
| token / 密钥 | secrets | 不进入 assistant/context/config |

结论：

- `env` 不再承担“每次 run 的业务输入”
- 所有 secrets 一律不进入 assistant `context/config`

## 4. 动态能力边界

静态 graph 仍然允许动态运行参数。

允许动态的：

- `RuntimeContext.model_id`
- `RuntimeContext.system_prompt`
- `RuntimeContext.temperature`
- `RuntimeContext.max_tokens`
- `RuntimeContext.top_p`
- `RuntimeContext.enable_tools`
- `RuntimeContext.tools`
- `config.recursion_limit`
- `config.tags`
- `config.metadata`
- `config.configurable.thread_id`
- `config.configurable.checkpoint_id`
- 服务私有 override

不允许动态的：

- 前端上传任意工具实现
- 前端指定任意 MCP endpoint 并要求服务端现场接入
- 前端通过 payload 覆盖可信身份字段
- 前端动态改 graph 拓扑

### 工具动态规则

推荐方式：

1. graph 静态注册稳定工具全集
2. 运行时根据 `RuntimeContext.enable_tools/tools` 做筛选
3. 工具内部通过 `ToolRuntime.context` 读业务上下文

不推荐方式：

- 每次 run 从前端输入动态构造新工具对象
- 每次 run 现场装配不受控的外部工具实现

### 4.1 动态能力的推荐实现方式

统一推荐：

1. graph 静态导出
2. 显式声明 `context_schema=RuntimeContext`
3. 用共享 middleware / resolver 解析模型、prompt、tools
4. 工具内部通过 `ToolRuntime.context` 读取业务上下文

其中：

- 模型切换走共享 middleware / resolver
- `system_prompt` 覆盖走 `RuntimeContext + middleware`
- 工具动态控制走静态 registry + 运行时筛选

不再推荐：

- 为 run-level 动态参数引入默认 factory
- 把模型、prompt、工具控制散落在各 graph 里自己解析

## 5. assistant 默认值与 run 覆盖优先级

业务字段优先级：

1. 服务端可信注入
2. run `context`
3. assistant 默认 `context`
4. 服务私有 `config.configurable`
5. `env`
6. 代码默认值

执行控制优先级：

1. run `config`
2. assistant 默认 `config`
3. 服务端默认值

## 6. assistant 持久化语义

assistant 三段结构继续保留，但语义收紧：

| assistant 字段 | 语义 |
|---|---|
| `assistant.context` | 业务默认运行参数 |
| `assistant.config` | 默认执行控制参数 |
| `assistant.metadata` | 检索、展示、审计元数据 |

正确示例：

- `assistant.context.model_id`
- `assistant.context.enable_tools`
- `assistant.context.tools`
- `assistant.config.recursion_limit`

不再推荐：

- `assistant.config.configurable.model_id`
- `assistant.config.configurable.system_prompt`
- `assistant.config.configurable.tools`

## 7. 明确禁止的错误放法

| 错误放法 | 原因 | 正确去向 |
|---|---|---|
| 前端直接写 `user_id/tenant_id/project_id` 到 `context` | 不可信 | `platform-api` 注入 |
| 长期把 `model_id/system_prompt/tools` 放 `configurable` | 业务与平台通道混淆 | `RuntimeContext` |
| 把 `project_id` 只放 `metadata` 当业务真源 | 语义太弱 | `RuntimeContext.project_id` |
| 把 secrets 放 assistant `config/context` | 泄漏风险高 | `env` |
| 前端上传任意工具定义 | 安全和治理失控 | 只传工具名白名单 |

## 8. 已确认边界与暂缓项

### 8.1 graph 形态目标

当前统一目标已经确认：

- `assistant_agent`
- `research_agent`
- `deepagent_agent`
- `test_case_service`

都优先按静态 graph 收敛。

结论：

- 默认按静态 graph 设计
- 只有未来出现真实硬阻塞，才重新评估是否保留薄 factory

### 8.2 `skills` / `subagents`

结论已确认：

- 不进入 v1 公开 runtime contract
- 先只作为 deepagent 内部静态能力
- 若未来开放，优先考虑 `profile` / `preset` 形式

### 8.3 `environment`

结论已确认：

- 不作为前端主输入
- 归回部署默认值与 secrets 概念

### 8.4 工具白名单治理

当前结论：

- `RuntimeContext.tools` 继续保留
- 细颗粒度白名单治理模型暂缓到后续阶段
- 当前不阻塞静态 registry + 运行时筛选这条主线

### 8.5 服务私有 override 白名单

当前结论：

- 允许少量服务私有字段继续保留在 `config.configurable`
- 精确白名单治理暂缓到后续阶段

### 8.6 错误策略

当前结论已确认：

- 非法 `model_id` 直接报错
- 非法 `tools` 直接报错
- 非法 runtime 参数直接报错
- 不做静默兜底

### 8.7 run override 权限边界

当前结论：

- 权限模型暂缓到后续阶段
- 当前先不设计更细的 override 权限系统

## 9. 对应上层系统的影响

### `platform-api`

需要配合调整：

- `runtime_gateway` 的项目注入逻辑改成更坚定的 `context-first`
- `parameter_schema` 以 `context` 作为主运行参数区
- assistant create/update 与 run create/stream 的 payload 规则同步收紧

### `platform-web-v2`

需要配合调整：

- assistant 创建 / 编辑页把 `model_id/enable_tools/tools` 迁到 `context`
- schema editor 同时支持 `context` 与 `config`
- 若后续支持会话级 override，再补 run-level `context`

## 10. 当前状态说明

本文档代表早期讨论范式，不等同于当前新 Runtime 契约。

当前代码中仍存在：

- `configurable-first` 倾向
- assistant graph 尚未全量接入 `context_schema=RuntimeContext`
- 平台 schema / 编辑页仍按旧口径组织字段
- 模型切换 / 工具筛选尚未完全收敛到共享 middleware / resolver

后续重构不得以本文档为准，统一以 14 号文档为准。
