"""
Application initialization functions
"""

from typing import List

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.api.chat import router as chat_router


async def init_data():
    """Initialize application data"""
    logger.info("开始初始化应用数据...")

    # 这里可以添加数据库初始化、缓存预热等逻辑
    try:
        # 示例：初始化数据库连接
        logger.debug("初始化数据库连接...")

        # 示例：预热缓存
        logger.debug("预热应用缓存...")

        # 示例：检查外部服务连接
        logger.debug("检查外部服务连接...")

        logger.success("🚀 应用数据初始化完成")
    except Exception as e:
        logger.error(f"应用数据初始化失败: {e}")
        raise


def make_middlewares() -> List[Middleware]:
    """Create and configure middlewares"""
    logger.info("配置应用中间件...")

    middlewares = [
        Middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]

    logger.debug(f"已配置 {len(middlewares)} 个中间件")
    return middlewares


def register_exceptions(app: FastAPI):
    """Register exception handlers"""
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse

    from backend.core.exceptions import (
        ConfigurationError,
        ServiceError,
        SettingNotFound,
    )

    logger.info("注册异常处理器...")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(
            f"HTTP异常: {exc.status_code} - {exc.detail} | 请求: {request.url}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP Exception",
                "detail": exc.detail,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(SettingNotFound)
    async def setting_not_found_handler(request: Request, exc: SettingNotFound):
        logger.error(f"配置错误: {exc} | 请求: {request.url}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Configuration Error",
                "detail": str(exc),
                "status_code": 500,
            },
        )

    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError):
        logger.error(f"服务错误: {exc} | 请求: {request.url}")
        return JSONResponse(
            status_code=503,
            content={"error": "Service Error", "detail": str(exc), "status_code": 503},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"未处理的异常: {exc} | 请求: {request.url}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(exc),
                "status_code": 500,
            },
        )

    logger.debug("异常处理器注册完成")


def register_routers(app: FastAPI, prefix: str = ""):
    """Register application routers"""
    logger.info("注册应用路由...")

    # 注册聊天路由
    app.include_router(chat_router)
    logger.debug("聊天路由注册完成")

    # 注册基础路由
    @app.get("/")
    async def root():
        logger.debug("根路径被访问")
        return {"message": "AI Chat API is running!"}

    @app.get("/health")
    async def health_check():
        logger.debug("健康检查被访问")
        return {"status": "healthy"}

    logger.success(f"✅ 路由注册完成，前缀: {prefix}")
