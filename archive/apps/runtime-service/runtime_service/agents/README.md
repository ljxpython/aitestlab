# runtime_service 智能体开发手册

这份文档只讲当前现行范式，不给历史屎山招魂。

## 1. 先记住这 5 条

1. graph 默认静态导出，能不写 `make_graph(...)` 就别写。
2. 公共业务参数统一走 `RuntimeContext`。
3. 模型 / prompt / tools 的动态能力统一走 `RuntimeRequestMiddleware`。
4. graph 文件只做装配，不自己再发明一套运行时解析规则。
5. 新增 agent 必须同时补注册、测试、文档。

## 2. 推荐目录结构

```text
agents/<your_agent>/
  __init__.py
  graph.py
  prompts.py
  tools.py
```

- `prompts.py`：prompt 常量
- `tools.py`：工具、状态、builder（如确实需要）
- `graph.py`：顶层静态 graph 装配

## 3. `graph.py` 标准写法

默认推荐：

```python
graph = create_agent(...)
graph = create_deep_agent(...)
graph = builder.compile()
```

必须显式做到：

- `context_schema=RuntimeContext`
- 接入 `RuntimeRequestMiddleware(...)`
- prompt / tools / middleware 尽量顶层可见

## 4. 什么时候才允许 factory

只有这些场景才允许保留薄 `make_graph(config, runtime)`：

- 必须读取 `ServerRuntime`
- 必须在 graph 构建期装配不能延迟解析的重资源
- 无法用静态 graph + middleware 完成

下面这些都不算理由：

- 动态切模型
- 动态改 `system_prompt`
- 动态开关 tools
- 运行时参数覆盖

## 5. 新增 agent 必改项

1. `runtime_service/langgraph.json`
2. 相关测试文件
3. `runtime_service/docs/README.md`

## 6. 提交前最少验证

```bash
uv run pytest runtime_service/tests -q
uv run python -m compileall runtime_service
```

## 7. 现成样板

- `runtime_service/agents/assistant_agent/graph.py`
- `runtime_service/agents/deepagent_agent/graph.py`
- `runtime_service/agents/research_agent/graph.py`
- `runtime_service/services/test_case_service/graph.py`
