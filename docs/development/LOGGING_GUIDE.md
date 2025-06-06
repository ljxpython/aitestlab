# 日志系统使用指南

[← 返回主文档](../../README.md) | [📖 文档中心](../) | [📋 导航索引](../DOCS_INDEX.md)

## 📚 相关文档
- [Makefile 使用指南](../setup/MAKEFILE_GUIDE.md) - 项目管理命令
- [工厂模式架构说明](../setup/FACTORY_PATTERN.md) - 后端架构设计
- [日志系统实现总结](./LOGGING_IMPLEMENTATION.md) - 技术实现详解

## 📋 概述

本项目使用 [loguru](https://github.com/Delgan/loguru) 作为日志库，提供了强大、灵活且易用的日志功能。

## 🏗️ 日志架构

### 日志配置模块 (`backend/core/logger.py`)

- **LoggerConfig**: 日志配置类
- **setup_logging()**: 初始化日志系统
- **get_logger()**: 获取日志器实例
- **装饰器**: 函数调用日志装饰器

### 日志文件结构

```
logs/
├── app.log          # 主日志文件（所有级别）
└── error.log        # 错误日志文件（ERROR 及以上）
```

## 🎯 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| `DEBUG` | 调试信息 | 函数调用、变量值 |
| `INFO` | 一般信息 | 服务启动、请求处理 |
| `SUCCESS` | 成功操作 | 操作完成、初始化成功 |
| `WARNING` | 警告信息 | 配置问题、性能警告 |
| `ERROR` | 错误信息 | 异常、失败操作 |
| `CRITICAL` | 严重错误 | 系统崩溃、致命错误 |

## 🔧 配置说明

### 配置文件 (`backend/conf/settings.yaml`)

```yaml
test:
  LOG_LEVEL: "INFO"        # 日志级别
  LOG_FILE: "ai_chat.log"  # 日志文件名
```

### 日志特性

- **控制台输出**: 彩色格式化输出
- **文件输出**: 结构化日志记录
- **日志轮转**: 10MB 自动轮转
- **日志保留**: 7天自动清理
- **压缩存储**: zip 格式压缩

## 📝 使用方法

### 1. 基本使用

```python
from loguru import logger

# 基本日志记录
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")
logger.success("这是一条成功日志")
```

### 2. 带变量的日志

```python
user_id = "12345"
operation = "登录"

logger.info(f"用户操作 | 用户ID: {user_id} | 操作: {operation}")
```

### 3. 异常日志

```python
try:
    # 一些可能出错的代码
    result = risky_operation()
except Exception as e:
    logger.error(f"操作失败: {e}", exc_info=True)
```

### 4. 使用装饰器

```python
from backend.core.logger import log_function_call, log_async_function_call

@log_function_call
def some_function(param1, param2):
    return param1 + param2

@log_async_function_call
async def async_function(data):
    return await process_data(data)
```

## 🎨 日志格式

### 控制台输出格式
```
2025-06-05 18:03:57 | INFO     | backend:create_app:52 | 创建 FastAPI 应用...
```

### 文件输出格式
```
2025-06-05 18:03:57 | INFO     | backend:create_app:52 | 创建 FastAPI 应用...
```

## 📍 关键日志位置

### 1. 应用生命周期
- 应用启动/关闭
- 配置加载/验证
- 组件初始化

### 2. API 请求处理
- 请求接收
- 参数验证
- 响应生成
- 错误处理

### 3. AutoGen 服务
- Agent 创建
- 对话处理
- 流式响应
- 错误处理

### 4. 异常处理
- HTTP 异常
- 业务异常
- 系统异常

## 🔍 日志查看

### 实时查看日志
```bash
# 查看应用日志
make logs

# 或直接使用 tail
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log
```

### 日志过滤
```bash
# 查看特定级别的日志
grep "ERROR" logs/app.log

# 查看特定模块的日志
grep "autogen_service" logs/app.log

# 查看特定时间的日志
grep "2025-06-05 18:" logs/app.log
```

## 🛠️ 调试技巧

### 1. 开启调试模式
修改配置文件中的日志级别：
```yaml
LOG_LEVEL: "DEBUG"
```

### 2. 临时调试
```python
# 临时降低日志级别
logger.remove()
logger.add(sys.stdout, level="DEBUG")
```

### 3. 性能监控
```python
import time
from loguru import logger

start_time = time.time()
# 执行操作
operation_time = time.time() - start_time
logger.info(f"操作耗时: {operation_time:.2f}s")
```

## 📊 日志分析

### 常用分析命令
```bash
# 统计错误数量
grep -c "ERROR" logs/app.log

# 查看最近的错误
grep "ERROR" logs/app.log | tail -10

# 统计不同级别的日志数量
grep -o "INFO\|WARNING\|ERROR\|SUCCESS" logs/app.log | sort | uniq -c
```

## ⚙️ 高级配置

### 自定义日志格式
```python
from backend.core.logger import LoggerConfig

config = LoggerConfig()
config.setup_logger(
    log_level="DEBUG",
    log_file="custom.log",
    rotation="50 MB",
    retention="30 days"
)
```

### 添加自定义处理器
```python
from loguru import logger

# 添加邮件通知（错误级别）
logger.add(
    "email_handler",
    level="ERROR",
    format="{time} | {level} | {message}",
    # 配置邮件发送参数
)
```

## 🚨 注意事项

1. **敏感信息**: 避免在日志中记录密码、API密钥等敏感信息
2. **性能影响**: 过多的DEBUG日志可能影响性能
3. **磁盘空间**: 定期检查日志文件大小，确保有足够的磁盘空间
4. **日志级别**: 生产环境建议使用INFO级别
5. **异常信息**: 使用 `exc_info=True` 记录完整的异常堆栈

## 📈 最佳实践

1. **结构化日志**: 使用一致的格式记录日志
2. **上下文信息**: 包含足够的上下文信息（用户ID、请求ID等）
3. **错误处理**: 在catch块中记录详细的错误信息
4. **性能监控**: 记录关键操作的耗时
5. **业务日志**: 记录重要的业务操作和状态变化
