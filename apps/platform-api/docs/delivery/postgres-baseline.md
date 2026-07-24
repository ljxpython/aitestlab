# Platform API PostgreSQL 基线

这份文档把 `platform-api` 的 PostgreSQL 开发基线定死，避免后面一边写模块一边乱长 schema。

## 1. 当前口径

当前阶段的数据库策略：

- 日常快速烟测继续允许使用 SQLite
- `identity / projects / announcements / audit / assistants` 这批核心模块稳定后
- `platform-api` 的默认开发数据库切到 PostgreSQL

从这一步开始：

- PostgreSQL 是默认开发/验收数据库
- SQLite 只保留给超轻量 smoke test
- 不再把 `create_all` 当正式建库方案
- schema 变更统一走 Alembic

## 2. 默认环境变量

建议使用：

```bash
export PLATFORM_API_PLATFORM_DB_ENABLED=true
export PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false
export PLATFORM_API_DATABASE_URL=postgresql+psycopg://bytedance@127.0.0.1:5432/agent_platform
```

说明：

- `PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false`
  - PostgreSQL 基线场景下必须关闭自动建表
- `PLATFORM_API_DATABASE_URL`
  - Alembic 和应用启动都使用这一条连接串

## 3. 初始化本地开发库

如果本机 PostgreSQL 已经跑在 `127.0.0.1:5432`：

```bash
psql -h 127.0.0.1 -d postgres -c "DROP DATABASE IF EXISTS agent_platform;"
psql -h 127.0.0.1 -d postgres -c "CREATE DATABASE agent_platform;"
```

如果你要换数据库名，记得同步修改 `PLATFORM_API_DATABASE_URL`。

## 4. Alembic 命令

初始化/升级：

```bash
cd apps/platform-api
PLATFORM_API_DATABASE_URL=postgresql+psycopg://bytedance@127.0.0.1:5432/agent_platform \
uv run alembic upgrade head
```

查看当前 revision：

```bash
cd apps/platform-api
PLATFORM_API_DATABASE_URL=postgresql+psycopg://bytedance@127.0.0.1:5432/agent_platform \
uv run alembic current
```

生成新 revision：

```bash
cd apps/platform-api
PLATFORM_API_DATABASE_URL=postgresql+psycopg://bytedance@127.0.0.1:5432/agent_platform \
uv run alembic revision -m "describe change"
```

## 5. 启动应用

```bash
cd apps/platform-api
PLATFORM_API_PLATFORM_DB_ENABLED=true \
PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false \
PLATFORM_API_DATABASE_URL=postgresql+psycopg://bytedance@127.0.0.1:5432/agent_platform \
uv run uvicorn main:app --host 127.0.0.1 --port 3035
```

本地开发如果要保留 bootstrap admin：

```bash
export PLATFORM_API_BOOTSTRAP_ADMIN_ENABLED=true
export PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME=admin
export PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD=admin123456
```

## 6. 当前 baseline 包含哪些表

首个 revision 已覆盖：

- `users`
- `refresh_tokens`
- `tenants`
- `projects`
- `project_members`
- `announcements`
- `announcement_reads`
- `agents`
- `assistant_profiles`
- `audit_logs`

IAM 增量 revision `20260723_0001` 还增加：

- `users.must_change_password / failed_login_attempts / locked_until`
- `refresh_tokens.family_id / consumed_at`
- `service_account_project_grants`

这意味着当前核心控制面样板模块都已经有 PostgreSQL 基线落点。

## 7. 后续开发规则

后续所有 schema 变更必须遵守：

1. 先改模块模型
2. 再补 Alembic revision
3. 再跑 PostgreSQL upgrade
4. 最后再跑应用联调

禁止继续靠：

- 手工进库改字段
- 直接删库后 `create_all`
- 新模块写完却不补 migration

应用回滚时保留上述新增列和 grant 表，不执行破坏性 downgrade，不恢复已经消费或
撤销的 refresh token。前端和 API 的登录/资料响应契约必须成对回滚。
