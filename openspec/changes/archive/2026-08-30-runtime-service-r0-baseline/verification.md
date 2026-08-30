# R0 验证记录

- Status: Passed
- Disposition: Ready for archive
- Pre-apply review: Approved
- Owner/依据：用户于 2026-08-30 明确要求“调用 OpenSpec，开始 R0”。

## Local

- `uv lock`：通过，解析 133 个包。
- `uv sync`：通过，审计 131 个已安装包。
- `uv run pytest tests/test_r0_baseline.py -q`：通过，`6 passed`。
- `uv run python -m compileall -q src`：通过。
- JSON 配置解析检查：通过，`langgraph.json` 仅含 `reference_agent`，Demo 配置含两个新 Graph。
- `uv run langgraph dev --config ./langgraph.json --port 8123 --no-browser`：启动成功。
- `curl -fsS http://127.0.0.1:8123/info`：通过，返回 LangGraph API `0.13.0` 和 Python `1.2.11`。
- 启动日志确认只导入 `./src/runtime_service/graphs/reference_agent.py`；服务已正常停止。

## Real-model E2E

- 规则：`RUNTIME_E2E=1` 时必须使用 DeepSeek 文本中转；多模态测试使用 GPT 中转；缺少凭据不得降级为 fake model。
- 未加载环境变量时，E2E 按设计跳过，不伪装为通过。
- `set -a; . ./.env; set +a; RUNTIME_E2E=1 uv run pytest tests/e2e/test_reference_agent_real_model.py -m e2e -q`：通过，`1 passed`。
- 该测试使用 DeepSeek 文本中转；未输出或写入 API Key。多模态 GPT 中转配置已进入 `.env.example`，对应测试留到后续多模态能力阶段。

## Shortest chain

- R0 只涉及 `apps/runtime-service`，不启动 `platform-api`；未执行跨服务契约测试，符合本阶段范围。

## Formal / Human

- 本变更属于 runtime-service 单一 locus；pre-apply review 已获用户批准。本阶段不要求 Platform 或生产部署门禁。

## 未覆盖边界与残余风险

- Auth、RuntimeContext、Resolver、Middleware、Provider、MCP、Backend、Checkpoint、Trace 和 Platform Gateway 属于后续阶段。
- Auth、RuntimeContext、Resolver、Middleware、Provider、MCP、Backend、Checkpoint、Trace 和 Platform Gateway 属于后续阶段。
- R0 的基线图使用 fake model；真实 Provider 仅通过显式 DeepSeek E2E 验证连通性和最小响应，不能替代后续模型解析契约。

## Docs / Runbook

- 已更新 28 号计划为 R0 实施完成，并修正根配置暂不含 Auth 的口径。
- 已更新 13 号目标目录文档，记录 Legacy 代码已归档且不再维护。
- 已重写 `apps/runtime-service/README.md`，补充新目录、Demo、启动、配置和测试入口。
- 旧 `runtime_service/` 包、旧标准和旧本地配置已归档；本阶段不新增生产运维 runbook。
