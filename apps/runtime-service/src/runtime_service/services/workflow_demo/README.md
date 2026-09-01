# workflow_demo

这是 R2 的确定性 `StateGraph` 参考 Service。它用 Typed State 演示条件分支和本地
Interrupt/Resume，不需要模型、Provider 凭据或 Platform API。

## State And Routes

入口是：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    ...
```

输入支持 `message`、`route` 和 `requires_confirmation`：

- `route="approve"` 进入批准节点；
- `route="reject"` 进入拒绝节点；
- 不提供 `route` 时保留 R0 的确定性 `workflow response`；
- `requires_confirmation=True` 时先暂停，Resume 的值必须是 `approve` 或 `reject`。

`prepare_count` 是 State 中的验证字段，用于证明 Resume 不会重新执行已完成的准备节点。

## Local Invocation

带 checkpointer 的执行必须提供稳定的 `thread_id`：

```python
from langgraph.types import Command
from runtime_service.services.workflow_demo.agent import get_agent

graph = await get_agent({})
config = {"configurable": {"thread_id": "workflow-example"}}

result = graph.invoke(
    {"message": "hello", "requires_confirmation": True},
    config,
)
interrupt_id = result["__interrupt__"][0].id
resumed = graph.invoke(Command(resume={interrupt_id: "approve"}), config)
```

首次调用返回 `__interrupt__` 和保存的 State；Resume 使用返回的 interrupt ID 和同一个
`thread_id`，从确认点继续。非法 interrupt ID 或 Resume 值不会完成流程，而是返回带有
`workflow.invalid_resume` 的下一次确认点。

## Lifecycle And Verification

Graph 在模块加载时编译一次，`get_agent(config)` 只绑定观测配置，不连接外部资源。当前
checkpointer 是进程内 `InMemorySaver`，只用于 R2 本地组合验证；PostgreSQL、Redis、Worker
重启和生产 Durable Run 由 R6 验证。

验证命令：

```bash
uv run pytest tests/services/workflow_demo -q
uv run pytest tests/integration/test_workflow_demo_agent_server.py -m integration -q
```
