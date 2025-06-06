# Makefile 使用指南

[← 返回主文档](../../README.md) | [📖 文档中心](../) | [📋 导航索引](../DOCS_INDEX.md)

## 📚 相关文档
- [工厂模式架构说明](./FACTORY_PATTERN.md) - 了解后端架构
- [日志系统使用指南](../development/LOGGING_GUIDE.md) - 日志查看和调试
- [问题排查指南](../troubleshooting/) - 故障排除方案

## 🚀 快速开始

```bash
# 查看所有命令
make help

# 安装所有依赖
make install

# 启动所有服务
make start

# 查看服务状态
make status

# 停止所有服务
make stop
```

## 📦 环境管理

### 安装依赖
```bash
make install          # 安装所有依赖
make install-backend  # 仅安装后端依赖 (使用 Poetry)
make install-frontend # 仅安装前端依赖 (使用 npm)
```

### Poetry 管理
```bash
make poetry-shell     # 进入 Poetry 虚拟环境
make poetry-show      # 显示依赖信息
make poetry-update    # 更新所有依赖

# 添加依赖
make add-dep DEP=requests
make add-dev-dep DEP=pytest

# 移除依赖
make remove-dep DEP=requests
```

## 🌐 服务管理

### 启动服务
```bash
make start            # 启动所有服务
make start-backend    # 启动后端 (nohup 后台运行)
make start-frontend   # 启动前端开发服务器
```

### 停止服务
```bash
make stop             # 停止所有服务
make stop-backend     # 停止后端服务
make stop-frontend    # 停止前端服务
```

### 查看状态
```bash
make status           # 查看服务运行状态
make show-processes   # 显示所有相关进程
make logs             # 查看后端日志 (实时)
```

## 🔧 其他功能

### 测试和清理
```bash
make test-config      # 测试配置是否正确
make clean            # 清理临时文件 (PID、日志等)
make force-clean      # 强制清理所有进程
```

## 📁 生成的文件

- `backend.pid` - 后端进程 PID
- `frontend.pid` - 前端进程 PID
- `backend.log` - 后端日志
- `frontend.log` - 前端日志

## 🛠️ 技术特点

- ✅ 使用 Poetry 管理 Python 依赖
- ✅ 使用 nohup 后台运行服务
- ✅ 自动 PID 管理和进程监控
- ✅ 彩色输出和友好的用户界面
- ✅ 错误处理和状态检查
- ✅ 日志文件管理

## 🚨 注意事项

1. **Poetry 要求**: 确保已安装 Poetry 1.4+
2. **权限问题**: 确保有写入权限创建 PID 和日志文件
3. **端口冲突**: 后端默认使用 8000 端口，前端使用 3000 端口
4. **进程管理**: 使用 `make stop` 正确停止服务，避免僵尸进程

## 🔍 故障排除

### 服务启动失败
```bash
# 查看日志
make logs
tail -f backend.log

# 检查配置
make test-config

# 清理并重启
make clean
make start
```

### Poetry 问题
```bash
# 检查 Poetry 版本
poetry --version

# 重新安装依赖
poetry install --no-root

# 查看依赖
make poetry-show
```
