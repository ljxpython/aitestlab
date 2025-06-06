"""
日志配置模块
使用 loguru 进行日志管理
"""

import os
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


class LoggerConfig:
    """日志配置类"""

    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

    def setup_logger(
        self,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        rotation: str = "10 MB",
        retention: str = "7 days",
        compression: str = "zip",
    ):
        """
        配置日志器

        Args:
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: 日志文件名，如果为 None 则使用默认名称
            rotation: 日志轮转大小
            retention: 日志保留时间
            compression: 压缩格式
        """
        # 移除默认的控制台处理器
        logger.remove()

        # 添加控制台输出（带颜色）
        logger.add(
            sys.stdout,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>",
            colorize=True,
        )

        # 添加文件输出
        if log_file is None:
            log_file = "app.log"

        log_path = self.log_dir / log_file

        logger.add(
            str(log_path),
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
        )

        # 添加错误日志文件（只记录 ERROR 及以上级别）
        error_log_path = self.log_dir / "error.log"
        logger.add(
            str(error_log_path),
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
        )

        logger.info(f"日志系统初始化完成，日志文件: {log_path}")
        return logger


# 创建全局日志配置实例
log_config = LoggerConfig()


# 设置默认日志配置
def setup_logging(log_level: str = "INFO"):
    """设置日志配置"""
    return log_config.setup_logger(log_level=log_level)


# 获取日志器实例
def get_logger(name: str = None):
    """获取日志器实例"""
    if name:
        return logger.bind(name=name)
    return logger


# 日志装饰器
def log_function_call(func):
    """函数调用日志装饰器"""

    def wrapper(*args, **kwargs):
        logger.debug(f"调用函数: {func.__name__}, 参数: args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"函数 {func.__name__} 执行成功")
            return result
        except Exception as e:
            logger.error(f"函数 {func.__name__} 执行失败: {e}")
            raise

    return wrapper


# 异步函数日志装饰器
def log_async_function_call(func):
    """异步函数调用日志装饰器"""

    async def wrapper(*args, **kwargs):
        logger.debug(
            f"调用异步函数: {func.__name__}, 参数: args={args}, kwargs={kwargs}"
        )
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"异步函数 {func.__name__} 执行成功")
            return result
        except Exception as e:
            logger.error(f"异步函数 {func.__name__} 执行失败: {e}")
            raise

    return wrapper
