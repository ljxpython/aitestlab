# 从零到一容器化部署指南

文档类型：`Current How-To`

这份文档面向第一次接触本项目的人，目标是回答：

> 我拿到项目后，怎么一步一步把它用容器跑起来，并确认前端真的能用？

## 1. 先选部署模式

本项目当前有 3 种容器化入口：

1. 单应用 `runtime-service`
2. 整仓 no-nginx stack
3. 整仓 nginx stack

如果你只是想验证 `runtime-service` 本身，选第 1 种。
如果你想验证平台前端、平台后端和结果域链路，选第 2 或第 3 种。

推荐顺序：

1. 单应用 `runtime-service`
2. 整仓 no-nginx stack
3. 整仓 nginx stack

## 2. 前置条件

至少需要：

- Docker Desktop 或等价 Docker 环境
- 当前有效的 `LANGSMITH_API_KEY`

如果你还要启用可选知识依赖：

- 平台侧 RAG HTTP 地址
- runtime 私有 MCP SSE 地址

补充说明：

- `apps/lightrag-service` 可以作为可选仓库内知识服务单独运行
- 它不属于默认 Compose 成员；默认四服务容器栈不会自动把它带起来
- 宿主机直跑该可选服务时，repo-local 默认 MCP SSE 地址按 `http://127.0.0.1:8621/sse` 约定

地址如何填写，另见：

- [`docs/container-address-guide.md`](./container-address-guide.md)

## 3. 单应用 `runtime-service`

### 3.1 准备配置

```bash
cp apps/runtime-service/deploy/.env.runtime-service.example apps/runtime-service/deploy/.env.runtime-service
```

至少确认：

- `LANGSMITH_API_KEY`
- `LANGSMITH_ENDPOINT`
- `LANGGRAPH_CLOUD_LICENSE_KEY` 留空

如果要启用 runtime 私有 knowledge MCP：

- `TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED=true`
- 宿主机直跑 LightRAG 时：`TEST_CASE_V2_KNOWLEDGE_MCP_URL=http://host.docker.internal:8621/sse`

### 3.2 启动

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service up -d
```

### 3.3 验证

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service ps
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

### 3.4 停止

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service down
```

## 4. 整仓 no-nginx stack

### 4.1 准备配置

```bash
cp deploy/.env.stack.example deploy/.env.stack
```

至少确认：

- `LANGSMITH_API_KEY`
- `LANGSMITH_ENDPOINT=https://api.smith.langchain.com`
- `LANGGRAPH_CLOUD_LICENSE_KEY` 留空

如果要启用可选知识依赖：

- `PLATFORM_API_KNOWLEDGE_UPSTREAM_URL`
- `TEST_CASE_V2_KNOWLEDGE_MCP_URL=http://host.docker.internal:8621/sse`

### 4.2 启动

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack up -d
```

### 4.3 验证服务状态

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack ps
curl http://127.0.0.1:8081/_service/health
curl http://127.0.0.1:2142/_system/probes/ready
curl http://127.0.0.1:8123/info
curl -I http://localhost:3000
```

### 4.4 前端验证

浏览器打开：

- `http://localhost:3000`
- `http://127.0.0.1:3000` 也可用

验证路径：

1. 打开登录页
2. 用 `admin / admin123456` 登录
3. 进入后确认：
   - 首页能打开
   - 项目列表能打开
   - Runtime 页面能打开
   - Testcase / Knowledge 页面至少能加载壳层

如果你要看浏览器请求：

- 登录接口应打到：
  - `http://localhost:2142/api/identity/session`
- 不应该打到：
  - `http://localhost:3000/api/identity/session`

### 4.5 如果你看到这个错误

```text
POST http://localhost:3000/api/identity/session 404 (Not Found)
nginx/1.29.8
```

这说明前端是按**同源 `/api`** 方式构建出来了，但你跑的是 **no-nginx stack**。

当前正确状态应该是：

- no-nginx stack 的前端构建参数已经固定为：
  - `VITE_PLATFORM_API_URL_DIRECT=http://localhost:2142`
  - `VITE_PLATFORM_API_RUNTIME_ENABLED=true`

如果你仍看到这个 404，优先做：

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack build platform-web
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack up -d --force-recreate platform-web
```

然后重新刷新浏览器。

### 4.6 如果你用的不是 localhost

默认 no-nginx stack 已放行：

- `http://localhost:3000`
- `http://127.0.0.1:3000`

如果你准备从其他主机名、局域网 IP 或外网域名访问前端，需要同时调整：

- `VITE_PLATFORM_API_URL_DIRECT`
- `VITE_PLATFORM_API_RUNTIME_ENABLED`
- `PLATFORM_API_CORS_ALLOW_ORIGINS`

### 4.7 停止

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack down
```

## 5. 整仓 nginx stack

### 5.1 启动

```bash
cp deploy/.env.stack.example deploy/.env.stack
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack up -d
```

### 5.2 验证

```bash
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack ps
curl -I http://127.0.0.1:80
curl http://127.0.0.1:80/_system/probes/ready
```

浏览器打开：

- `http://127.0.0.1`

这时前端应走同源代理：

- `/` -> `platform-web`
- `/api/` -> `platform-api`
- `/_system/` -> `platform-api`

### 5.3 停止

```bash
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack down
```

## 6. 查看日志

单应用：

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service logs -f
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service logs -f runtime-service
```

整仓 no-nginx：

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack logs -f
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack logs -f runtime-service
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack logs -f platform-api
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack logs -f interaction-data-service
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack logs -f platform-web
```

整仓 nginx：

```bash
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack logs -f
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack logs -f nginx
```

## 7. 地址填写规则

记不住时，直接看：

- [`docs/container-address-guide.md`](./container-address-guide.md)

最短规则：

- 宿主机服务：`host.docker.internal`
- Docker 网络服务：`service-name`
- 外网服务：真实 URL
