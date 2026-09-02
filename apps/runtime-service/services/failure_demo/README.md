# failure_demo / timeout_demo

这是 R6 的确定性 Tool failure/timeout Service。两个 graph 只注册在 `langgraph.r6.json`，
不进入生产 `langgraph.json`，也不依赖外部模型 Provider。

Graph 每次执行都会调用 `unrecoverable_tool` 并抛出稳定错误
`runtime.demo.unrecoverable_tool`。R6 durable 测试使用真实 Agent Server、PostgreSQL 和 Redis
验证 Run 最终为 failed，且不会产生 success terminal event。

`timeout_demo` 调用 `slow_tool`，由 GraphHarbor 配置的通用 Run deadline 终止。R6 durable
测试验证 Run 最终为 `timeout`，且只有一个 timeout terminal event。
