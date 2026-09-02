# Container Update Runbook

文档类型：`Current Runbook`

本文定义当前容器化交付面的标准更新路径。

## 1. 适用范围

适用于：

- `apps/runtime-service` 单应用部署
- 整仓 compose（无 Nginx）
- 整仓 compose（有 Nginx）

## 2. 更新动作分类

### 2.1 代码或 Dockerfile 变更

单应用 `runtime-service`：

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service build
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service up -d
```

如果你修改了 `TEST_CASE_V2_*` 或 `INTERACTION_DATA_SERVICE_*` 这类 runtime 私有 env，也按这条重建 / 重启 `runtime-service`。

整仓 `platform-api` / worker 共镜像：

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack build platform-api
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack up -d --force-recreate platform-api platform-api-worker
```

说明：

- `platform-api-worker` 会执行 `runtime.*.refresh`、`knowledge.documents.*`、`testcase.*.export`、`assistant.resync`
- 这些异步 operation 依赖的 upstream env 必须和 `platform-api` 主容器保持一致
- 如果你改了 `PLATFORM_API_LANGGRAPH_*`、`PLATFORM_API_INTERACTION_DATA_SERVICE_*`、`PLATFORM_API_KNOWLEDGE_*`，要同时重建 / 重启 worker

### 2.2 仅 env / 配置变更

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service up -d --force-recreate runtime-service
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack up -d --force-recreate <service>
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack up -d --force-recreate <service>
```

### 2.3 数据库相关变更

共享 Postgres 初始化入口：

- `deploy/postgres/init/01-init-shared-databases.sh`

标准动作：

1. 先处理数据库更新 / 初始化脚本
2. 必要时清卷重建
3. 再重启受影响服务
4. 再做 health / smoke 验证

### 2.4 Nginx 配置变更

```bash
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack up -d --force-recreate nginx
```

## 3. 推荐验证顺序

### 3.1 单应用 `runtime-service`

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service config
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

### 3.2 整仓 no-nginx stack

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack config
curl http://127.0.0.1:8081/_service/health
curl http://127.0.0.1:2142/_system/probes/ready
curl http://127.0.0.1:8123/info
curl -I http://localhost:3000
```

### 3.3 整仓 nginx stack

```bash
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack config
curl -I http://127.0.0.1:80
curl http://127.0.0.1:80/_system/probes/ready
```

## 4. 回滚原则

标准思路：

1. 先停掉新版本服务
2. 回退到上一个可用镜像或代码版本
3. 如涉及 DB 风险，先恢复备份或回退 migration/init
4. 再重新启动服务
5. 重跑 health / smoke

R6 Runtime 的回滚门禁：

1. 先停止新版本流量或服务实例，不删除 PostgreSQL/Redis volume。
2. 只回退到已验证的上一版 Runtime 镜像；GraphHarbor 包版本必须与该镜像 lockfile 一致。
3. migration 不可逆或恢复失败时，停止切流，保留当前库并由数据库 owner 使用备份恢复；禁止在验收脚本中 drop 现有库。
4. 恢复后执行 `apps/runtime-service/scripts/r6-durable-smoke.sh`、跨网络 SSE 验收和 health/readiness 检查。
5. 灰度比例、route ownership 和 legacy upstream 切换属于 Platform governed change，本 Runbook 不代替其批准。

Runtime 镜像回滚默认只生成计划；真正执行必须同时提供上一版镜像、`--apply` 和显式确认：

```bash
R6_PREVIOUS_RUNTIME_IMAGE=aitestlab-runtime-service:<known-good-tag> \
R6_ROLLBACK_CONFIRM=1 apps/runtime-service/scripts/r6_runtime_rollback.sh --apply
```

脚本不执行 `down`，不删除数据卷，也不修改 Platform gateway 路由。没有已验证上一版镜像时必须失败，不能自动猜测回滚目标。

隔离 PostgreSQL 备份恢复验收：

```bash
R6_POSTGRES_CONTAINER=runtime-service-post17-postgres-1 apps/runtime-service/scripts/r6_postgres_backup_restore.sh
```

该脚本只读导出配置的隔离源容器，并恢复到临时容器；生产灾备仍需数据库 owner 的独立备份存储、恢复点和演练记录。

## 5. 注意事项

- `runtime-service` Lite 模式依赖当前有效的 `LANGSMITH_API_KEY`
- 可选外部知识依赖如果运行在宿主机，不应在容器 env 中写成 `127.0.0.1`
- 可选 MCP 地址不应写成 `0.0.0.0`
- 对容器来说，推荐使用：
  - `host.docker.internal:<port>`
  - 或同网络 service name

## 6. 宿主 PostgreSQL/Redis 模式

本地 PostgreSQL/Redis 可以使用，最快的路径是 API、Worker 和 migration 都在宿主进程运行，三者
共享同一组显式 URI：

```bash
cd apps/runtime-service
export DATABASE_URI="postgresql://<dedicated-user>:<password>@127.0.0.1:<pg-port>/<dedicated-db>"
export REDIS_URI="redis://127.0.0.1:<redis-port>/<dedicated-db>"
uv run graphharbor migrate upgrade
uv run graphharbor serve --host 127.0.0.1 --port <free-api-port> --config langgraph.json --n-jobs-per-worker 0
uv run graphharbor worker --config langgraph.json --n-jobs-per-worker 1
```

三个命令应在独立终端或进程管理器中使用相同环境变量。执行前先按
`docs/solve_problem/r6-validation-harness-and-failure-prevention.md` 完成 PG/Redis 连接、账号权限、
目标库、Redis DB/namespace、端口和 readiness 预检。

当前 `docker-compose.runtime-service.yml` 仍会启动自己的 `postgres`/`redis`，并让 API、Worker、
`migrate` 依赖它们。Docker API/Worker 连接宿主资源目前没有可直接执行的正式 Compose 文件；在
新增 host-infra override/profile 之前，不得只修改 `RUNTIME_POSTGRES_HOST`/`RUNTIME_REDIS_HOST`
就启动。容器访问宿主资源必须使用 `host.docker.internal`，不能使用容器内 `localhost`。

## 7. GraphHarbor 发布门禁

在 GraphHarbor 仓库发布时，两个包必须锁步：
`graphharbor-runtime` 先发布，`graphharbor` 后发布。发布前执行版本一致性、`uv.lock --check`、
lint、完整测试、build、wheel import 和目标 index 可见性检查。

可以使用 `~/.my_best/.env` 中的 `UV_PUBLISH_TOKEN`，但只在发布终端安全加载，不打印或复制 token。
`UV_TEST_PUBLISH_TOKEN` 只用于 TestPyPI 或等价测试 index。Trusted Publishing/OIDC workflow
和本地 token 是互斥发布路径，不能混用，也不能把 token 发布结果记为 OIDC 通过。

PyPI 版本不可覆盖。单包成功、另一包失败时，保留已发布包和证据，修复后递增版本重新发布；
不要删除已发布包、重传同版本或提前把 Runtime lockfile 改到目标 index 尚不可见的版本。

## 8. R6 验收后的清理

验收批次必须有独立 Compose project。正常退出、失败和中断都执行：

```bash
docker compose -p <unique-project> -f <compose-file> down --remove-orphans
```

清理不带 `--volumes`，只删除确认属于该批次的容器、网络和临时镜像；随后扫描 project label、
容器名、监听端口、目标镜像和 Worker 进程。禁止无范围执行 `docker system prune -a`，也不能让
Docker 清理脚本终止宿主 PostgreSQL/Redis。没有残留扫描记录，就不能把本批次验收标记为完成。
