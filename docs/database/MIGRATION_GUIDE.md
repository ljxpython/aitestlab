# 数据库迁移管理指南

## 概述

本项目使用Aerich作为数据库迁移工具，它是专为Tortoise ORM设计的迁移管理工具，类似于Django的migrations或Alembic。

## Aerich配置

### 配置文件
项目中的Aerich配置位于`pyproject.toml`文件中：

```toml
[tool.aerich]
tortoise_orm = "backend.core.database.TORTOISE_ORM"
location = "./migrations"
src_folder = "./."
```

**配置说明**:
- `tortoise_orm`: Tortoise ORM配置的路径
- `location`: 迁移文件存储目录
- `src_folder`: 源代码根目录

### Tortoise ORM配置
数据库配置位于`backend/core/database.py`：

```python
TORTOISE_ORM = {
    "connections": {
        "default": DATABASE_URL
    },
    "apps": {
        "models": {
            "models": [
                "backend.models.user",
                "backend.models.chat",
                "backend.models.testcase",
                "aerich.models"
            ],
            "default_connection": "default",
        },
    },
}
```

## 常用命令

### 初始化数据库

#### 1. 初始化Aerich
```bash
# 使用Makefile命令
make init-db

# 或直接使用Poetry
poetry run python scripts/init_db.py
```

这个命令会：
- 初始化Aerich配置
- 创建初始迁移文件
- 运行迁移创建表结构
- 创建默认数据

#### 2. 手动初始化（如果需要）
```bash
# 初始化Aerich
poetry run aerich init -t backend.core.database.TORTOISE_ORM

# 创建初始迁移
poetry run aerich init-db
```

### 创建迁移

#### 1. 自动检测模型变更
```bash
# 使用Makefile命令
make makemigrations

# 或直接使用Aerich
poetry run aerich migrate
```

#### 2. 创建命名迁移
```bash
# 使用Makefile命令（推荐）
make makemigrations MSG="add_user_profile_fields"

# 或直接使用Aerich
poetry run aerich migrate --name "add_user_profile_fields"
```

### 应用迁移

#### 1. 运行所有待应用的迁移
```bash
# 使用Makefile命令
make migrate

# 或直接使用Aerich
poetry run aerich upgrade
```

#### 2. 查看迁移状态
```bash
# 查看迁移历史
poetry run aerich history

# 查看当前状态
poetry run aerich heads
```

### 回滚迁移

#### 1. 回滚到上一个版本
```bash
poetry run aerich downgrade
```

#### 2. 回滚到指定版本
```bash
poetry run aerich downgrade --version 1
```

### 重置数据库

#### 1. 完全重置（谨慎使用）
```bash
# 使用Makefile命令（会提示确认）
make reset-db

# 手动重置
rm -rf migrations/
rm -f backend/data/aitestlab.db*
make init-db
```

## 迁移文件结构

### 目录结构
```
migrations/
├── models/
│   ├── 0_20241201000000_init.py
│   ├── 1_20241201120000_add_testcase_models.py
│   └── 2_20241202000000_add_user_profile.py
└── aerich.ini
```

### 迁移文件示例
```python
# migrations/models/1_20241201120000_add_testcase_models.py
from tortoise import BaseDBAsyncClient

async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "testcase_conversations" (
            "id" CHAR(36) NOT NULL PRIMARY KEY,
            "user_id" INT,
            "conversation_id" VARCHAR(255) NOT NULL UNIQUE,
            "title" VARCHAR(500),
            "status" VARCHAR(50) NOT NULL DEFAULT 'active',
            "round_number" INT NOT NULL DEFAULT 1,
            "max_rounds" INT NOT NULL DEFAULT 3,
            "text_content" TEXT,
            "files_info" JSON,
            "requirement_analysis" TEXT,
            "generated_testcases" TEXT,
            "final_testcases" TEXT,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "completed_at" TIMESTAMP,
            FOREIGN KEY ("user_id") REFERENCES "users" ("id") ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS "idx_testcase_conversations_user_id" ON "testcase_conversations" ("user_id");
        CREATE INDEX IF NOT EXISTS "idx_testcase_conversations_conversation_id" ON "testcase_conversations" ("conversation_id");
        CREATE INDEX IF NOT EXISTS "idx_testcase_conversations_status" ON "testcase_conversations" ("status");
    """

async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "testcase_conversations";
    """
```

## 最佳实践

### 1. 迁移命名规范
- 使用描述性的名称：`add_user_profile_fields`
- 包含操作类型：`create_`, `add_`, `remove_`, `modify_`
- 避免使用特殊字符和空格

### 2. 模型变更流程
1. **修改模型**: 在`backend/models/`中修改模型定义
2. **创建迁移**: 运行`make makemigrations`
3. **检查迁移**: 查看生成的迁移文件
4. **测试迁移**: 在开发环境中测试
5. **应用迁移**: 运行`make migrate`

### 3. 数据迁移
对于复杂的数据变更，创建自定义迁移：

```python
# 自定义数据迁移示例
async def upgrade(db: BaseDBAsyncClient) -> str:
    # 1. 结构变更
    await db.execute_query("""
        ALTER TABLE users ADD COLUMN profile_image VARCHAR(500);
    """)

    # 2. 数据迁移
    await db.execute_query("""
        UPDATE users SET profile_image = '/default/avatar.png'
        WHERE profile_image IS NULL;
    """)

    return "Added profile_image field with default values"
```

### 4. 回滚策略
- 每次迁移前备份数据库
- 测试回滚脚本的正确性
- 重要变更前创建数据快照

### 5. 生产环境迁移
```bash
# 1. 备份数据库
cp backend/data/aitestlab.db backend/data/aitestlab.db.backup

# 2. 应用迁移
poetry run aerich upgrade

# 3. 验证数据完整性
poetry run python scripts/verify_db.py
```

## 故障排除

### 常见问题

#### 1. 迁移冲突
```bash
# 错误信息
aerich.exceptions.DowngradeError: Can't downgrade to version xxx

# 解决方案
poetry run aerich history
poetry run aerich heads
# 手动解决冲突后重新迁移
```

#### 2. 模型不同步
```bash
# 错误信息
tortoise.exceptions.OperationalError: no such table: xxx

# 解决方案
make reset-db  # 重置数据库（开发环境）
# 或手动同步模型
```

#### 3. 迁移文件损坏
```bash
# 删除损坏的迁移文件
rm migrations/models/xxx_broken_migration.py

# 重新创建迁移
make makemigrations
```

### 调试技巧

#### 1. 查看SQL语句
```python
# 在迁移文件中添加调试信息
async def upgrade(db: BaseDBAsyncClient) -> str:
    sql = "CREATE TABLE ..."
    print(f"Executing SQL: {sql}")
    await db.execute_query(sql)
    return "Migration completed"
```

#### 2. 验证数据库状态
```bash
# 连接到SQLite数据库
sqlite3 backend/data/aitestlab.db

# 查看表结构
.schema users
.schema testcase_conversations

# 查看数据
SELECT * FROM aerich LIMIT 5;
```

## 自动化脚本

### 数据库初始化脚本
项目提供了自动化的数据库初始化脚本`scripts/init_db.py`：

```python
async def main():
    """主函数"""
    # 1. 初始化Aerich
    await init_aerich()

    # 2. 创建初始迁移
    await create_initial_migration()

    # 3. 运行迁移
    await run_migrations()

    # 4. 创建默认数据
    await create_default_data()
```

### 数据验证脚本
创建数据验证脚本确保迁移正确：

```python
# scripts/verify_db.py
async def verify_database():
    """验证数据库完整性"""
    await Tortoise.init(config=TORTOISE_ORM)

    # 验证表存在
    tables = await Tortoise.get_connection("default").execute_query(
        "SELECT name FROM sqlite_master WHERE type='table';"
    )

    # 验证数据完整性
    user_count = await User.all().count()
    print(f"用户数量: {user_count}")

    await Tortoise.close_connections()
```

---

**相关文档**:
- [数据库设计](./DATABASE_DESIGN.md)
- [数据初始化](./DATA_INITIALIZATION.md)
- [开发环境搭建](../development/DEVELOPMENT_SETUP.md)
