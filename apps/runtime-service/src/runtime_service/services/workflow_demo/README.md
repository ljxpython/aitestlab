# workflow_demo

这是 R0 的最小 `StateGraph` 参考 Service。它用 Typed State 和确定性节点演示显式流程，不需要
模型、Provider 凭据或 Platform API。

正式入口是：

```python
async def get_agent(config: RunnableConfig) -> Pregel:
    ...
```
