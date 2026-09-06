# workflow_demo

这是一个真实模型驱动的 Workflow Agent。它使用 Runtime 的模型解析、模型目录连接和
`create_agent` 调用模型；外层 Typed StateGraph 保留条件分支和本地 Interrupt/Resume。

## State And Routes

入口是：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    ...
```

输入支持旧的 `message` 字段以及标准 Chat 的 `messages` 字段，另有 `route` 和
`requires_confirmation`：

- `route="approve"` 进入批准节点；
- `route="reject"` 进入拒绝节点；
- 不提供 `route` 时调用真实模型回答当前对话；
- `requires_confirmation=True` 时先暂停，Resume 的值必须是 `approve` 或 `reject`。
- Chat 请求会从当前 Thread 中最新的 user/human 消息提取文本并传给模型，把最终响应追加到 `messages`；
  同一个 Thread 的每一轮都会处理当前输入，不会复用第一轮的 `message`。

`prepare_count` 是 State 中的验证字段，用于证明 Resume 不会重新执行已完成的准备节点。

## Local Invocation

带 checkpointer 的执行必须提供稳定的 `thread_id`：

```python
from langgraph.types import Command
from runtime_service.services.demo.workflow_demo.agent import get_agent

graph = await get_agent({"configurable": {"_runtime_test_local_auth": True}})
config = {"configurable": {"thread_id": "workflow-example"}}

result = await graph.ainvoke(
    {"message": "hello", "requires_confirmation": True},
    config,
)
interrupt_id = result["__interrupt__"][0].id
resumed = await graph.ainvoke(Command(resume={interrupt_id: "approve"}), config)
```

首次调用返回 `__interrupt__` 和保存的 State；Resume 使用返回的 interrupt ID 和同一个
`thread_id`，从确认点继续。非法 interrupt ID 或 Resume 值不会完成流程，而是返回带有
`workflow.invalid_resume` 的下一次确认点。

## Lifecycle And Verification

`get_agent(config)` 会按当前 Runtime Context 构造模型 Agent；模型连接来自 Platform 模型目录的
受控 opaque reference，未提供目录引用时使用部署级 Runtime Provider 配置。外层 checkpointer
当前是进程内 `InMemorySaver`，只用于本地组合验证；PostgreSQL、Redis、Worker 重启和生产
Durable Run 由 R6 验证。

验证命令：

```bash
uv run pytest tests/services/workflow_demo -q
uv run pytest tests/integration/test_workflow_demo_agent_server.py -m integration -q
```
