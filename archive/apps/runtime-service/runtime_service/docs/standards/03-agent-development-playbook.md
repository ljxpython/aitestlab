# runtime_service 智能体开发团队规范（Playbook）

本文是团队在 `runtime_service` 下开发智能体的统一实践，目标是：

- 运行时契约单一
- graph 形态简单稳定
- 动态能力走官方推荐路径，不靠工厂乱拼

## 1. 总原则

- `context-first`：公共业务运行参数优先进入 `RuntimeContext`。
- `config-for-control`：`config` 只承担执行控制，不承担主业务输入。
- `configurable-for-platform`：`config.configurable` 只放线程、平台、鉴权、服务私有字段。
- `env-for-defaults-and-secrets`：`env` 只放部署默认值与 secrets。
- `static-first`：graph 默认静态导出，能不写 `make_graph(...)` 就不写。
- `middleware-first`：模型切换、prompt 覆盖、工具动态控制优先通过共享 middleware / resolver 完成。
- `direct-error`：非法 `model_id`、非法 `tools`、非法 runtime 参数直接报错，不做静默兜底。

## 2. 运行时字段归位

### 2.1 `RuntimeContext`

这里放公共业务字段，例如：

- `user_id`
- `tenant_id`
- `project_id`
- `model_id`
- `system_prompt`
- `temperature`
- `max_tokens`
- `top_p`
- `enable_tools`
- `tools`

### 2.2 `config`

这里只放执行控制，例如：

- `recursion_limit`
- `tags`
- `metadata`
- `callbacks`

### 2.3 `config.configurable`

这里只放线程、平台和服务私有字段，例如：

- `thread_id`
- `checkpoint_id`
- `assistant_id`
- `langgraph_auth_*`
- 少量服务私有 override

### 2.4 `env`

这里只放部署默认值与 secrets，例如：

- provider 默认配置
- 上游服务默认地址
- token / api key

## 3. 模式选型规则

### 3.1 什么时候用 `create_agent`

适用：

- 单智能体为主
- 线性对话流程
- 需要模型 + 工具循环
- 需要 middleware、多模态、HITL 等横切能力

推荐方式：

- 顶层静态导出 `graph = create_agent(...)`
- 显式传 `context_schema=RuntimeContext`
- 通过共享 middleware 处理模型切换、prompt 覆盖、工具筛选

### 3.2 什么时候用 `builder.compile()`

适用：

- 需要显式状态流
- 需要 handoff、条件推进、步骤切换
- 流程结构本身就是主要设计对象

推荐方式：

- 顶层静态导出 `graph = builder.compile()`
- 运行时业务字段仍然走 `RuntimeContext`
- 不因为流程复杂就把 runtime contract 搞成两套

### 3.3 什么时候用 `create_deep_agent`

适用：

- 复杂多步任务
- 强任务分解 / 规划能力
- 工具链长，执行路径不固定
- 需要文件系统产物、长期任务执行

推荐方式：

- 顶层静态导出 `graph = create_deep_agent(...)`
- `skills` / `subagents` 静态配置
- 对外 runtime contract 仍只暴露通用业务字段，不暴露 `skills` / `subagents`

## 4. graph 形态规范

默认推荐：

```python
graph = create_agent(...)
graph = create_deep_agent(...)
graph = builder.compile()
```

默认不推荐：

- 把 `make_graph(config, runtime)` 当成所有 graph 的统一入口
- 为了动态切模型、改 prompt、筛工具而重建 graph

### 4.1 什么时候允许薄 factory

只有满足下面条件时，才允许保留薄 `make_graph(config, runtime)`：

- 必须读取 `ServerRuntime`
- 必须在工厂期装配执行期无法延迟解析的重资源
- 无法通过静态 graph + `RuntimeContext` + middleware 完成
- graph 拓扑依然稳定

如果只是这些需求，不允许上 factory：

- run-level 模型切换
- `system_prompt` 覆盖
- `temperature` / `top_p` / `max_tokens` 动态修改
- 工具启停或工具子集筛选

## 5. 统一运行时解析层

后续 graph 都应围绕一个共享 runtime middleware / resolver 收敛。

这个公共层负责：

- 读取 `RuntimeContext`
- 合并可信注入与 assistant 默认值
- 解析模型与运行参数
- 覆盖 `system_prompt`
- 根据 `enable_tools/tools` 筛选静态注册工具
- 对非法 runtime 输入直接报错

这个公共层不负责：

- 业务流程编排
- 业务服务私逻辑
- 深任务的 `skills` / `subagents` 决策

要求：

- graph 里不要再到处手搓一套 `config/configurable/env` 解析逻辑
- graph 只保留业务默认值和最薄装配
- 中间件职责说明见 `docs/standards/08-middleware-development-playbook.md`

## 6. 工具策略

统一规则：

- `tools/registry.py` 是工具 catalog 唯一真源
- `custom_routes/tools.py` 是对外暴露层，不是 graph 内部真源
- graph 静态声明稳定工具全集
- public optional 工具必须同时静态注册并由 `AgentDefaults.public_tool_names` 或请求 `tools` 显式允许；两者为空时不公开 optional 工具
- 运行时通过 `RuntimeContext.enable_tools/tools` 做筛选
- 运行时不得向模型注入未在 graph 中注册、且没有工具调用执行路径的动态工具
- 工具内部通过 `ToolRuntime.context` 读取业务上下文

不允许：

- 前端上传任意工具实现
- 每次 run 临时拼新工具对象
- 把工具权限藏在 `config.configurable` 里长期传递

## 7. deepagent 额外规则

- `deepagent` 也按静态 graph 收敛。
- `skills` / `subagents` 当前不进入公开 runtime contract。
- `skills` / `subagents` 先只保留为 deepagent 内部静态能力。
- 如果将来要开放，也优先考虑 `profile` / `preset`，不直接裸露内部结构。

## 8. HITL 与多模态

- HITL 默认优先官方 `HumanInTheLoopMiddleware`。
- 多模态属于横切能力，优先放 middleware，不放进 graph 主流程。
- runtime 参数校验错误直接报错。
- 外部增强链路是否允许降级，必须在中间件文档里单独写清楚，不能静默吃掉。

## 9. assistant 样板说明

当前推荐样板：

- `runtime_service/agents/assistant_agent/graph.py`

要求：

- 新功能默认落在 `graph.py`
- 历史范式只保留在 `docs/archive/` 文档中，不再保留运行时代码副本

## 10. 开发流程（执行清单）

1. 明确业务场景，先做模式选型：`create_agent`、`builder.compile()`、`create_deep_agent`
2. 明确字段归位：哪些进 `RuntimeContext`，哪些进 `config`
3. graph 优先静态导出，并显式接入 `context_schema=RuntimeContext`
4. 接入共享 runtime middleware / resolver
5. 静态声明工具全集，再补运行时筛选
6. 接入 HITL / 多模态等横切能力（若需要）
7. 验证：
   - 相关文件无语法错误
   - `compileall` 通过
   - 最小冒烟测试通过

补充：

- 若是业务服务开发，目录与边界请按 `docs/07-service-modularization.md` 执行。

## 11. 禁止事项

- 为了“看起来灵活”默认上 `make_graph(...)`
- 为简单场景引入过重图编排
- 把公共业务字段长期塞进 `config.configurable`
- 绕开共享 runtime 解析层，各 graph 自己发明一套字段读取规则
- 把 `skills` / `subagents` 提前塞进公开 runtime contract
- 通过兼容入口文件扩散旧 graph 形态
