# runtime_service 文档入口

`runtime_service` 是 `runtime-service` 的执行层，负责 graph 注册、运行时参数解析、模型与工具装配、鉴权以及附加能力路由。

## 跨应用 AI 执行入口

如果这是跨应用需求，或者你是先让 AI 判定这件事应不应该落在 `runtime-service`，先读：

1. [Root AGENTS Routing Surface](../../../../AGENTS.md)
2. [AI 执行系统当前标准](../../../../docs/standards/01-ai-execution-system.md)
3. [AI 执行系统使用指南](../../../../docs/ai-execution-system-usage-guide.md)

然后再进入 `runtime_service` 自己的 standards / knowledge / runbooks。

## 新成员先读什么

推荐阅读顺序：

1. `docs/standards/01-harness-overview.md`
2. `docs/standards/02-architecture.md`
3. `docs/standards/03-agent-development-playbook.md`
4. `docs/standards/08-middleware-development-playbook.md`
5. `docs/standards/04-agent-scaffold-templates.md`
6. `docs/standards/05-template-to-runnable-agent-10min.md`
7. `docs/knowledge/04-runtime-contract-v1.md`
8. `docs/knowledge/06-runtime-blueprint-pseudocode.md`
9. `agents/assistant_agent/graph.py`
10. 按专题再读鉴权、runbook、知识文档与其他资料

如果你只是想知道“这个任务该不该先走 runtime-service、该怎么选验证深度”，优先回到：

- [Root AGENTS Routing Surface](../../../../AGENTS.md)
- [AI 执行系统当前标准](../../../../docs/standards/01-ai-execution-system.md)

其中：

- `agents/assistant_agent/graph.py`：当前推荐的 assistant 开发范式
- `agents/deepagent_agent/graph.py`：deepagent 范式参考模板
- `agents/personal_assistant_agent/graph.py`：subagent / supervisor 协作范式参考模板
- `docs/archive/`：历史模板和背景资料，不作为现行开发范式入口

## 当前 graph 一览

- `assistant`：默认主入口，推荐基于它继续演进
- `deepagent_demo`：深任务分解范式
- `customer_support_handoffs_demo`：步骤式状态流范式
- `personal_assistant_demo`：supervisor + subagent 范式
- `research_demo`：deepagent 研究范式（research_agent 私有 skills + 可选 Tavily MCP）
- `skills_sql_assistant_demo`：middleware + skills 范式
- `test_case_agent`：测试用例分析与正式持久化服务，设计见 `docs/10-test-case-service-persistence-design.md`

graph 注册以 `runtime_service/langgraph.json` 和 `runtime_service/langgraph_auth.json` 为准。

## 本地启动

在 `apps/runtime-service` 目录执行：

```bash
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser --allow-blocking
```

说明：

- `research_demo`、`deepagent_demo`、`test_case_agent` 这类依赖 Deep Agents 文件后端/skills 的 graph 可能需要 `--allow-blocking`，否则同步文件 I/O 会被 `blockbuster` 拦成 `BlockingError`。实际 Agent Server 版本以锁文件、固定镜像 digest 与 `/info` 为准，详见 `docs/knowledge/09-langgraph-runtime-upgrade-and-event-migration.md`。
- 如果是部署环境，可以在 `langgraph.json` 中直接使用内联 `env`：

```json
{
  "env": {
    "BG_JOB_ISOLATED_LOOPS": "true"
  }
}
```

- 容器环境也可以直接在启动前设置：

```bash
export BG_JOB_ISOLATED_LOOPS=true
```

- 需要注意：`BG_JOB_ISOLATED_LOOPS=true` 对后台 worker/部署环境有价值，但单独配置它并不能替代当前本地 dev 的 `--allow-blocking`。

## 持久化配置

默认本地开发不变，不设置持久化环境变量时使用内存：

```bash
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser --allow-blocking
```

生产试验直接设置 LangGraph API 官方环境变量：

```bash
export POSTGRES_URI=postgresql://runtime_service:runtime_service@127.0.0.1:5432/runtime_service
export REDIS_URI=redis://127.0.0.1:6379/0
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser --allow-blocking
```

Redis 持久化依赖 Redis Stack，或带 RedisJSON 与 RediSearch 模块的 Redis 8+。普通 Redis 会在 `FT._LIST` 处失败。只试 Postgres 时只设置 `POSTGRES_URI`。

常用验证：

```bash
curl -sS -X POST http://127.0.0.1:8123/assistants/search -H "Content-Type: application/json" -d '{}'
curl -sS http://127.0.0.1:8123/internal/capabilities/tools
curl -sS http://127.0.0.1:8123/internal/capabilities/models
```

## 多模态自测（devtools）

`runtime_service/devtools/` 是开发期自测用的辅助脚本集合，不属于生产运行时逻辑；它的目标是让后端在不依赖前端的情况下复现/检查多模态输入。

- `runtime_service/devtools/multimodal_frontend_compat.py`：把 PDF / 图片等原始输入编码为「前端形状」的 content blocks，便于本地自测。
- `runtime_service/devtools/dump_multimodal_fixtures.py`：遍历并输出 fixtures 的原始 bytes 与（如有）PDF 文本提取结果。
- `runtime_service/tests/multimodal_selfcheck.py`：直接走一遍 `MultimodalMiddleware` 的解析与改写链路，适合单文件调试。

运行命令：

```bash
./.venv/bin/python -m runtime_service.devtools.dump_multimodal_fixtures
uv run python runtime_service/tests/multimodal_selfcheck.py --file runtime_service/test_data/11a1f536fbf8a56a69ffa6b298b2408d.jpeg
uv run python runtime_service/tests/multimodal_selfcheck.py --file runtime_service/test_data/12-多轮对话中让AI保持长期记忆的8种优化方式篇.pdf
```

fixtures 存放在 `runtime_service/test_data/`。

## 运行时最小心智模型

- graph 入口统一从 `langgraph.json` 注册
- 公共业务参数通过 `RuntimeContext` 进入 graph
- graph 内统一通过 `RuntimeRequestMiddleware + runtime/runtime_request_resolver.py` 做模型、prompt、工具解析
- 模型装配统一走 `resolve_runtime_settings(...) + resolve_model_by_id(...)`
- `runtime/options.py` 已删除，不再保留旧运行时入口
- 工具装配在 `tools/registry.py`
- MCP server 清单在 `mcp/servers.py`
- 自定义 HTTP 路由在 `custom_routes/`
- 鉴权逻辑在 `auth/provider.py`

最常用运行时参数：

- `model_id`
- `system_prompt`（仅用于外部覆盖；未提供时由各 graph 自己回退到业务默认 prompt）
- `enable_tools`
- `tools`
- `temperature`
- `max_tokens`
- `top_p`

## 文档分工

- `docs/standards/`：现行标准与开发范式，团队默认以这里为准
- `docs/standards/01-harness-overview.md`：harness 总览与验收范围
- `docs/standards/02-architecture.md`：稳定运行时契约与目录边界
- `docs/standards/03-agent-development-playbook.md`：graph 形态、RuntimeContext、工具与 middleware 的团队规范
- `docs/standards/08-middleware-development-playbook.md`：middleware 生命周期、目录组织与测试规范
- `docs/standards/04-agent-scaffold-templates.md`：现行脚手架模板
- `docs/standards/05-template-to-runnable-agent-10min.md`：从模板到可运行 graph 的最小落地流程
- `docs/knowledge/`：面向学习与官方对照的知识型资料，重点覆盖 `RuntimeContext` / `config` / `create_agent` / SDK 与 HTTP API 传参
- `docs/runbooks/`：排障手册与问题定位文档
- `docs/archive/`：历史模板、旧范式和背景资料，不作为现行实施模板
- `docs/01-auth-and-sdk-validation.md`：鉴权模式与验证方法
- `docs/06-multimodal-middleware-design.md`：当前多模态实现状态与扩展边界
- `docs/07-service-modularization.md`：同一运行时内的业务服务模块化规范
- `docs/10-test-case-service-persistence-design.md`：test_case_service 与 interaction-data-service 的新持久化范式
- `docs/11-testcase-platform-workspace-design.md`：Testcase 平台工作区、管理接口与页面结构的一期设计

知识文档入口：

1. `docs/knowledge/01-langgraph-context-vs-config.md`
2. `docs/knowledge/02-create-agent-params.md`
3. `docs/knowledge/03-sdk-and-curl-passing-context-and-config.md`
4. `docs/knowledge/04-runtime-contract-v1.md`
5. `docs/knowledge/05-runtime-contract-open-questions.md`
6. `docs/knowledge/06-runtime-blueprint-pseudocode.md`
7. `docs/knowledge/07-langgraph-ecosystem-repository-research.md`

## 开发约定

1. 优先参考活代码，不先参考抽象模板
2. 默认以 `assistant_agent/graph.py` 为 create_agent 推荐范式
3. 复杂任务分解参考 `deepagent_agent/graph.py`
4. subagent / supervisor 协作参考 `personal_assistant_agent/graph.py`
5. 现行规范优先参考 `docs/standards/`
6. 知识和官方对照优先参考 `docs/knowledge/`
7. 具体排障优先参考 `docs/runbooks/`
8. 历史模板只在需要理解旧设计时查看 `docs/archive/`
9. 显式步骤流可额外参考 `customer_support_agent/graph.py`
10. 业务服务模块化开发规范见 `docs/07-service-modularization.md`
11. 改完代码后至少跑相关 pytest 与 `python -m compileall runtime_service`
