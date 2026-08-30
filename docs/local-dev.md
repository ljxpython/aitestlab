# 本地开发与联调说明

文档类型：`Operational`（仓库级 supporting doc）

本文是给人快速浏览的本地联调摘要；AI 代理在读取 contract 后，也可以继续读取本文来补齐启动、验证和脚本使用细节。

默认本地部署的唯一事实源是 `docs/local-deployment-contract.yaml`；如果本文与 contract 冲突，以 contract 为准。

建议按下面这个事实源优先级理解本地开发文档：

1. `docs/local-deployment-contract.yaml`
2. `README.md` / `README.en.md`
3. `docs/local-dev.md`
4. `docs/env-matrix.md`
5. `docs/deployment-guide.md`

当前仓库的总哲学是 `AI Harness`：

- 根文档定义仓库级边界、契约和默认主链
- 每个 app 在这个 harness 下维护自己的本地范式
- 本文只解释“当前正式本地链路怎么跑起来”，不承担历史全量架构说明

## 1. 当前正式本地链路

以下内容对应 contract 中的正式本地演示 profile。

### 1.1 固定端口

- `apps/runtime-service`: `8123`
- `apps/interaction-data-service`: `8081`
- `apps/platform-api`: `2142`
- `apps/platform-web`: `3000`

可选调试入口：

- `apps/runtime-web`: `3001`

### 1.2 当前默认链路

- 平台主链：`platform-web -> platform-api -> runtime-service`
- 结果域链路：`platform-api -> interaction-data-service`
- Runtime 落库链路：`runtime-service -> interaction-data-service`
- 可选调试链路：`runtime-web -> runtime-service`

### 1.3 非主链应用说明

本文只覆盖当前正式默认本地部署主线。其他非主链应用与历史材料不在本文展开。

## 2. 配置文件口径

根目录不维护统一 `.env`，本地调试时只使用各应用自己的配置文件。

### 2.1 当前正式主链常用配置

- `apps/platform-web/.env.example`
- `apps/platform-web/.env`
- `apps/platform-web/.env.local`
- `apps/platform-api/.env`
- `apps/platform-api/deploy/env/local.example.env`
- `apps/interaction-data-service/.env`
- `apps/runtime-service/runtime_service/.env`
- `apps/runtime-service/runtime_service/conf/settings.yaml`
- `apps/runtime-service/runtime_service/conf/settings.local.yaml`
- `apps/runtime-web/.env`（仅在启用 `runtime-web` 时）

### 2.2 其他说明

本文不展开非主链应用的配置口径。本地联调时，`runtime-web` 应直连 `http://localhost:8123`，不要把它指到控制面地址。

## 3. 推荐启动顺序

1. 启动 `runtime-service`
2. 启动 `interaction-data-service`
3. 启动 `platform-api`
4. 启动 `platform-web`
5. 如需 runtime 调试，再启动 `runtime-web`

这个顺序对应的是当前正式 harness 主链，而不是历史服务全集启动顺序。

## 4. 各应用启动命令

### 4.1 `apps/runtime-service`

启动前先检查 `apps/runtime-service/runtime_service/.env`：

- `MODEL_ID` 留空：使用 `apps/runtime-service/runtime_service/conf/settings.yaml` 当前环境的 `default_model_id`
- `MODEL_ID` 非空：会覆盖默认模型，且必须是 `settings.yaml` 中真实存在的模型 key

如果只是按默认配置联调，建议把 `MODEL_ID` 留空，避免本地 `.env` 残留旧值导致运行时继续选错模型。

```bash
cd apps/runtime-service
uv run langgraph dev --config langgraph.json --port 8123 --no-browser
```

### 4.2 `apps/interaction-data-service`

```bash
cd apps/interaction-data-service
uv run uvicorn main:app --host 127.0.0.1 --port 8081 --reload
```

### 4.3 `apps/platform-api`

```bash
cd apps/platform-api
cp deploy/env/local.example.env .env
uv run uvicorn main:app --host 127.0.0.1 --port 2142 --reload
```

### 4.4 `apps/platform-web`

```bash
cd apps/platform-web
VITE_DEV_PORT=3000 pnpm dev
```

### 4.5 `apps/runtime-web`（可选）

```bash
cd apps/runtime-web
PORT=3001 pnpm dev
```

## 5. 最小健康检查

### 5.0 `interaction-data-service`

```bash
curl http://127.0.0.1:8081/_service/health
```

### 5.1 `runtime-service`

```bash
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

### 5.2 `platform-api`

```bash
curl http://127.0.0.1:2142/_system/health
curl http://127.0.0.1:2142/api/langgraph/info
```

### 5.3 页面访问

- `platform-web`: `http://127.0.0.1:3000`
- `runtime-web`: `http://127.0.0.1:3001`

如果 `platform-api` 的 `/api/langgraph/info` 返回 `200`，说明平台到 runtime 的主联调链路已经打通。

如果 `interaction-data-service` 的 `/_service/health` 返回 `200`，说明结果域服务可用；testcase 等结果域页面是否可用，还要继续经过 `platform-api` 验证项目权限与聚合读取。

## 6. 根级快捷脚本

仓库根目录提供：

```bash
scripts/dev-up.sh
scripts/check-health.sh
scripts/dev-down.sh
```

推荐把它们理解成当前正式主链的固定操作者入口：

- 启动：`scripts/dev-up.sh`
- 健康检查：`scripts/check-health.sh`
- 停止：`scripts/dev-down.sh`

对于最少描述触发的标准部署，AI 代理应先按 contract 完成检查后尝试根脚本 bring-up；如果脚本失败、状态不清或需要隔离诊断，再回退到手工逐个启动。用户不需要额外指挥这一步。

## 7. 当前约定

- 不共享 `.venv`
- 不共享 Node 依赖
- 不共享根级 `.env`
- `apps/platform-web` 是当前正式平台前端宿主
- `apps/platform-api` 是当前正式控制面宿主
- `apps/runtime-service` 是正式 runtime 执行层
- `apps/interaction-data-service` 是正式结果域服务
- `apps/runtime-web` 是可选调试壳，不是默认产品入口
- 先保证正式四服务演示链路可独立运行，再按需处理可选调试入口
