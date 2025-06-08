# 数据初始化指南

## 概述

本文档描述了AI测试实验室项目的数据初始化流程，包括默认数据创建、种子数据导入和开发环境数据准备。

## 初始化流程

### 自动初始化
项目提供了自动化的数据库初始化脚本：

```bash
# 使用Makefile命令（推荐）
make init-db

# 或直接运行脚本
poetry run python scripts/init_db.py
```

### 手动初始化
如果需要手动控制初始化过程：

```bash
# 1. 初始化Aerich
poetry run aerich init -t backend.core.database.TORTOISE_ORM

# 2. 创建初始迁移
poetry run aerich init-db

# 3. 运行迁移
poetry run aerich upgrade

# 4. 创建默认数据
poetry run python scripts/create_default_data.py
```

## 默认数据

### 管理员用户
系统会自动创建一个默认的管理员用户：

```python
# 默认管理员账户
username: admin
password: admin123
email: admin@aitestlab.com
full_name: 系统管理员
is_superuser: True
is_active: True
```

**安全提示**: 生产环境中请立即修改默认密码！

### 测试用例模板
系统会创建默认的测试用例模板：

#### 标准功能测试模板
```markdown
## 测试用例模板

### 用例编号: TC_{序号}
### 用例标题: {功能名称}测试
### 测试类型: 功能测试
### 优先级: 高/中/低
### 前置条件:
- 系统正常运行
- 用户已登录

### 测试步骤:
1. 步骤1描述
2. 步骤2描述
3. 步骤3描述

### 预期结果:
- 期望的结果描述

### 后置条件:
- 清理测试数据
```

## 种子数据

### 开发环境数据
为了便于开发和测试，可以创建额外的种子数据：

```python
# scripts/create_seed_data.py
async def create_seed_data():
    """创建开发环境种子数据"""

    # 创建测试用户
    test_users = [
        {
            "username": "testuser1",
            "email": "test1@example.com",
            "full_name": "测试用户1",
            "password": "test123"
        },
        {
            "username": "testuser2",
            "email": "test2@example.com",
            "full_name": "测试用户2",
            "password": "test123"
        }
    ]

    for user_data in test_users:
        existing_user = await User.get_or_none(username=user_data["username"])
        if not existing_user:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                full_name=user_data["full_name"],
                is_active=True
            )
            user.set_password(user_data["password"])
            await user.save()
            logger.info(f"创建测试用户: {user_data['username']}")

    # 创建示例对话
    await create_sample_conversations()

    # 创建测试用例模板
    await create_sample_templates()
```

### 示例对话数据
```python
async def create_sample_conversations():
    """创建示例对话数据"""

    admin_user = await User.get(username="admin")

    # 示例对话1：用户登录功能测试
    conversation1 = TestCaseConversation(
        user_id=admin_user.id,
        conversation_id="sample-login-test",
        title="用户登录功能测试用例生成",
        status="completed",
        round_number=1,
        text_content="需要为用户登录功能生成测试用例，包括正常登录、密码错误、用户名不存在等场景。",
        requirement_analysis="用户登录功能需要验证用户身份，确保系统安全性...",
        generated_testcases="1. 正常登录测试\n2. 密码错误测试\n3. 用户名不存在测试...",
        final_testcases="经过优化的完整测试用例...",
        completed_at=datetime.now()
    )
    await conversation1.save()

    # 添加对话消息
    messages = [
        {
            "content": "开始分析用户登录功能需求...",
            "agent_type": "requirement_agent",
            "agent_name": "requirement_analyst",
            "round_number": 1
        },
        {
            "content": "基于需求分析，生成以下测试用例...",
            "agent_type": "testcase_agent",
            "agent_name": "testcase_generator",
            "round_number": 1
        }
    ]

    for msg_data in messages:
        message = TestCaseMessage(
            conversation=conversation1,
            content=msg_data["content"],
            agent_type=msg_data["agent_type"],
            agent_name=msg_data["agent_name"],
            round_number=msg_data["round_number"]
        )
        await message.save()
```

### 测试用例模板数据
```python
async def create_sample_templates():
    """创建示例测试用例模板"""

    templates = [
        {
            "name": "API接口测试模板",
            "description": "适用于API接口功能测试的模板",
            "category": "接口测试",
            "template_content": """
## API接口测试用例

### 接口信息
- **接口名称**: {接口名称}
- **请求方法**: {GET/POST/PUT/DELETE}
- **请求URL**: {接口地址}

### 测试场景
1. **正常请求测试**
   - 请求参数: {正常参数}
   - 预期响应: {成功响应}

2. **异常请求测试**
   - 请求参数: {异常参数}
   - 预期响应: {错误响应}

3. **边界值测试**
   - 请求参数: {边界参数}
   - 预期响应: {边界响应}
            """,
            "sort_order": 2
        },
        {
            "name": "性能测试模板",
            "description": "适用于系统性能测试的模板",
            "category": "性能测试",
            "template_content": """
## 性能测试用例

### 测试目标
- **响应时间**: < {目标响应时间}ms
- **并发用户**: {并发数量}
- **吞吐量**: {目标TPS}

### 测试场景
1. **负载测试**
   - 模拟正常业务负载
   - 验证系统稳定性

2. **压力测试**
   - 逐步增加负载
   - 找到系统瓶颈

3. **峰值测试**
   - 模拟业务高峰
   - 验证系统承载能力
            """,
            "sort_order": 3
        }
    ]

    for template_data in templates:
        existing_template = await TestCaseTemplate.get_or_none(name=template_data["name"])
        if not existing_template:
            template = TestCaseTemplate(**template_data)
            await template.save()
            logger.info(f"创建测试用例模板: {template_data['name']}")
```

## 数据验证

### 验证脚本
创建数据验证脚本确保初始化正确：

```python
# scripts/verify_initialization.py
async def verify_initialization():
    """验证数据初始化是否正确"""

    await Tortoise.init(config=TORTOISE_ORM)

    try:
        # 验证管理员用户
        admin_user = await User.get_or_none(username="admin")
        assert admin_user is not None, "管理员用户未创建"
        assert admin_user.is_superuser, "管理员权限设置错误"
        logger.success("✅ 管理员用户验证通过")

        # 验证默认模板
        default_template = await TestCaseTemplate.get_or_none(is_default=True)
        assert default_template is not None, "默认模板未创建"
        logger.success("✅ 默认模板验证通过")

        # 验证数据库表
        tables = await Tortoise.get_connection("default").execute_query(
            "SELECT name FROM sqlite_master WHERE type='table';"
        )
        table_names = [table[0] for table in tables]

        required_tables = [
            "users", "testcase_conversations", "testcase_messages",
            "testcase_feedbacks", "testcase_files", "testcase_templates"
        ]

        for table in required_tables:
            assert table in table_names, f"表 {table} 不存在"

        logger.success("✅ 数据库表验证通过")

        # 统计信息
        user_count = await User.all().count()
        template_count = await TestCaseTemplate.all().count()

        logger.info(f"📊 初始化统计:")
        logger.info(f"   用户数量: {user_count}")
        logger.info(f"   模板数量: {template_count}")

    except Exception as e:
        logger.error(f"❌ 验证失败: {e}")
        raise
    finally:
        await Tortoise.close_connections()
```

## 环境配置

### 开发环境
```bash
# .env.development
DATABASE_URL=sqlite://./backend/data/aitestlab_dev.db
DEBUG=True
CREATE_SAMPLE_DATA=True
```

### 测试环境
```bash
# .env.testing
DATABASE_URL=sqlite://./backend/data/aitestlab_test.db
DEBUG=True
CREATE_SAMPLE_DATA=False
```

### 生产环境
```bash
# .env.production
DATABASE_URL=sqlite://./backend/data/aitestlab.db
DEBUG=False
CREATE_SAMPLE_DATA=False
```

## 数据重置

### 完全重置
```bash
# 使用Makefile命令（推荐）
make reset-db

# 手动重置
rm -rf migrations/
rm -f backend/data/aitestlab.db*
make init-db
```

### 仅重置数据
```bash
# 保留表结构，仅清空数据
poetry run python scripts/clear_data.py
poetry run python scripts/create_default_data.py
```

## 备份和恢复

### 数据备份
```bash
# 备份数据库文件
cp backend/data/aitestlab.db backend/data/aitestlab_backup_$(date +%Y%m%d_%H%M%S).db

# 导出数据
poetry run python scripts/export_data.py --output backup/data_$(date +%Y%m%d).json
```

### 数据恢复
```bash
# 恢复数据库文件
cp backend/data/aitestlab_backup_20241201_120000.db backend/data/aitestlab.db

# 导入数据
poetry run python scripts/import_data.py --input backup/data_20241201.json
```

## 故障排除

### 常见问题

#### 1. 初始化失败
```bash
# 检查数据库连接
poetry run python -c "from backend.core.database import DATABASE_URL; print(DATABASE_URL)"

# 检查目录权限
ls -la backend/data/
```

#### 2. 默认用户创建失败
```bash
# 检查用户是否已存在
poetry run python -c "
from backend.models.user import User
import asyncio
from tortoise import Tortoise
from backend.core.database import TORTOISE_ORM

async def check():
    await Tortoise.init(config=TORTOISE_ORM)
    user = await User.get_or_none(username='admin')
    print(f'Admin user exists: {user is not None}')
    await Tortoise.close_connections()

asyncio.run(check())
"
```

#### 3. 模板创建失败
```bash
# 检查模板数据
poetry run python scripts/verify_templates.py
```

---

**相关文档**:
- [数据库设计](./DATABASE_DESIGN.md)
- [迁移管理](./MIGRATION_GUIDE.md)
- [开发环境搭建](../development/DEVELOPMENT_SETUP.md)
