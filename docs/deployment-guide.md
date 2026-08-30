# 部署准备与环境说明

本文是当前正式本地部署的补充说明，重点保留系统依赖、配置准备、启动方式、验证路径和常见排错信息。

默认本地部署的唯一事实源是 `docs/local-deployment-contract.yaml`；如果本文与 contract 冲突，以 contract 为准。

如果你要看已经收敛的容器化交付方向，另见：

- [`deploy/README.md`](../deploy/README.md)
- [`apps/runtime-service/deploy/README.md`](../apps/runtime-service/deploy/README.md)
- [`docs/zero-to-one-container-deploy.md`](./zero-to-one-container-deploy.md)
- [`docs/container-address-guide.md`](./container-address-guide.md)
- [`docs/runbooks/container-update-runbook.md`](./runbooks/container-update-runbook.md)

## 1. 当前正式部署口径

### 1.1 正式默认链路

当前正式默认本地链路是：

```text
platform-web -> platform-api -> runtime-service
runtime-service -> interaction-data-service
platform-api -> interaction-data-service
```

可选调试链路：

```text
runtime-web -> runtime-service
```

### 1.2 当前正式服务集合

默认本地 demo / 联调集合：

- `apps/runtime-service`
- `apps/interaction-data-service`
- `apps/platform-api`
- `apps/platform-web`

可选调试入口：

- `apps/runtime-web`

本文只覆盖这套正式默认链路，不展开非主链应用。

补充说明：

- 本文主要说明当前本地默认部署口径
- 容器化部署属于新增交付面，单独收敛在 `deploy/README.md`

### 1.3 当前正式端口

- `runtime-service`: `8123`
- `interaction-data-service`: `8081`
- `platform-api`: `2142`
- `platform-web`: `3000`
- `runtime-web`: `3001`（可选）

## 2. 这个仓库为什么这样部署

当前仓库的总哲学不是“把所有代码都堆到一个服务里”，而是把它当成一套可供 AI 和人类持续协同开发的 `AI Harness`：

- 平台治理层：`platform-web` + `platform-api`
- 运行时执行层：`runtime-service`
- 结果域承接层：`interaction-data-service`
- 可选调试壳：`runtime-web`

也就是说，这篇文档解决的是“怎么把当前正式链路跑起来”，不是“所有历史服务怎么一起启动”。

如果你想理解为什么架构要这么拆，先看：

- `docs/development-paradigm.md`
- `apps/platform-api/docs/handbook/project-handbook.md`

## 3. 系统依赖准备

### 3.1 Python / uv

当前 Python 服务统一要求：

- `Python >= 3.13`
- `uv`

建议检查：

```bash
python3 --version
uv --version
```

如果本机没有 Python 3.13，可用：

```bash
uv python install 3.13
```

### 3.2 Node / pnpm

当前前端应用建议对齐：

- `Node 22.x`
- `pnpm 10.5.1`

证据源：

- `docs/local-deployment-contract.yaml`
- `apps/platform-web/package.json`

建议检查：

```bash
node -v
pnpm -v
```

### 3.3 PostgreSQL

当前正式默认 demo 并不强制要求 PostgreSQL 作为全部服务前提，但如果你要切到真实数据库部署、扩展结果域或平台侧持久化，建议本机准备一个 PostgreSQL 实例。

当前 contract 中的默认参考值：

- host: `127.0.0.1`
- port: `5432`
- database: `agent_platform`
- user: `agent`

## 4. 配置文件准备

### 4.1 总原则

- 不依赖 repo-root `.env`
- 只使用各应用自己的配置文件
- 配置文件优先以 app-local 模板和 contract 为准

### 4.2 `apps/runtime-service`

必须检查：

- `apps/runtime-service/runtime_service/.env`
- `apps/runtime-service/runtime_service/conf/settings.yaml`

最关键的不是“把文件凑齐”，而是保证：

- `.env` 中有 `APP_ENV`
- `MODEL_ID` 要么留空，要么是 `settings.yaml` 中真实存在的模型 key
- `PLATFORM_RUNTIME_DELEGATION_SECRET` 与 platform-api 的签发 secret 相同且至少 32 bytes
- `PLATFORM_RUNTIME_MANAGEMENT_API_KEY` 与 platform-api 的 upstream API key 相同且至少 32 bytes
- `settings.yaml` 中存在 `default.default_model_id`
- `settings.yaml` 中存在对应的 `default.models.<model_id>` 配置块

如果缺配置，建议优先看：

- `docs/local-deployment-contract.yaml`
- `docs/env-matrix.md`
- `apps/runtime-service/README.md`

### 4.3 `apps/interaction-data-service`

必须检查：

- `apps/interaction-data-service/.env`

最小关键变量：

- `SERVICE_NAME=interaction-data-service`
- `INTERACTION_DB_ENABLED=false` 或者配置有效 `DATABASE_URL`

### 4.4 `apps/platform-api`

必须检查：

- `apps/platform-api/.env`

关键变量包括：

- `PLATFORM_API_LANGGRAPH_UPSTREAM_URL=http://127.0.0.1:8123`
- `PLATFORM_API_LANGGRAPH_UPSTREAM_API_KEY`
- `PLATFORM_API_RUNTIME_DELEGATION_SECRET`
- `PLATFORM_API_RUNTIME_DELEGATION_ISSUER=platform-api`
- `PLATFORM_API_RUNTIME_DELEGATION_AUDIENCE=runtime-service`
- `PLATFORM_API_INTERACTION_DATA_SERVICE_URL=http://127.0.0.1:8081`
- `PLATFORM_API_DATABASE_URL=sqlite+pysqlite:///./.data/platform-api.db`
- `PLATFORM_API_PLATFORM_DB_ENABLED=true`
- `PLATFORM_API_PLATFORM_DB_AUTO_CREATE=true`
- `PLATFORM_API_JWT_ACCESS_SECRET`
- `PLATFORM_API_JWT_REFRESH_SECRET`
- `PLATFORM_API_BOOTSTRAP_ADMIN_ENABLED=true`
- `PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME=admin`
- `PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD=admin123456`

### 4.5 `apps/platform-web`

当前正式前端宿主可使用：

- `apps/platform-web/.env.example`
- `apps/platform-web/.env`
- `apps/platform-web/.env.local`

最小本地建议：

```env
VITE_PLATFORM_API_URL=http://localhost:2142
VITE_PLATFORM_API_RUNTIME_ENABLED=true
VITE_DEV_PROXY_TARGET=http://localhost:2142
VITE_DEV_PORT=3000
VITE_LANGGRAPH_DEBUG_URL=
```

### 4.6 `apps/runtime-web`（可选）

仅在你要使用 runtime 调试壳时检查：

- `apps/runtime-web/.env`

默认应直连：

```env
NEXT_PUBLIC_API_URL=http://localhost:8123
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

不要把它指向控制面地址；`runtime-web` 应始终直连 `runtime-service`。

## 5. 推荐启动方式

### 5.1 推荐优先使用根脚本

当前正式 bring-up 推荐入口：

```bash
scripts/dev-up.sh
scripts/check-health.sh
scripts/dev-down.sh
```

它们统一代理到正式 demo 脚本：

- `scripts/platform-web-demo-up.sh`
- `scripts/platform-web-demo-health.sh`
- `scripts/platform-web-demo-down.sh`

### 5.2 手工逐服务启动顺序

如果脚本失败或你需要隔离排查，按下面顺序手工启动：

1. `runtime-service`
2. `interaction-data-service`
3. `platform-api`
4. `platform-web`
5. `runtime-web`（可选）

## 6. 各服务启动命令

### 6.1 `apps/runtime-service`

```bash
cd apps/runtime-service
uv run langgraph dev --config langgraph.json --port 8123 --no-browser
```

如果你在本地调试依赖 Deep Agents 文件后端/skills 的 graph，按该应用 README 的说明带 `--allow-blocking`。

### 6.2 `apps/interaction-data-service`

```bash
cd apps/interaction-data-service
uv run uvicorn main:app --host 127.0.0.1 --port 8081 --reload
```

### 6.3 `apps/platform-api`

```bash
cd apps/platform-api
uv run uvicorn main:app --host 127.0.0.1 --port 2142 --reload
```

### 6.4 `apps/platform-web`

```bash
cd apps/platform-web
VITE_DEV_PORT=3000 pnpm dev
```

### 6.5 `apps/runtime-web`（可选）

```bash
cd apps/runtime-web
PORT=3001 pnpm dev
```

## 7. 最小健康检查

### 7.1 服务健康

```bash
curl http://127.0.0.1:8081/_service/health
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:2142/_system/health
curl http://127.0.0.1:2142/api/langgraph/info
```

### 7.2 页面访问

- `platform-web`: `http://localhost:3000`
- `platform-web` 兼容入口：`http://127.0.0.1:3000`
- `runtime-web`: `http://127.0.0.1:3001`（可选）

如果 `platform-api` 的 `/api/langgraph/info` 返回 `200`，且 `interaction-data-service` 的 `/_service/health` 返回 `200`，说明当前正式平台链路和结果域链路已经基本打通。

## 8. 常见排查方向

### 8.1 前端能打开，但平台链路不通

优先检查：

- `apps/platform-web/.env*` 是否仍残留旧地址
- `platform-api` 是否已启动到 `2142`
- `VITE_DEV_PROXY_TARGET` 是否指向 `http://localhost:2142`
- 如果你不是从 `localhost:3000` 或 `127.0.0.1:3000` 访问前端，检查 `PLATFORM_API_CORS_ALLOW_ORIGINS`

### 8.2 Runtime 可用，但平台聊天/线程链路异常

优先检查：

- `platform-api` 的 runtime gateway 配置
- 当前项目上下文与权限
- `apps/platform-web/src/router/routes.ts` 对应页面是否已经属于当前正式范围

### 8.3 interaction-data-service 接口正常，但文档与实现不一致

以当前真实实现为准，优先参考：

- `apps/interaction-data-service/docs/README.md`
- `apps/interaction-data-service/app/api/**`

### 8.4 看到与本文不一致的旧宿主 / 旧端口口径

这通常意味着你正在读历史文档、过渡文档，或者某篇文档尚未完成收口。

当前正式默认链路只认：

- `platform-web`
- `platform-api`
- `2142`
- `8081`

## 9. 推荐阅读顺序

如果你是第一次接手当前仓库，推荐这样读：

1. `docs/local-deployment-contract.yaml`
2. `README.md`
3. `docs/local-dev.md`
4. `docs/env-matrix.md`
5. `docs/development-paradigm.md`
6. `apps/platform-api/docs/handbook/project-handbook.md`

如果你是要让 AI 帮你部署，入口仍然是：

- `docs/ai-deployment-assistant-instruction.md`

## 10. 文档边界说明

本文属于 `Operational` 文档：

- 它解释当前正式默认部署如何准备和启动
- 它不是历史服务全集说明
- 它也不是唯一事实源

如果后续架构再次重构，优先更新：

1. `docs/local-deployment-contract.yaml`
2. 根脚本与实际服务配置
3. 本文和 `docs/local-dev.md`
