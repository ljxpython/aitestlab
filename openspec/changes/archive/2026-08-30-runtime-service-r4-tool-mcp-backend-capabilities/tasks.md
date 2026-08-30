## 1. Read-only Tool

- [x] 1.1 在 `reference_agent/tools.py` 定义一个无副作用、带明确 schema 的只读 Tool。
- [x] 1.2 在 reference Service 的 `AgentDefaults`/`RuntimePolicy` 和 `get_agent()` 中显式装配该 Tool。
- [x] 1.3 增加模型可见与执行前 allowlist 测试。

## 2. Deep Agent / Backend / Skills / Subagent

- [x] 2.1 新增 `deep_agent_demo` Service、Graph 导出和 README，使用 `create_deep_agent` 与显式 fake model。
- [x] 2.2 使用 `StateBackend`、一个 bundled Skill 和一个缩权 `SubAgent`，覆盖同 Thread 状态和无外部副作用启动。
- [x] 2.3 新增 `backend_demo`，使用最小 in-memory Backend，验证 thread 隔离、失败关闭和资源不泄漏。

## 3. MCP Demo

- [x] 3.1 新增 `mcp_demo` Service 和本地 fake MCP loader，不连接外部凭据。
- [x] 3.2 实现 Tool 名称冲突检测和显式 allowlist，增加冲突失败测试。

## 4. 配置、文档和验证

- [x] 4.1 更新 `langgraph.demo.json`、R4 Demo README 和 28 号开发计划。
- [x] 4.2 运行 R0-R4 测试、真实模型 E2E、`compileall`、`uv lock --check`、`git diff --check`。
- [x] 4.3 运行 OpenSpec strict validate、更新 graphify，并在 `verification.md` 记录 B3 评审、证据和残余风险。
