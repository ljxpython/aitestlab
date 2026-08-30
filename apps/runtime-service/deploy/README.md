# Runtime-Service Container Deployment

文档类型：`Planned Delivery Guide`

本文描述的是 `apps/runtime-service` 的单应用容器化交付面。对应文件资产已经开始落地，但还不是已验证完成的运行事实。

## 1. 目标

让用户在不理解整仓控制面细节的情况下，单独把 `runtime-service` 跑起来。

目标拓扑：

- `runtime-service`
- `redis`
- `postgres`

补充说明：

- 单应用 `runtime-service` compose 中的 Postgres 默认只在容器网络内可达
- 默认不绑定宿主机 `5432`
- 这样可以避免和本机已有 PostgreSQL 冲突

## 2. 镜像构建原则

规划已收敛为：

- 使用仓库内受管 Dockerfile
- 路径：`apps/runtime-service/deploy/Dockerfile`
- Python 基线：`3.13`
- 当前官方基座镜像 tag：`langchain/langgraph-api:3.13`；共享/生产部署必须进一步固定为可追溯 digest。
- 用户应可直接使用 `docker compose build` / `docker compose up -d`
- 不要求用户先安装 LangGraph CLI
- 当前验证结论：
  - `langgraph-api` license-gated 基座镜像在无 key 条件下会启动失败
  - 本仓应改为基于 `langgraph dev` 能力的容器运行路线

说明：

- Dockerfile 可以最初参考 `langgraph dockerfile` 的生成结果
- 但最终交付物应作为仓库内一等文件维护

## 3. 配置归属

### 3.1 模型配置

模型相关真实配置仍归：

- `runtime_service/.env`
- `runtime_service/conf/settings.local.yaml`

其中：

- `.env` 放轻量环境选择与默认项
- `settings.local.yaml` 放真实模型组配置

容器里的共享多模态附件解析默认模型：

- `MULTIMODAL_PARSER_MODEL_ID`
- 当前容器化基线默认值：`gpt_5.4-ccr`

如果未配置这个值，代码默认会回退到 `doubao_vision_mini`。

### 3.2 runtime 私有 knowledge MCP

规划中的 env 名称：

- `TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED`
- `TEST_CASE_V2_KNOWLEDGE_MCP_URL`
- `TEST_CASE_V2_KNOWLEDGE_TIMEOUT_SECONDS`
- `TEST_CASE_V2_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS`

这些值属于：

- service-private runtime config

不属于：

- 公共 MCP registry

### 3.3 runtime 远端持久化

如果你希望 `test_case_service` / `test_case_service_v2` 把正式结果持久化到远端 `interaction-data-service`，还需要：

- `INTERACTION_DATA_SERVICE_URL`
- `INTERACTION_DATA_SERVICE_TOKEN`
- `INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS`

如果这组值未配置，`persist_test_case_results` 会返回：

- `status=skipped_remote_not_configured`

### 3.4 运行时 config 文件

默认容器化 config 源：

- `langgraph.json`

若未来需要鉴权模式，可另行支持：

- `langgraph.json`（R1 加入 Auth 后更新）

## 4. Graph 范围

当前规划默认：

- 跟随根级 `langgraph.json` 注册的 graph 集

当前已知风险：

- 至少部分 graph 存在 blocking-IO 敏感性，后续实现时必须通过真实容器 smoke 验证

## 5. 未来交付物

计划中的文件：

- `apps/runtime-service/deploy/Dockerfile`
- `apps/runtime-service/deploy/docker-compose.runtime-service.yml`
- `apps/runtime-service/deploy/.env.runtime-service.example`

当前已补齐到：

- `apps/runtime-service/deploy/Dockerfile`
- `apps/runtime-service/deploy/docker-compose.runtime-service.yml`
- `apps/runtime-service/deploy/.env.runtime-service.example`
- `apps/runtime-service/.dockerignore`

仍待完成：

- 镜像 build 级验证
- 容器启动级验证
- health / graph registry 运行级验证

当前验证发现：

- `langgraph dev` 在无 license 条件下仍能正常提供：
  - `/info`
  - `/internal/capabilities/models`
  - `/internal/capabilities/tools`
- 因此后续 runtime 容器应改为围绕该运行模式构建

更新结论：

- 当前交付继续沿用官方 `langgraph-api` 基座镜像路线
- 运行模式按 Lite 模式收敛：
  - 提供 `LANGSMITH_API_KEY`
  - 提供有效 `LANGSMITH_ENDPOINT`（默认 `https://api.smith.langchain.com`）
  - `LANGGRAPH_CLOUD_LICENSE_KEY` 留空

## 6. 更新与重建

更新 runbook 不在本页展开，统一收敛到：

- [`docs/runbooks/container-update-runbook.md`](../../../docs/runbooks/container-update-runbook.md)

核心原则已经确定：

- 代码 / Dockerfile 变更：
  - rebuild + recreate
- 仅 env/config 变更：
  - recreate

## 7. 历史设计记录

以下内容只用于追溯原始容器化决策：

- [PRD](../../../.harness/plans/prd-containerized-deployment-20260421.md)
- [Test Spec](../../../.harness/plans/test-spec-containerized-deployment-20260421.md)
- [TODO Checklist](../../../.harness/plans/todo-containerized-deployment-20260421.md)
