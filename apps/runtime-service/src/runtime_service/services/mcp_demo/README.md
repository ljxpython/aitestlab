# mcp_demo

R4 的 Service 私有 MCP 示例。`loader.py` 使用官方 `MultiServerMCPClient` 通过 stdio 启动
`fake_server.py`，调用 `await client.get_tools()` 获取真正的 MCP Tool；组合根在创建 `create_agent`
前完成名称冲突检查和 `allowed_names` allowlist。冲突或未授权工具直接失败，不连接外部 MCP
Server，也不读取凭据。

入口是 `async def get_agent(config: RunnableConfig) -> Pregel`。测试通过
`configurable._mcp_conflict` 验证构图前失败路径。
