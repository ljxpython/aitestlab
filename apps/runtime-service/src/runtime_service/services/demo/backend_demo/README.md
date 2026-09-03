# backend_demo

R4 的 Backend 最小示例。`get_agent()` 直接创建进程内 `StateBackend` 并交给
`create_deep_agent`，用于展示 Backend 的显式装配，不切换到其他目录或外部存储。当前示例不
声称已实现 Thread Workspace 持久化、跨 Worker 重连、清理或生产租户隔离。每次构图都是独立
graph 对象，初始化失败直接抛出，不做静默 fallback。

入口是 `async def get_agent(config: RunnableConfig) -> Pregel`，默认 fake model 不需要外部服务。
