## 1. 公共 Middleware

- [x] 1.1 创建 `src/runtime_service/middlewares/` package 及最小公开导出。
- [x] 1.2 实现 `RuntimeConfigMiddleware`：在 agent/model/tool 边界调用 Resolver，绑定模型与生成配置，并对未授权 Tool fail-closed。
- [x] 1.3 实现 `ModelCallTimeoutMiddleware`：使用 `asyncio.timeout` 限制单次模型调用，原样传播超时和取消。

## 2. Reference Agent 装配

- [x] 2.1 在 `reference_agent/agent_server.py` 显式装配 Runtime、官方 Model/Tool limit 和 timeout Middleware，固定顺序。
- [x] 2.2 保留显式 fake model 注入，确保 Middleware 在 fake model 和真实 Provider 路径行为一致。

## 3. 契约测试与文档

- [x] 3.1 新增 Middleware 单元测试，覆盖 Context/Policy 拒绝、模型参数覆盖、Tool 拒绝、超时和取消传播。
- [x] 3.2 新增 reference service 顺序/调用上限测试，确认官方 ToolError/ToolRetry 未被错误扩大捕获范围。
- [x] 3.3 更新 reference README 和 28 号计划的 R3 进度/门槛说明。

## 4. 验证与交付记录

- [x] 4.1 运行 R0-R3 测试、真实模型 E2E、`compileall`、`uv lock --check`、`git diff --check`。
- [x] 4.2 运行 OpenSpec strict validate、更新 graphify，并在 `verification.md` 记录 B3 评审、证据和残余风险。
