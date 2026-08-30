# backend_demo

R4 的 Backend 最小示例。`get_agent()` 直接创建 `StateBackend` 并交给
`create_deep_agent`，文件状态只存在当前 LangGraph Thread 的 state 中，不切换到其他目录或
外部存储。每次构图都是独立资源边界，初始化失败直接抛出，不做静默 fallback。

入口是 `async def get_agent(config: RunnableConfig) -> Pregel`，默认 fake model 不需要外部服务。
