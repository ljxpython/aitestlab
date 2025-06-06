# FastAPI 工厂模式架构说明

[← 返回主文档](../../README.md) | [📖 文档中心](../) | [📋 导航索引](../DOCS_INDEX.md)

## 📚 相关文档
- [Makefile 使用指南](./MAKEFILE_GUIDE.md) - 项目管理命令
- [日志系统使用指南](../development/LOGGING_GUIDE.md) - 日志系统使用
- [日志系统实现总结](../development/LOGGING_IMPLEMENTATION.md) - 日志技术实现

## 🏗️ 架构概述

本项目采用工厂模式来创建和配置 FastAPI 应用，提供了更好的模块化、可测试性和可维护性。

## 📁 目录结构

```
backend/
├── __init__.py              # 工厂模式应用创建
├── core/                    # 核心模块
│   ├── __init__.py
│   ├── init_app.py         # 应用初始化逻辑
│   ├── exceptions.py       # 自定义异常
│   └── config_validator.py # 配置验证
├── conf/                   # 配置管理
│   ├── config.py          # 配置加载
│   └── settings.yaml      # 配置文件
├── api/                    # API 路由
├── models/                 # 数据模型
└── services/              # 业务逻辑
```

## 🔧 核心组件

### 1. 应用工厂 (`backend/__init__.py`)

```python
def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.VERSION,
        openapi_url="/openapi.json",
        middleware=make_middlewares(),
        lifespan=lifespan,
    )

    register_exceptions(app)
    register_routers(app, prefix="/api")

    return app
```

### 2. 生命周期管理

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # 启动时执行
    await init_data()
    yield
    # 关闭时执行
    print("🛑 应用正在关闭...")
```

### 3. 中间件配置 (`backend/core/init_app.py`)

```python
def make_middlewares() -> List[Middleware]:
    """Create and configure middlewares"""
    middlewares = [
        Middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
    return middlewares
```

### 4. 异常处理

```python
def register_exceptions(app: FastAPI):
    """Register exception handlers"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(...)

    @app.exception_handler(SettingNotFound)
    async def setting_not_found_handler(request: Request, exc: SettingNotFound):
        return JSONResponse(...)
```

### 5. 路由注册

```python
def register_routers(app: FastAPI, prefix: str = ""):
    """Register application routers"""
    app.include_router(chat_router)

    @app.get("/")
    async def root():
        return {"message": "AI Chat API is running!"}
```

### 6. 配置验证

```python
def validate_settings(settings):
    """Validate application settings"""
    required_fields = [
        'APP_TITLE',
        'APP_DESCRIPTION',
        'VERSION',
        'aimodel.model',
        'aimodel.base_url',
        'aimodel.api_key'
    ]
    # 验证逻辑...
```

## 🎯 优势

### 1. **模块化设计**
- 每个功能模块独立
- 易于测试和维护
- 支持插件式扩展

### 2. **配置管理**
- 集中化配置管理
- 配置验证机制
- 环境变量支持

### 3. **异常处理**
- 统一的异常处理机制
- 自定义异常类型
- 友好的错误响应

### 4. **生命周期管理**
- 应用启动时初始化
- 优雅的关闭处理
- 资源清理机制

### 5. **可测试性**
- 工厂函数易于测试
- 依赖注入支持
- 模拟和存根友好

## 🚀 使用方式

### 开发环境
```python
from backend import create_app

app = create_app()
```

### 测试环境
```python
from backend import create_app

def test_app():
    app = create_app()
    # 测试逻辑...
```

### 生产环境
```python
# main.py
from backend import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 🔄 扩展指南

### 添加新的中间件
在 `backend/core/init_app.py` 的 `make_middlewares()` 函数中添加：

```python
def make_middlewares() -> List[Middleware]:
    middlewares = [
        # 现有中间件...
        Middleware(YourCustomMiddleware, **options),
    ]
    return middlewares
```

### 添加新的路由
在 `backend/core/init_app.py` 的 `register_routers()` 函数中添加：

```python
def register_routers(app: FastAPI, prefix: str = ""):
    # 现有路由...
    app.include_router(your_router, prefix=f"{prefix}/your-path")
```

### 添加新的异常处理
在 `backend/core/init_app.py` 的 `register_exceptions()` 函数中添加：

```python
@app.exception_handler(YourCustomException)
async def your_exception_handler(request: Request, exc: YourCustomException):
    return JSONResponse(...)
```

## 📋 最佳实践

1. **配置管理**: 所有配置都应该通过配置文件管理
2. **异常处理**: 使用自定义异常类型，提供清晰的错误信息
3. **日志记录**: 在关键位置添加日志记录
4. **测试覆盖**: 为每个模块编写单元测试
5. **文档更新**: 及时更新 API 文档和架构说明
