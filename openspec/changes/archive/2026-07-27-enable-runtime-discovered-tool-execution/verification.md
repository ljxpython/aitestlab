# Verification

## Status

- Evidence: Complete
- Disposition: Accepted

## Pre-apply review

- Decision: Approved
- Owner approval or waiver: Owner 于 2026-07-27 在本会话明确回复“批准实施”。
- Scope: `RuntimeRequestMiddleware` 动态工具 model-call 可见性、tool-call 执行绑定及 runtime-service 最短工具调用链。

## Planned evidence

### Local

- 在 `apps/runtime-service` 运行 `uv run pytest runtime_service/tests/test_runtime_request_middleware.py`。
- 运行 research、test-case knowledge、SQL agent 和 tool registry 相关 pytest。
- 运行 `uv run python -m compileall runtime_service`。

### Shortest chain

- 使用 scripted model、fake resolver 和无外部副作用的 dynamic tool 运行最小 `create_agent`/DeepAgents 工具调用链。
- 输入包含模型生成的动态 tool call；结果必须包含该 fake tool 的真实 `ToolMessage`，而不是仅检查 model request 工具列表。
- 运行 `uv run pytest runtime_service/tests/harness`。
- 通过已启动的 `platform-api -> runtime-service -> LightRAG MCP` 真实 HTTP 链路创建 thread、执行 wait run，并从 platform gateway state 读回动态工具 `ToolMessage`。

### Formal / human

- B2 不要求额外 formal chain。
- owner 在 apply 前审阅 proposal、spec、design 和 tasks；实现后确认 disposition。

## Results

- 失败基线：`uv run pytest runtime_service/tests/test_runtime_request_middleware.py -q` -> `7 failed, 9 passed`。
- 失败均为预期缺口：动态 resolver 工具被 model-call 合并过滤、sync/async tool-call hook 未实现、完整 Agent 链生成 invalid-tool `ToolMessage`。
- 实现后：`uv run pytest runtime_service/tests/test_runtime_request_middleware.py -q` -> `16 passed`。
- 相邻 graph/loader/registry：指定 research、test-case v1/v2、SQL、public resolver 与 registry contract 测试 -> `63 passed`。
- Harness：`uv run pytest runtime_service/tests/harness -q` -> `37 passed`。
- 全量：`uv run pytest runtime_service/tests -q` -> `185 passed`；`uv run python -m compileall runtime_service` -> passed。
- 当前仅有既有第三方依赖 deprecation warnings，无本 change 引入的测试失败。
- 文档：已更新 `08-middleware-development-playbook.md` 与 LangGraph 生态调研文档，记录双 hook、执行期重解析、静态优先、fail-closed 和真实 MCP 未覆盖边界。
- `ruff check` 未执行成功：当前 `apps/runtime-service/.venv` 未提供 `ruff` 可执行文件；未新增依赖，改以 pytest、compileall 和 `git diff --check` 验证。
- OpenSpec：`openspec validate enable-runtime-discovered-tool-execution` -> valid。
- Spec sync：`runtime-agent-tool-governance` delta spec 已同步至主规范 `openspec/specs/runtime-agent-tool-governance/spec.md`。
- Graphify：`graphify update .` -> `30040 nodes, 63214 edges, 1203 communities`；超过 5000 节点，按工具保护策略跳过 HTML，`graph.json` 与 `GRAPH_REPORT.md` 已更新。
- 平台栈健康检查：runtime-service、platform-api、platform-web、interaction-data-service、LightRAG HTTP/MCP 和 platform-api worker 均正常。
- 平台 API 首次 live run 使用项目策略中的占位 `deepseek_chat`，runtime 成功枚举 LightRAG MCP 后在首次模型调用收到上游 `401 invalid api key`；该失败与动态工具执行无关。
- 平台 API live E2E 使用项目 `b1740605-a922-4962-958a-e77227b5114c`、graph `test_case_agent_v2`、model `openai_proxy`：登录 `200`，创建 thread `200`，`/runs/wait` `200`；平台注入后的 thread metadata 同时包含正确 `project_id` 与 `graph_id`。
- live run 消息轨迹为 `human -> ai -> tool(read_file) -> ai -> tool(query_project_knowledge) -> ai`；动态 `query_project_knowledge` ToolMessage 为 `status=success`，结果携带正确项目 ID，LightRAG 返回该项目暂未索引知识。
- 通过平台 API `GET /api/langgraph/threads/{thread_id}/state` 再次读回持久化的动态 ToolMessage；用另一项目访问同一 thread 返回 `403 thread_project_denied`。
- platform-api runtime gateway contract、SDK adapter 与 normalization regression：`uv run python -m unittest ... -v` -> `16 tests OK`。platform-api 环境未安装 `pytest`，未为此新增依赖。

## Uncovered boundaries and residual risk

- 本地真实 LightRAG MCP 已经由 platform-api live E2E 覆盖；真实 Tavily 和其他生产 MCP 连接、凭证及外部副作用仍未覆盖。
- model call 与 tool call 之间的远端工具目录漂移采用 fail-closed；首次实现不增加跨 run 缓存。
- CORS、生产 graph 拆分、run budget、领域 benchmark 和 `runtime-web` 交互不属于本 change。

## Docs / runbook impact

- 需要更新 `apps/runtime-service/runtime_service/docs/standards/08-middleware-development-playbook.md` 的动态工具双 hook 规则。
- 需要在 `docs/knowledge/07-langgraph-ecosystem-repository-research.md` 标注该缺口实施后的状态。
- 不需要新增运维 runbook；本 change 不修改 MCP endpoint、secret、部署或恢复操作。

## Disposition

- Accepted. Owner 于 2026-07-27 在本会话明确回复“验收通过并归档”；实现、platform-api E2E、delta-spec sync 与归档前证据均已完成。
