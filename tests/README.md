# 测试文件目录

本目录包含AI测试实验室项目的所有测试文件。

## 目录结构

```
tests/
├── README.md                    # 本文件
├── test_config.py              # 配置测试
├── test_makefile.sh            # Makefile功能测试
├── test_testcase_module.py     # 测试用例模块测试
├── unit/                       # 单元测试
│   ├── test_models.py          # 数据模型测试
│   ├── test_services.py        # 服务层测试
│   └── test_utils.py           # 工具函数测试
├── integration/                # 集成测试
│   ├── test_api.py             # API接口测试
│   ├── test_database.py        # 数据库测试
│   └── test_auth.py            # 认证测试
├── e2e/                        # 端到端测试
│   ├── test_user_flow.py       # 用户流程测试
│   └── test_testcase_flow.py   # 测试用例生成流程测试
└── fixtures/                   # 测试数据
    ├── sample_data.json        # 示例数据
    └── test_files/             # 测试文件
```

## 运行测试

### 运行所有测试
```bash
make test
# 或
poetry run pytest tests/ -v
```

### 运行特定类型的测试
```bash
# 单元测试
poetry run pytest tests/unit/ -v

# 集成测试
poetry run pytest tests/integration/ -v

# 端到端测试
poetry run pytest tests/e2e/ -v
```

### 生成测试覆盖率报告
```bash
make test-coverage
# 或
poetry run pytest tests/ --cov=backend --cov-report=html --cov-report=term
```

## 测试配置

### pytest配置
项目使用pytest作为测试框架，配置在`pyproject.toml`中：

```toml
[tool.pytest.ini_options]
minversion = "6.0"
addopts = "-ra -q --strict-markers --strict-config"
testpaths = ["tests"]
asyncio_mode = "auto"
```

### 测试标记
- `@pytest.mark.unit`: 单元测试
- `@pytest.mark.integration`: 集成测试
- `@pytest.mark.e2e`: 端到端测试
- `@pytest.mark.slow`: 慢速测试

### 测试数据库
测试使用独立的数据库：
```bash
DATABASE_URL=sqlite://./backend/data/aitestlab_test.db
```

## 编写测试

### 单元测试示例
```python
# tests/unit/test_models.py
import pytest
from backend.models.user import User

@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_creation():
    """测试用户创建"""
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User"
    )
    user.set_password("password123")

    assert user.username == "testuser"
    assert user.verify_password("password123")
    assert not user.verify_password("wrongpassword")
```

### 集成测试示例
```python
# tests/integration/test_api.py
import pytest
from httpx import AsyncClient
from backend.main import app

@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_registration():
    """测试用户注册API"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
            "full_name": "New User"
        })

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert "id" in data
```

## 测试工具

### 测试夹具
```python
# conftest.py
import pytest
from tortoise.contrib.test import finalizer, initializer

@pytest.fixture(scope="session", autouse=True)
async def initialize_tests():
    """初始化测试环境"""
    await initializer(["backend.models"])
    yield
    await finalizer()

@pytest.fixture
async def test_user():
    """创建测试用户"""
    from backend.models.user import User
    user = await User.create(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashed_password"
    )
    yield user
    await user.delete()
```

### Mock和Stub
```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_ai_service_with_mock():
    """使用Mock测试AI服务"""
    with patch('backend.services.ai_service.openai_client') as mock_client:
        mock_client.chat.completions.create = AsyncMock(
            return_value={"choices": [{"message": {"content": "Test response"}}]}
        )

        # 测试代码
        result = await ai_service.generate_response("test prompt")
        assert result == "Test response"
```

## 持续集成

### GitHub Actions
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.10
    - name: Install dependencies
      run: |
        pip install poetry
        poetry install
    - name: Run tests
      run: |
        poetry run pytest tests/ --cov=backend --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

## 性能测试

### 负载测试
```python
# tests/performance/test_load.py
import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_requests():
    """测试并发请求性能"""
    async def make_request():
        async with AsyncClient(app=app, base_url="http://test") as client:
            return await client.get("/api/health")

    # 并发100个请求
    tasks = [make_request() for _ in range(100)]
    responses = await asyncio.gather(*tasks)

    # 验证所有请求都成功
    for response in responses:
        assert response.status_code == 200
```

## 故障排除

### 常见问题

1. **数据库连接错误**
   ```bash
   # 确保测试数据库配置正确
   export DATABASE_URL=sqlite://./backend/data/aitestlab_test.db
   ```

2. **异步测试问题**
   ```python
   # 确保使用正确的异步测试装饰器
   @pytest.mark.asyncio
   async def test_async_function():
       pass
   ```

3. **测试数据清理**
   ```python
   # 在测试后清理数据
   @pytest.fixture(autouse=True)
   async def cleanup():
       yield
       # 清理代码
   ```

---

**相关文档**:
- [测试指南](../docs/testing/TESTING_GUIDE.md)
- [API测试](../docs/testing/API_TESTING.md)
- [开发环境搭建](../docs/development/DEVELOPMENT_SETUP.md)
