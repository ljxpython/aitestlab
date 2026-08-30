# reference_agent

这是 R2 的最小 Runtime-aware `create_agent` 参考 Service。组合根会先解析
`RuntimeContext`、`AgentDefaults` 和本地演示 `RuntimePolicy`，再创建模型和 Agent Graph。

生产默认路径使用 `DEEPSEEK_PROXY_*` Provider 配置，缺少凭据时直接失败，不会静默切换 fake
model。测试可以通过 `configurable._runtime_model` 显式注入 `FakeListChatModel`，这种注入不属于
生产配置。

正式入口是：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    ...
```

Graph 注册由根目录的 `langgraph.json` 和 `langgraph.demo.json` 负责。

本地组合测试示例：

```python
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from runtime_service.runtime import RuntimeContext
from runtime_service.services.reference_agent.agent import get_agent

graph = await get_agent({"configurable": {"_runtime_model": FakeListChatModel(responses=["ok"])}})
result = await graph.ainvoke(
    {"messages": [{"role": "user", "content": "hello"}]},
    context=RuntimeContext(),
)
```

`get_agent(config)` 只负责构图配置；每次 Run 的 Context 使用 LangGraph 的 `context` 参数传入，
不会写入 `configurable` 或 Prompt。无 Thread 级外部资源时默认 graph 可复用；未来需要
Workspace/Sandbox 时才改为按 Thread 动态构图。

R3 在组合根中显式加入 `RuntimeConfigMiddleware`、官方模型/工具调用上限和单次模型超时。
R4 增加 `read_reference` 只读 Tool，并同时通过模型可见性过滤和执行前 allowlist 检查；写入、
MCP、Sandbox 和 Subagent 能力由对应 R4 Demo 单独展示，不塞进这个最小模板。
