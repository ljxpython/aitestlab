# deep_agent_demo

R4 的 `create_deep_agent` 最小示例。组合根在 `agent.py` 直接声明：

- `StateBackend`：文件状态由 LangGraph Thread/Checkpoint 承载；
- `skills/runtime-notes/SKILL.md`：Bundled Skill，按 Deep Agents 机制发现；
- `summarizer`：显式 `tools=[]` 的缩权 Subagent。

入口仍是 `async def get_agent(config: RunnableConfig) -> Pregel`。示例默认使用本地 fake model，
测试可通过 `configurable._runtime_model` 注入支持 `bind_tools()` 的模型；不连接 Sandbox、MCP
或 Platform API。
