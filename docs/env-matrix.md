# 环境变量矩阵

文档类型：`Operational`

本文只做配置文件与关键变量索引。

默认本地部署的服务成员、启动顺序、端口和链路，以 [`docs/local-deployment-contract.yaml`](./local-deployment-contract.yaml) 为准。

## 1. `platform-api`

主要配置来源：

- `apps/platform-api/.env`
- `apps/platform-api/.env.example`
- `deploy/.env.stack.example`

关键变量：

- `PLATFORM_API_LANGGRAPH_UPSTREAM_URL`
- `PLATFORM_API_LANGGRAPH_UPSTREAM_API_KEY`
- `PLATFORM_API_RUNTIME_DELEGATION_SECRET`
- `PLATFORM_API_RUNTIME_DELEGATION_KID`
- `PLATFORM_API_RUNTIME_DELEGATION_ISSUER`
- `PLATFORM_API_RUNTIME_DELEGATION_AUDIENCE`
- `PLATFORM_API_RUNTIME_DELEGATION_TTL_SECONDS`
- `PLATFORM_API_INTERACTION_DATA_SERVICE_URL`
- `PLATFORM_API_KNOWLEDGE_UPSTREAM_URL`
- `PLATFORM_API_KNOWLEDGE_UPSTREAM_API_KEY`
- `PLATFORM_API_DATABASE_URL`
- `PLATFORM_API_PLATFORM_DB_ENABLED`
- `PLATFORM_API_PLATFORM_DB_AUTO_CREATE`
- `PLATFORM_API_AUTH_REQUIRED`
- `PLATFORM_API_JWT_ACCESS_SECRET`
- `PLATFORM_API_JWT_REFRESH_SECRET`
- `PLATFORM_API_BOOTSTRAP_ADMIN_ENABLED`

说明：

- `platform-api` 是正式控制面宿主
- 平台侧 RAG / LightRAG HTTP URL 归 `platform-api`
- `apps/lightrag-service` 当前会随默认本地一键启动脚本一起拉起，也仍可替换为外部兼容 LightRAG HTTP 服务
- 如果该上游运行在宿主机，不应写成 `127.0.0.1:<port>`，应改成容器可达地址，例如 `host.docker.internal:<port>`
- 当前验证通过的宿主机可达形态：`http://host.docker.internal:9621`

## 2. `interaction-data-service`

主要配置来源：

- `apps/interaction-data-service/.env`
- `apps/interaction-data-service/.env.example`
- `deploy/.env.stack.example`

关键变量：

- `SERVICE_NAME`
- `INTERACTION_DB_ENABLED`
- `INTERACTION_DB_AUTO_CREATE`
- `DATABASE_URL`
- `DOCUMENT_ASSET_ROOT`

说明：

- 它是结果域服务，不承载平台治理主数据
- 容器化 stack 默认 `INTERACTION_DB_ENABLED=true`

## 3. `platform-web`

主要配置来源：

- `apps/platform-web/.env.example`
- `apps/platform-web/.env.local`
- `deploy/.env.stack.example`

关键变量：

- `VITE_PLATFORM_API_URL`
- `VITE_PLATFORM_API_RUNTIME_ENABLED`
- `VITE_DEV_PROXY_TARGET`
- `VITE_DEV_PORT`
- `VITE_LANGGRAPH_DEBUG_URL`

说明：

- `platform-web` 是正式平台前端宿主
- 正常情况下应通过 `platform-api` 访问平台能力

## 4. `runtime-service`

主要配置来源：

- `apps/runtime-service/runtime_service/.env`
- `apps/runtime-service/runtime_service/.env.example`
- `apps/runtime-service/runtime_service/conf/settings.yaml`
- `apps/runtime-service/runtime_service/conf/settings.local.yaml`
- `apps/runtime-service/deploy/.env.runtime-service.example`
- `deploy/.env.stack.example`

关键变量：

- `APP_ENV`
- `MODEL_ID`
- `MULTIMODAL_PARSER_MODEL_ID`
- `ENABLE_TOOLS`
- `TOOLS`
- `LANGSMITH_API_KEY`
- `LANGSMITH_ENDPOINT`
- `LANGGRAPH_CLOUD_LICENSE_KEY`
- `TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED`
- `TEST_CASE_V2_KNOWLEDGE_MCP_URL`
- `TEST_CASE_V2_KNOWLEDGE_TIMEOUT_SECONDS`
- `TEST_CASE_V2_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS`
- `PLATFORM_RUNTIME_DELEGATION_SECRET`
- `PLATFORM_RUNTIME_DELEGATION_ISSUER`
- `PLATFORM_RUNTIME_DELEGATION_AUDIENCE`
- `PLATFORM_RUNTIME_MANAGEMENT_API_KEY`
- `PYTHON_VERSION=3.13`

说明：

- `MODEL_ID` 建议默认留空，让 `settings.yaml` 的 `default_model_id` 生效
- `PLATFORM_API_RUNTIME_DELEGATION_SECRET` 与 `PLATFORM_RUNTIME_DELEGATION_SECRET` 必须相同且至少 32 bytes
- `PLATFORM_API_LANGGRAPH_UPSTREAM_API_KEY` 与 `PLATFORM_RUNTIME_MANAGEMENT_API_KEY` 必须相同且至少 32 bytes
- `MULTIMODAL_PARSER_MODEL_ID` 控制共享 `MultimodalMiddleware` 的附件解析模型默认值
- 当前容器化基线默认值：`gpt_5.4-ccr`
- 上面这组 `TEST_CASE_V2_*` 变量已经接到 `test_case_service_v2` 的 env fallback
- 它们属于 service-private runtime config，不进入公共 MCP registry
- 默认本地宿主机模式下，repo-local `apps/lightrag-service` 的 MCP SSE 口径收敛为 `http://127.0.0.1:8621/sse`
- 若 `runtime-service` 跑在容器里而 LightRAG 跑在宿主机，不应写成 `0.0.0.0:<port>`，应改成容器可达地址，例如 `host.docker.internal:<port>`
- 当前验证通过的容器内访问形态：`http://host.docker.internal:8621/sse`

## 5. `runtime-web`

主要配置来源：

- `apps/runtime-web/.env`
- `apps/runtime-web/.env.example`

关键变量：

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_ASSISTANT_ID`

说明：

- 当前只作为可选调试入口
- 默认应直连 `runtime-service`

## 6. 当前原则

- 默认正式演示链路的环境变量彼此独立维护
- 根目录不新增统一 `.env`
- `apps/platform-web` 是正式平台前端宿主
- `apps/platform-api` 是正式控制面宿主
- `apps/runtime-service` 是正式执行层
- `apps/interaction-data-service` 是正式结果域服务
