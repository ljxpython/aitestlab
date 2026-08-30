# runtime_service Harness Tests

这里存放 `runtime_service` 的开发范式验收测试。

目标不是测业务正确性，而是测“是否符合现行工程标准”。

## 1. 计划中的第一批检查

### 1.1 graph contract

检查项：

- graph 默认应静态导出
- 新 graph 不应把 `make_graph(...)` 当默认范式
- `create_agent(...)` / `create_deep_agent(...)` / `builder.compile()` 应显式声明 `context_schema=RuntimeContext`

### 1.2 runtime context contract

检查项：

- `RuntimeContext` 字段表符合 v1 定义
- 不应包含 `environment`
- 不应包含 `skills`
- 不应包含 `subagents`

### 1.3 middleware contract

检查项：

- 共享 runtime middleware 存在
- model/tools/system_prompt 的运行时解析由共享 middleware 驱动
- 非法 `model_id` / `tools` 直接报错
- `test_case_service` 不得从 `state / configurable / metadata / system prompt` 反推 `project_id`
- `runtime/options.py` 不再存在

### 1.4 tool registry contract

检查项：

- `tools/registry.py` 是公开可选工具唯一真源
- graph-required tools 不应塞进公共 registry
- 不再暴露 `build_tools(options)` 这种旧入口

### 1.5 graph registration

检查项：

- `langgraph.json` 里的 graph 都有 `description`
- 注册路径有效

## 2. 原则

- harness 测试优先测“结构约束”，不是业务细节
- 单测失败时，应该能直接指出违反了哪条开发范式
- 不为 harness 引入多余抽象层
