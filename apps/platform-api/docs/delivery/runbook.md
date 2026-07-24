# Platform API Runbook

这份 runbook 先覆盖当前最常见的故障排查路径，目标是让值班和联调时别再一脸懵逼。

## 1. 环境基线

- `local`
  - `SQLite + db_polling`
  - 环境样板：`deploy/env/local.example.env`
- `dev / staging / prod`
  - `PostgreSQL + redis_list`
  - 环境样板：
    - `deploy/env/dev.example.env`
    - `deploy/env/staging.example.env`
    - `deploy/env/prod.example.env`

风险最低的处理方式：

1. 先确认当前环境口径
2. 再决定是查 SQLite 还是 PostgreSQL
3. 再决定 worker 是 `db_polling` 还是 `redis_list`

## 2. 服务活性

先看：

- `GET /_system/probes/live`
- `GET /_system/probes/ready`
- `GET /_system/health`

判定口径：

- `live=alive`：进程活着
- `ready=ready`：数据库和 worker heartbeat 都就绪
- `health=degraded`：大概率是 worker 没起来，或者 heartbeat 已经过期

## 3. worker 没就绪

现象：

- `/_system/probes/ready` 返回 `not_ready`
- `Platform Config` 页面看不到健康 worker

排查顺序：

1. 确认 `uv run python worker.py` 是否已启动
2. 看 worker 日志里是否有 heartbeat 相关输出
3. 看 `operations_queue_backend` 是否与部署环境一致
4. 如果是 `redis_list`，确认 Redis 可连通

## 4. metrics 没数据

现象：

- `/_system/metrics` 请求成功，但 `requests.total` 一直很低或为 0

说明：

- 当前 metrics 是进程内聚合
- 只统计当前 API 进程生命周期内的请求

这不是 bug，是当前阶段设计选择。

## 5. service account 无法调用

排查顺序：

1. 确认 header 是否使用 `x-platform-api-key`
2. 确认 token 未 revoke
3. 确认 service account 状态是 `active`
4. 确认 token prefix 能在数据库查到
5. 确认目标接口权限是否是只读还是写入
6. 项目接口还要确认目标项目存在活动 grant，且项目状态为 `active`

## 5.1 用户登录或刷新失败

- 管理员创建或重置的密码可直接用于正常登录；用户需要时可在账户安全页主动修改。
- 连续五次密码错误会锁定十五分钟，外部统一返回凭据错误，不能据此判断账号是否存在。
- refresh token 重放会撤销整个 family；不要尝试恢复旧 token，要求用户重新登录。

## 6. artifact 下载失败

排查顺序：

1. 先确认 artifact 是否过期
2. 再确认 sidecar metadata 是否还在
3. 再确认本地 artifacts 目录是否存在
4. 如果 future 接对象存储，再看 adapter 配置

## 7. 备份与恢复

做高风险处理前，先备份。

SQLite：

```bash
bash "./scripts/backup_db.sh" sqlite ".data/platform-api.db" ".backup/platform-api.db"
```

PostgreSQL：

```bash
bash "./scripts/backup_db.sh" postgres "postgresql://platform:platform@127.0.0.1:5432/platform_api" ".backup/platform-api.dump"
```

恢复时使用：

```bash
bash "./scripts/restore_db.sh" sqlite ".backup/platform-api.db" ".data/platform-api.db"
bash "./scripts/restore_db.sh" postgres ".backup/platform-api.dump" "postgresql://platform:platform@127.0.0.1:5432/platform_api"
```

## 8. 推荐日志关注点

重点看这些 event：

- `http.request.completed`
- worker 启动/停止日志
- operation 执行失败日志
- API key 鉴权失败日志

## 9. 一线值班最小动作

1. 看 live / ready / health
2. 看 worker 是否在线
3. 看 platform-config 快照
4. 看 audit / operations 是否有失败高峰
5. 必要时做数据库备份再处理

## 10. 最小回滚顺序

1. 先停新版本 API / worker
2. 回退代码或镜像 tag
3. 如有 schema / 数据问题，恢复最近备份
4. 重新拉起 API / worker
5. 再看 `/_system/probes/ready` 和关键页面 smoke

本次 IAM 增量迁移采用非破坏性回滚：回退应用和前端，但保留新增列与
`service_account_project_grants` 表。不得删除身份、grant 或令牌历史来“回到旧版”。
