## 1. 先建立失败证据

- [x] 1.1 更新 `test_runtime_request_middleware.py`，证明合法 resolver 动态工具在 model call 阶段可见，并保留静态工具优先和 public allowlist 语义
- [x] 1.2 增加 `wrap_tool_call` / `awrap_tool_call` 单元测试，覆盖动态工具绑定、执行阶段不再可用、未授权、静态同名优先和 sync/async 一致性
- [x] 1.3 增加无外部 secret 的最小 Agent 调用链测试，使用 scripted model 和 fake dynamic tool 断言最终生成真实 `ToolMessage`

## 2. 实现动态工具执行闭环

- [x] 2.1 在 `RuntimeRequestMiddleware` 中提取基于 runtime context 的 settings 与 required/public runtime tool 解析 helper，保持现有 resolver 接口不变
- [x] 2.2 调整 model-call 工具合并，使获准动态工具可见，同时保持 graph 已注册工具和 DeepAgents 内置工具优先
- [x] 2.3 实现 `wrap_tool_call` / `awrap_tool_call`，仅为当前 runtime context 再次解析并精确匹配的动态工具绑定真实实现，未匹配路径保持 fail-closed
- [x] 2.4 运行相关 graph/loader 测试，确认 research、test-case、SQL 和 public MCP resolver 不需要新增工厂或第二套工具接口

## 3. 验证最短执行链

- [x] 3.1 在 `apps/runtime-service` 运行 runtime middleware、research agent、test-case knowledge、SQL agent 和 tool registry 相关 pytest
- [x] 3.2 运行 `runtime_service/tests/harness`，证明静态 graph、RuntimeContext 和工具治理契约仍成立
- [x] 3.3 运行 `uv run pytest runtime_service/tests` 与 `uv run python -m compileall runtime_service`，记录完整结果和未覆盖边界
- [x] 3.4 运行 `openspec validate enable-runtime-discovered-tool-execution` 和 `graphify update .`，确认变更产物与代码图一致

## 4. 文档与验收证据

- [x] 4.1 更新 middleware 现行规范和 LangGraph 生态调研文档中的动态工具状态，明确双 hook、fail-closed 与外部 MCP 未覆盖边界
- [x] 4.2 持续更新 `verification.md` 的 pre-apply review、执行命令、输入、结果、残余风险、docs/runbook 决策和 disposition
- [x] 4.3 owner 验收后同步 `runtime-agent-tool-governance` delta spec，再归档 change；若拒绝或放弃则记录 disposition 并跳过 sync
